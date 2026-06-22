"""`aln reset` command."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import click
from fp import get_fp_home
from fp.utils.storage import StorageManager, get_storage_manager

from .misc.process import is_pid_alive, stop_pid


def _stop_ui_process(fp_home_path: Path) -> bool:
    """Stop UI process from pid file when present."""
    pid_files = list(fp_home_path.glob("ui_*.pid"))

    # 向后兼容旧的 ui.pid 文件
    old_pid_file = fp_home_path / "ui.pid"
    if old_pid_file.exists():
        pid_files.append(old_pid_file)

    if not pid_files:
        return False

    stopped_any = False
    for pid_file in pid_files:
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
            if stop_pid(pid):
                stopped_any = True
        except (OSError, ValueError):
            pass
        finally:
            pid_file.unlink(missing_ok=True)

        # 同时删除对应的 port 文件
        port_file = pid_file.parent / pid_file.name.replace(".pid", ".port")
        port_file.unlink(missing_ok=True)

    return stopped_any


def _find_orphan_host_pids(exclude_pids: set[int]) -> list[int]:
    """Find host runtime pids not tracked in config."""
    if os.name == "nt":
        command = [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            (
                "Get-CimInstance Win32_Process | "
                "Where-Object { $_.CommandLine -like "
                "'*uvicorn aln.app.main:app*' } | "
                "ForEach-Object { '{0} {1}' -f "
                "$_.ProcessId, $_.CommandLine }"
            ),
        ]
    else:
        command = ["ps", "-ax", "-o", "pid=,command="]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []

    if result.returncode != 0:
        return []

    matched_pids: list[int] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        parts = stripped.split(maxsplit=1)
        if len(parts) != 2:
            continue

        pid_text, command_text = parts
        if "uvicorn aln.app.main:app" not in command_text:
            continue

        try:
            pid = int(pid_text)
        except ValueError:
            continue

        if pid in exclude_pids:
            continue
        if not is_pid_alive(pid):
            continue

        matched_pids.append(pid)

    return matched_pids


def _delete_all_hosts(storage: StorageManager) -> tuple[int, int]:
    """删除所有hosts及其entities，返回(删除成功数, 失败数)."""
    from aln.app.service import HostClient, HostClientError

    hosts = storage.get_all_hosts()
    deleted_count = 0
    failed_count = 0

    for host_uid, host_config in list(hosts.items()):
        click.echo(f"Deleting host '{host_config.name}'...")

        # 获取该host下的所有entities
        entity_uids = storage.get_entities_for_host(host_uid)
        pid = storage.get_host_pid(host_uid)

        # 通知 parent 注销 child
        if host_config.parent_url:
            try:
                parent_client = HostClient(host_config.parent_url, timeout=5.0)
                parent_client.unregister_child(host_uid)
                click.echo(f"  ✓ Unregistered from parent")
            except Exception as e:
                click.echo(f"  ⚠ Failed to unregister from parent: {e}")

        # 如果host正在运行，通过API删除entities
        if pid and is_pid_alive(pid):
            try:
                host_url = storage.get_host_url(host_uid)
                client = HostClient(base_url=host_url, timeout=5.0)

                for entity_uid in entity_uids:
                    try:
                        client.entity_delete(entity_uid)
                        click.echo(f"  ✓ Deleted entity {entity_uid[:8]}")
                    except HostClientError as e:
                        click.echo(f"  ⚠ Failed to delete entity {entity_uid[:8]}: {e}")
            except Exception as e:
                click.echo(f"  ⚠ Failed to connect to host: {e}")

            # 停止host进程
            if stop_pid(pid):
                click.echo(f"  ✓ Host stopped (PID: {pid})")
            else:
                click.echo(f"  ⚠ Failed to stop host (PID: {pid})")

        # 从配置和文件系统中删除host
        try:
            storage.delete_host_from_config(host_uid)
            click.echo(f"  ✓ Host '{host_config.name}' deleted")
            deleted_count += 1
        except Exception as e:
            click.echo(f"  ✗ Failed to delete host: {e}")
            failed_count += 1

    return deleted_count, failed_count


@click.command(name="reset", context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def command(yes: bool) -> None:
    """Reset FP system by deleting all hosts, entities, and data.

    WARNING: This will:
    - Stop the web UI
    - Delete all hosts and their entities (with proper cleanup)
    - Delete all data in ~/.fp directory

    This action cannot be undone!
    """
    fp_home = get_fp_home()

    if not yes:
        click.echo("This will:")
        click.echo("  - Stop web UI (if running)")
        click.echo("  - Delete all hosts and entities")
        click.echo(f"  - Delete all data in {fp_home}")
        click.echo("")
        click.echo("This action CANNOT be undone!")
        click.echo("")

        if not click.confirm("Are you sure you want to reset?"):
            click.echo("Aborted.")
            sys.exit(0)

    click.echo("Resetting FP system...")

    fp_home_path = Path(os.path.expanduser(fp_home))

    click.echo("Stopping UI...")
    ui_stopped = _stop_ui_process(fp_home_path)
    if ui_stopped:
        click.echo("✓ UI stopped")
    else:
        click.echo("No UI process found")

    storage = get_storage_manager()
    known_pids: set[int] = set()

    # 删除所有hosts（包括通过API删除entities）
    click.echo("Deleting hosts...")
    if storage.exists():
        # 收集所有已知PID
        hosts = storage.get_all_hosts()
        for host_uid in hosts:
            pid = storage.get_host_pid(host_uid)
            if pid:
                known_pids.add(pid)

        deleted, failed = _delete_all_hosts(storage)
        click.echo(f"Deleted {deleted} hosts")
        if failed:
            click.echo(f"✗ Failed to delete {failed} hosts")
    else:
        click.echo("No host config found")

    # 停止孤儿进程
    click.echo("Stopping orphan host processes...")
    orphan_pids = _find_orphan_host_pids(exclude_pids=known_pids)
    orphan_stopped = 0
    for pid in orphan_pids:
        if stop_pid(pid):
            orphan_stopped += 1
    click.echo(f"Stopped orphan hosts: {orphan_stopped}")

    # Delete ~/.fp directory (清理残留数据)
    if fp_home_path.exists():
        click.echo(f"Cleaning up {fp_home_path}...")
        try:
            shutil.rmtree(fp_home_path)
            click.echo(f"✓ Deleted {fp_home_path}")
        except Exception as e:
            click.echo(f"✗ Failed to delete {fp_home_path}: {e}")
            sys.exit(1)
    else:
        click.echo(f"Directory {fp_home_path} does not exist")

    click.echo("")
    click.echo("✓ Reset complete!")
    click.echo("Run 'aln host new' to set up a new host")
