"""`aln ui` command group."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import click

from fp import get_fp_home
from fp.utils.storage import get_storage_manager

from .misc.common import generate_qr_lines, get_local_ip
from .misc.process import is_pid_alive


def _get_ui_status() -> dict | None:
    """获取 UI 状态"""
    config_dir = Path(get_fp_home())
    pid_file = config_dir / "ui.pid"
    port_file = config_dir / "ui.port"

    if not pid_file.exists():
        return None

    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)  # 检查进程是否存在
        port = int(port_file.read_text().strip()) if port_file.exists() else 5173
        return {"pid": pid, "port": port}
    except (OSError, ValueError, ProcessLookupError):
        # 进程不存在，清理文件
        pid_file.unlink(missing_ok=True)
        port_file.unlink(missing_ok=True)
        return None


def _show_all_hosts_entities(ui_port: int) -> None:
    """显示所有 host 上的 human entities 及其访问链接（从本地 config 读取）"""
    storage = get_storage_manager()
    config = storage.load_config()

    humans_by_host: dict[str, list[tuple[str, str]]] = {}
    for entity_uid, entity_entry in config.entities.items():
        if entity_entry.kind == "human" and entity_entry.enabled:
            humans_by_host.setdefault(entity_entry.host_uid, []).append(
                (entity_uid, entity_entry.name)
            )

    if not humans_by_host:
        click.echo("\n📋 No human entities found")
        return

    local_ip = get_local_ip()
    ui_base_local = f"http://localhost:{ui_port}"
    ui_base_public = f"http://{local_ip}:{ui_port}"

    for host_uid, entities in humans_by_host.items():
        host_entry = config.hosts.get(host_uid)
        if not host_entry or not host_entry.enabled:
            continue

        bind_host_local = "127.0.0.1" if host_entry.bind_host == "0.0.0.0" else host_entry.bind_host
        host_url_local = f"http://{bind_host_local}:{host_entry.port}"
        host_url_public = f"http://{local_ip}:{host_entry.port}"

        pid = storage.get_host_pid(host_uid)
        host_alive = pid is not None and is_pid_alive(pid)
        status_mark = "✓" if host_alive else "✗"

        click.echo(f"\n📡 Host: {host_entry.name} [{status_mark}] ({host_url_local})")
        click.echo("=" * 80)

        for entity_uid, name in entities:
            encoded_local = quote(host_url_local)
            encoded_public = quote(host_url_public)

            local_url = f"{ui_base_local}/?entity_uid={entity_uid}&host_url={encoded_local}"
            public_url = f"{ui_base_public}/?entity_uid={entity_uid}&host_url={encoded_public}"

            click.echo(f"\n👤 {name}")
            click.echo(f"   Entity UID: {entity_uid}")
            click.echo(f"   🔗 Local URL: {local_url}")
            if local_ip != "localhost":
                click.echo(f"   🌐 Public URL: {public_url}")
            click.echo("   📱 QR Code:")
            for line in generate_qr_lines(public_url):
                click.echo(f"      {line}")

    click.echo("\n" + "=" * 80)
    total = sum(len(e) for e in humans_by_host.values())
    click.echo(f"Total human entities: {total}")


@click.group(
    name="ui",
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.pass_context
def command(ctx: click.Context) -> None:
    """Manage web UI."""
    if ctx.invoked_subcommand is not None:
        return

    # 默认行为：显示状态
    status = _get_ui_status()

    if status:
        click.echo(f"✓ UI is running on port {status['port']} (PID: {status['pid']})")
        click.echo(f"  Local URL: http://localhost:{status['port']}")

        local_ip = get_local_ip()
        if local_ip != "localhost":
            click.echo(f"  Public URL: http://{local_ip}:{status['port']}")

        _show_all_hosts_entities(status["port"])
    else:
        click.echo("✗ UI is not running")
        click.echo("  Run 'aln ui start' to start the UI")


def _update_dependencies(web_dir: Path) -> bool:
    """更新所有依赖"""
    click.echo("Updating UI dependencies...")
    try:
        subprocess.run(
            ["npm", "update"],
            cwd=str(web_dir),
            check=True,
        )
        click.echo("✓ Dependencies updated")
        return True
    except subprocess.CalledProcessError:
        click.echo("✗ Failed to update dependencies")
        return False


def _start_ui_server(port: int, config_dir: Path, web_dir: Path) -> None:
    """启动 UI 服务器（dev 模式）"""
    pid_file = config_dir / "ui.pid"

    cmd = f"nohup npm run dev -- --port {port} --host 0.0.0.0 </dev/null >/dev/null 2>&1 & echo $!"

    result = subprocess.run(
        cmd,
        shell=True,
        cwd=str(web_dir),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to start process: {result.stderr}")

    pid = int(result.stdout.strip())

    pid_file.write_text(str(pid))
    port_file = config_dir / "ui.port"
    port_file.write_text(str(port))

    local_ip = get_local_ip()

    click.echo(f"✓ UI started on port {port} (PID: {pid})")
    click.echo(f"  Local URL: http://localhost:{port}")
    if local_ip != "localhost":
        click.echo(f"  Public URL: http://{local_ip}:{port}")


def _ensure_dependencies(web_dir: Path, quiet: bool = False) -> bool:
    """Run npm install (idempotent — fast when deps are current)."""
    try:
        kwargs: dict = {"cwd": str(web_dir), "check": True}
        if quiet:
            kwargs.update(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["npm", "install"], **kwargs)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


class UiStartError(Exception):
    """UI 启动错误"""


class UiStopError(Exception):
    """UI 停止错误"""


def start_ui(port: int) -> int:
    """启动 UI 服务，返回启动的 PID。已在运行或启动失败时抛出异常。"""
    status = _get_ui_status()
    if status:
        raise UiStartError(
            f"UI is already running on port {status['port']} (PID: {status['pid']})"
        )

    config_dir = Path(get_fp_home())
    config_dir.mkdir(parents=True, exist_ok=True)

    web_dir = Path(__file__).parent.parent / "web"
    if not web_dir.exists():
        raise UiStartError(f"Web directory not found: {web_dir}")

    # 确保依赖完整
    click.echo("Checking UI dependencies...")
    if not _ensure_dependencies(web_dir):
        raise UiStartError("Failed to install dependencies")

    try:
        _start_ui_server(port, config_dir, web_dir)
    except FileNotFoundError:
        raise UiStartError("npm not found. Please install Node.js and npm first.")
    except Exception as e:
        click.echo(f"✗ Failed to start UI: {e}")
        click.echo("\nRetrying with dependency update...")

        if not _update_dependencies(web_dir):
            raise UiStartError("Failed to update dependencies")
        try:
            _start_ui_server(port, config_dir, web_dir)
        except Exception as retry_error:
            raise UiStartError(f"Failed after updating dependencies: {retry_error}")

    new_status = _get_ui_status()
    return new_status["pid"] if new_status else 0


@command.command("start", help="Start web UI.")
@click.option("--port", type=int, default=5173, show_default=True, help="UI port")
def start_subcommand(port: int) -> None:
    """Start web UI server."""
    try:
        start_ui(port)
    except UiStartError as e:
        click.echo(f"✗ {e}")
        sys.exit(1)


def stop_ui() -> int:
    """停止 UI 服务，返回被停止的 PID。未运行或停止失败时抛出异常。"""
    config_dir = Path(get_fp_home())
    pid_file = config_dir / "ui.pid"
    port_file = config_dir / "ui.port"

    status = _get_ui_status()
    if not status:
        raise UiStopError("UI is not running")

    pid = status["pid"]
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        pid_file.unlink()
        port_file.unlink(missing_ok=True)
        return pid
    except (OSError, ValueError, ProcessLookupError) as e:
        pid_file.unlink(missing_ok=True)
        port_file.unlink(missing_ok=True)
        raise UiStopError(f"Failed to stop UI: {e}")


@command.command("stop", help="Stop web UI.")
def stop_subcommand() -> None:
    """Stop web UI server."""
    try:
        pid = stop_ui()
        click.echo(f"✓ UI stopped (PID: {pid})")
    except UiStopError as e:
        click.echo(f"✗ {e}")
        sys.exit(1)


def ensure_ui_running(port: int = 5173) -> None:
    """确保 UI 正在运行，如果没有则启动（用于其他命令调用）"""
    status = _get_ui_status()
    if status:
        return

    config_dir = Path(get_fp_home())
    config_dir.mkdir(parents=True, exist_ok=True)
    pid_file = config_dir / "ui.pid"

    web_dir = Path(__file__).parent.parent / "web"
    if not web_dir.exists():
        return

    click.echo("Installing UI dependencies (npm install)...")
    if not _ensure_dependencies(web_dir, quiet=True):
        click.echo("✗ Failed to install UI dependencies")
        return
    click.echo("✓ UI dependencies ready")

    try:
        cmd = f"nohup npm run dev -- --port {port} --host 0.0.0.0 </dev/null >/dev/null 2>&1 & echo $!"

        result = subprocess.run(
            cmd,
            shell=True,
            cwd=str(web_dir),
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            pid = int(result.stdout.strip())
            pid_file.write_text(str(pid))
            port_file = config_dir / "ui.port"
            port_file.write_text(str(port))
            click.echo(f"✓ UI auto-started on port {port}")
    except Exception:
        pass
