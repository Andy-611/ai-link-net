"""`aln host` command group."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import click
from click.core import ParameterSource
from fp.utils.storage import StorageManager, get_storage_manager

from aln.app import HostClient
from aln.app.schemas import HostUpdateRequest

from .misc.clistyle import HostCLIStyle
from .misc.common import _has_uv
from .misc.printer import CliPrinter
from .misc.process import is_pid_alive, is_port_open, stop_pid
from .misc.wrappers import cli_exception_wrapper, get_cli_printer, get_host_client, get_storage


def find_available_port(start_port: int = 7001, max_attempts: int = 100) -> int:
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("0.0.0.0", port))
                return port
        except OSError:
            continue
    raise RuntimeError(
        f"No available port found in range {start_port}-{start_port + max_attempts}"
    )


@click.group(
    name="host",
    cls=HostCLIStyle,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.pass_context
def command(ctx: click.Context) -> None:
    """Run `aln host COMMAND --help` for details on each command."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@command.command("new", help="Create/update one host profile and start it.")
@click.option(
    "-n",
    "--name",
    "host_name",
    default="default",
    show_default=True,
    help="Host name",
)
@click.option(
    "--bind-host", default="0.0.0.0", show_default=True, help="Host bind address."
)
@click.option(
    "--advertise-host",
    default=None,
    help="Address advertised to other hosts (default: auto-infer from bind-host).",
)
@click.option(
    "--port",
    "-p",
    type=int,
    default=None,
    help="Host bind port (auto-detect if not specified).",
)
@click.option(
    "--parent",
    "parent_url",
    default=None,
    help="Parent host URL (e.g., http://172.31.0.5:7001)",
)
@click.pass_context
@cli_exception_wrapper(error_message="Failed to create host")
@get_storage
@get_cli_printer
def new_command(
    ctx: click.Context,
    host_name: str,
    bind_host: str,
    advertise_host: str | None,
    port: int | None,
    parent_url: str | None,
    storage: StorageManager,
    cli_printer: CliPrinter,
) -> None:
    """Initialize one host profile and start host server process."""
    host_entry = None
    try:
        host_entry = storage.get_host(host_name)
    except Exception as e:
        # If config is corrupted, delete it and start fresh
        if "validation error" in str(e).lower():
            config_path = storage._config_path()
            if config_path.exists():
                config_path.unlink()
                cli_printer.echo("Detected corrupted config, recreating...")
        pass

    host_name_source = ctx.get_parameter_source("host_name")
    bind_host_source = ctx.get_parameter_source("bind_host")
    port_source = ctx.get_parameter_source("port")

    is_default_init_call = (
        host_name == "default"
        and host_name_source == ParameterSource.DEFAULT
        and bind_host_source == ParameterSource.DEFAULT
        and port_source == ParameterSource.DEFAULT
        and host_entry is not None
    )
    if is_default_init_call:
        _start_host(host_name, storage, cli_printer)
        return

    effective_bind_host = bind_host
    if bind_host_source == ParameterSource.DEFAULT and host_entry:
        effective_bind_host = host_entry.bind_host

    advertise_host_source = ctx.get_parameter_source("advertise_host")
    effective_advertise_host = advertise_host
    if advertise_host_source == ParameterSource.DEFAULT and host_entry:
        effective_advertise_host = host_entry.advertise_host

    effective_port = port
    if effective_port is None:
        if host_entry:
            effective_port = host_entry.port
        else:
            effective_port = find_available_port()

    existing_pid = storage.get_host_pid(host_name)
    if existing_pid and is_pid_alive(existing_pid):
        has_config_change = (
            host_entry and (
                host_entry.bind_host != effective_bind_host
                or host_entry.port != effective_port
            )
        )
        if has_config_change:
            raise click.ClickException(
                f"Host '{host_name}' is running (PID: {existing_pid}). "
                "Stop it before changing bind_host/port."
            )

    # Create or update host config
    url = f"http://{effective_bind_host}:{effective_port}"

    # Generate address if this is a new host
    from fp import FPAddress
    address = None
    if host_entry and host_entry.address:
        address = host_entry.address
    else:
        address = FPAddress.create().address

    storage.create_or_update_host(
        host_name=host_name,
        bind_host=effective_bind_host,
        advertise_host=effective_advertise_host,
        port=effective_port,
        url=url,
        address=address,
        parent_url=parent_url,
    )

    cli_printer.echo(
        f"Host '{host_name}' initialized at {effective_bind_host}:{effective_port}"
    )
    cli_printer.echo(f"Config saved to: {storage._config_path()}")

    # Start the host
    _start_host(host_name, storage, cli_printer)

    # Set parent via API only if user explicitly passed --parent
    if parent_url:
        _auto_set_parent_if_needed(host_name, storage, cli_printer, parent_url)


@command.command(
    "set",
    help="Update host configuration, including Parent host via --parent URL.",
)
@click.option(
    "--host",
    "host_name",
    default="default",
    help="Host name to configure (default: default)",
)
@click.option(
    "--parent",
    "parent_url",
    help="Parent host URL, must start with http:// or https://.",
)
@click.option("--bind-host", help="Set bind_host on current host server config.")
@click.option(
    "--port", "-p", type=int, help="Set bind port on current host server config."
)
@click.option(
    "--default", "set_default", is_flag=True, help="Set this host as default host."
)
@cli_exception_wrapper(error_message="Failed to set host config")
@get_storage
@get_cli_printer
@get_host_client
def set_command(
    host_name: str,
    parent_url: str | None,
    bind_host: str | None,
    port: int | None,
    set_default: bool,
    storage: StorageManager,
    cli_printer: CliPrinter,
    host_client: HostClient,
) -> None:
    """Update host configuration."""
    if not any([parent_url, bind_host, port, set_default]):
        lines = """
No options provided. Use --help to see available options:

  --parent URL       Set parent host URL
  --bind-host HOST   Set bind host address
  --port PORT        Set bind port
  --default          Set as default host
        """
        cli_printer.print_lines(lines)
        return

    update_request = HostUpdateRequest(
        host_name=host_name,
        parent_url=parent_url,
        bind_host=bind_host,
        port=port,
        set_default=set_default,
    )
    response = host_client.host_update(update_request)
    cli_printer.print(response)

    # NOTE: API端已经保存配置，CLI端不需要重复保存，避免并发写入问题
    # 只有 set_default 需要在本地保存（API不支持）
    if set_default:
        storage.set_default_host(host_name)


@command.command("start", help="Start host server process.")
@click.option(
    "--host",
    "host_name",
    default=None,
    help="Host name to start (default: all hosts)",
)
@cli_exception_wrapper(error_message="Failed to start host")
@get_storage
@get_cli_printer
def start_command(
    host_name: str | None,
    storage: StorageManager,
    cli_printer: CliPrinter,
) -> None:
    """Start host server process."""
    _start_host(host_name, storage, cli_printer)


@command.command("stop", help="Stop host server process.")
@click.option(
    "--host",
    "host_name",
    default=None,
    help="Host name to stop (default: all hosts)",
)
@cli_exception_wrapper(error_message="Failed to stop host")
@get_storage
@get_cli_printer
def stop_command(
    host_name: str | None, storage: StorageManager, cli_printer: CliPrinter
) -> None:
    """Stop host server process."""
    _stop_host(host_name, storage, cli_printer)


@command.command("reset", help="Reset host server process (stop then start).")
@click.option(
    "--host",
    "host_name",
    default=None,
    help="Host name to reset (default: all hosts)",
)
@cli_exception_wrapper(error_message="Failed to reset host")
@get_storage
@get_cli_printer
def reset_command(
    host_name: str | None, storage: StorageManager, cli_printer: CliPrinter
) -> None:
    """Reset host server process."""
    _stop_host(host_name, storage, cli_printer)
    _start_host(host_name, storage, cli_printer)




@command.command("list", help="List configured hosts and local runtime status.")
@cli_exception_wrapper(error_message="Failed to list hosts")
@get_storage
@get_cli_printer
def list_command(storage: StorageManager, cli_printer: CliPrinter) -> None:
    """Print all host records from local config."""
    hosts = storage.get_all_hosts()
    default_host_uid = storage.get_default_host()

    if not hosts:
        cli_printer.echo("No hosts configured")
        return

    cli_printer.echo(f"Default host: {default_host_uid}")
    cli_printer.echo("")
    cli_printer.echo("Configured hosts:")

    for uid, host_entry in hosts.items():
        url = host_entry.get_url()
        pid = storage.get_host_pid(uid)
        status = "running" if (pid and is_pid_alive(pid)) else "stopped"

        marker = "*" if uid == default_host_uid else " "
        cli_printer.echo(f"{marker} {host_entry.name} ({uid[:8]})")
        cli_printer.echo(f"    URL:    {url}")
        cli_printer.echo(f"    Status: {status}")
        if pid:
            cli_printer.echo(f"    PID:    {pid}")
        cli_printer.echo("")


def _auto_set_parent_if_needed(
    host_name: str,
    storage: StorageManager,
    cli_printer: CliPrinter,
    parent_url: str,
) -> None:
    """Set explicit parent on a running host."""
    time.sleep(0.5)
    try:
        host_url = storage.get_host_url(host_name)
        client = HostClient(base_url=host_url, timeout=5.0)
        client.host_update(HostUpdateRequest(host_name=host_name, parent_url=parent_url))
        cli_printer.echo(f"Parent host configured: {parent_url}")
    except Exception as e:
        cli_printer.echo(f"Warning: Failed to configure parent: {e}")
        cli_printer.echo(f"You can manually set it later with: aln host set --parent {parent_url}")


def _resolve_target_hosts(host_name: str | None, storage: StorageManager) -> list[str]:
    """Resolve target hosts from CLI argument.

    - host_name is None or "all": all configured hosts
    - host_name is specific: that host only

    Returns list of host UIDs.
    """
    hosts = storage.get_all_hosts()
    if host_name is None or host_name == "all":
        return list(hosts.keys())

    resolved_uid = storage.resolve_host_name(host_name)
    return [resolved_uid]


def _probe_host(bind_host: str) -> str:
    """Resolve bind host to a probe-friendly local address."""
    if bind_host in {"0.0.0.0", "::"}:
        return "127.0.0.1"
    return bind_host


def _wait_host_ready(
    process: subprocess.Popen[bytes],
    bind_host: str,
    port: int,
    timeout_seconds: float = 8.0,
) -> bool:
    """Wait until host process is alive and TCP port is reachable."""
    probe_host = _probe_host(bind_host)
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if process.poll() is not None:
            return False
        if is_port_open(probe_host, port):
            return True
        time.sleep(0.1)
    return process.poll() is None and is_port_open(probe_host, port)


def _start_host(
    host_name: str | None,
    storage: StorageManager,
    cli_printer: CliPrinter,
) -> None:
    """Start host server process for one or all hosts."""
    target_host_uids = _resolve_target_hosts(host_name, storage)
    if not target_host_uids:
        cli_printer.echo("No hosts configured")
        return

    has_error = False

    for uid in target_host_uids:
        host_entry = storage.get_host(uid)
        bind_host = host_entry.bind_host
        port = host_entry.port

        pid = storage.get_host_pid(uid)
        if pid and is_pid_alive(pid):
            cli_printer.echo(f"Host '{host_entry.name}' is already running (PID: {pid})")
            continue

        # Start uvicorn process with hot reload
        cmd = [
            "uv" if _has_uv() else sys.executable,
            "run" if _has_uv() else "-m",
            "uvicorn",
            "aln.app.main:app",
            "--host",
            bind_host,
            "--port",
            str(port),
            "--reload",
        ]

        # Get project root (src parent directory)
        project_root = Path(__file__).parent.parent.parent

        try:
            process_env = os.environ.copy()
            process_env["FP_HOST_NAME"] = host_entry.name
            process = subprocess.Popen(
                cmd,
                cwd=str(project_root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env=process_env,
            )

            new_pid = process.pid
            storage.set_host_pid(uid, new_pid)
            if _wait_host_ready(process, bind_host, port):
                cli_printer.echo(f"Host '{host_entry.name}' started (PID: {new_pid})")
                cli_printer.echo(f"URL: http://{bind_host}:{port}")
                continue

            has_error = True
            storage.delete_host_pid(uid)
            cli_printer.echo(
                f"Failed to start host '{host_entry.name}': process exited before becoming ready"
            )
            cli_printer.echo(
                f"Tip: check logs with `aln host log --host {host_entry.name} -n 80`"
            )
        except Exception as e:
            has_error = True
            cli_printer.echo(f"Failed to start host '{host_entry.name}': {e}")

    if has_error:
        sys.exit(1)


def _stop_host(
    host_name: str | None, storage: StorageManager, cli_printer: CliPrinter
) -> None:
    """Stop host server process for one or all hosts."""
    target_host_uids = _resolve_target_hosts(host_name, storage)
    if not target_host_uids:
        cli_printer.echo("No hosts configured")
        return

    has_error = False
    for uid in target_host_uids:
        host_entry = storage.get_host(uid)
        pid = storage.get_host_pid(uid)
        if not pid or not is_pid_alive(pid):
            cli_printer.echo(f"Host '{host_entry.name}' is not running")
            if pid:
                storage.delete_host_pid(uid)
            continue

        if stop_pid(pid):
            cli_printer.echo(f"Host '{host_entry.name}' stopped (PID: {pid})")
            storage.delete_host_pid(uid)
        else:
            has_error = True
            cli_printer.echo(f"Failed to stop host '{host_entry.name}' (PID: {pid})")

    if has_error:
        sys.exit(1)


@command.command("restart", help="Alias of 'aln host reset'.")
@click.option(
    "--host",
    "host_name",
    default=None,
    help="Host name to restart (default: all hosts)",
)
@cli_exception_wrapper(error_message="Failed to restart host")
@get_storage
@get_cli_printer
def restart_command(
    host_name: str | None, storage: StorageManager, cli_printer: CliPrinter
) -> None:
    """Backward-compatible alias for reset."""
    _stop_host(host_name, storage, cli_printer)
    _start_host(host_name, storage, cli_printer)


@command.command("delete", help="Delete a host and all its entities.")
@click.option(
    "--host",
    "host_name",
    required=True,
    help="Host name or uid to delete",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
@cli_exception_wrapper(error_message="Failed to delete host")
@get_storage
@get_cli_printer
def delete_command(
    host_name: str,
    yes: bool,
    storage: StorageManager,
    cli_printer: CliPrinter,
) -> None:
    """Delete a host and all its entities."""
    _delete_host(host_name, storage, cli_printer, confirm=not yes)


def _delete_host(
    host_name: str,
    storage: StorageManager,
    cli_printer: CliPrinter,
    confirm: bool = True,
) -> None:
    """删除指定host及其所有entities."""
    try:
        host_uid = storage.resolve_host_name(host_name)
    except ValueError:
        cli_printer.echo(f"Host not found: {host_name}")
        return

    host_entry = storage.get_host(host_uid)

    # 获取该host下的所有entities
    entity_uids = storage.get_entities_for_host(host_uid)

    if confirm:
        cli_printer.echo(f"This will delete host '{host_entry.name}' ({host_uid[:8]})")
        cli_printer.echo(f"  - {len(entity_uids)} entities will be deleted")
        cli_printer.echo("This action CANNOT be undone!")
        if not click.confirm("Are you sure?"):
            cli_printer.echo("Aborted.")
            return

    # 1. 通知 parent 注销 child
    if host_entry.parent_url:
        try:
            parent_client = HostClient(base_url=host_entry.parent_url, timeout=5.0)
            parent_client.unregister_child(host_uid)
            cli_printer.echo(f"  ✓ Unregistered from parent")
        except Exception as e:
            cli_printer.echo(f"  ⚠ Failed to unregister from parent: {e}")

    # 2. 如果host正在运行，先通过API删除entities
    pid = storage.get_host_pid(host_uid)
    if pid and is_pid_alive(pid):
        cli_printer.echo("Host is running, deleting entities via API...")
        host_url = storage.get_host_url(host_uid)
        client = HostClient(base_url=host_url, timeout=5.0)

        for entity_uid in entity_uids:
            try:
                client.entity_delete(entity_uid)
                cli_printer.echo(f"  ✓ Deleted entity {entity_uid[:8]}")
            except Exception as e:
                cli_printer.echo(f"  ⚠ Failed to delete entity {entity_uid[:8]}: {e}")

        # 3. 停止host进程
        cli_printer.echo("Stopping host...")
        if stop_pid(pid):
            cli_printer.echo(f"✓ Host stopped (PID: {pid})")
        else:
            cli_printer.echo(f"⚠ Failed to stop host (PID: {pid})")
    else:
        cli_printer.echo("Host is not running, deleting data directly...")

    # 4. 从配置和文件系统中删除host
    cli_printer.echo("Deleting host configuration and data...")
    storage.delete_host_from_config(host_uid)

    cli_printer.echo(f"✓ Host '{host_entry.name}' deleted successfully")


@command.command("detail", help="Show comprehensive status for one host.")
@click.option(
    "--host",
    "host_name",
    default="default",
    help="Host name or host uid to inspect (default: default)",
)
@cli_exception_wrapper(error_message="Failed to show host detail")
@get_storage
@get_cli_printer
def detail_command(
    host_name: str,
    storage: StorageManager,
    cli_printer: CliPrinter,
) -> None:
    """Show comprehensive status of one host."""
    from .misc.process import is_pid_alive

    hosts = storage.get_all_hosts()
    default_host_uid = storage.get_default_host()

    if not hosts:
        cli_printer.echo("No hosts configured")
        return

    try:
        resolved_uid = storage.resolve_host_name(host_name)
    except Exception:
        cli_printer.echo(f"Host not found: {host_name}")
        available_hosts = [f"{entry.name} ({uid[:8]})" for uid, entry in hosts.items()]
        cli_printer.echo(f"Available hosts: {', '.join(available_hosts)}")
        return

    host_entry = hosts[resolved_uid]
    pid = storage.get_host_pid(resolved_uid)
    is_running = pid and is_pid_alive(pid)

    cli_printer.echo(
        f"Host: {host_entry.name}"
        + (" (default)" if resolved_uid == default_host_uid else "")
    )
    cli_printer.echo(f"  UID:        {resolved_uid}")
    cli_printer.echo(f"  Status:     {'Running' if is_running else 'Stopped'}")
    cli_printer.echo(f"  URL:        {host_entry.url or 'N/A'}")
    cli_printer.echo(f"  Bind:       {host_entry.bind_host}:{host_entry.port}")
    if pid:
        cli_printer.echo(f"  PID:        {pid}")
    if host_entry.parent_url:
        cli_printer.echo(f"  Parent URL: {host_entry.parent_url}")

    # Show state info if exists
    state_path = storage.get_host_state_path(resolved_uid)
    if state_path.exists():
        import json
        try:
            with open(state_path) as f:
                state = json.load(f)
            entity_count = len(state.get('entities', {}))
            child_count = len(state.get('child_hosts', {}))
            cli_printer.echo(f"  Entities:   {entity_count}")
            cli_printer.echo(f"  Children:   {child_count}")
        except Exception:
            pass

    # Try to get live status and wellknown from API if running
    if is_running:
        try:
            from aln.app.service import HostClient

            client = HostClient(host_entry.url or f"http://{host_entry.bind_host}:{host_entry.port}", timeout=2.0)
            health = client.check_health()
            cli_printer.echo(f"  Health:     {'✓ OK' if health.ok else '✗ Error'}")

            # Fetch and display wellknown
            cli_printer.echo("")
            cli_printer.echo("Well-Known:")
            wellknown = client.get_wellknown()
            cli_printer.print(wellknown)

            # Display entities on this host (local only)
            cli_printer.echo("")
            cli_printer.echo("Entities on this host:")
            try:
                entities = client.entity_list()
                if entities:
                    for entity in entities:
                        entity_uid = entity.entity_uid
                        entity_name = entity.name
                        entity_kind = entity.kind
                        is_public = "public" if entity.is_public else "private"
                        cli_printer.echo(f"  • {entity_name} ({entity_kind}, {is_public})")
                        cli_printer.echo(f"    UID: {entity_uid}")
                else:
                    cli_printer.echo("  No entities registered")
            except Exception as e:
                cli_printer.echo(f"  Failed to fetch entities: {e}")
        except Exception:
            cli_printer.echo("  Health:     Unable to connect")


@command.command("log", help="Display host logs.")
@click.option(
    "--host",
    "host_name",
    default="default",
    help="Host name to show logs for (default: default)",
)
@click.option(
    "-f",
    "--follow",
    "follow",
    is_flag=True,
    help="Follow log output in real-time (like tail -f)",
)
@click.option(
    "-n",
    "--lines",
    type=int,
    default=50,
    help="Number of lines to show (default: 50)",
)
@click.option(
    "--since",
    help="Show logs since timestamp (e.g., '2024-01-01 10:00:00')",
)
@click.option(
    "--until",
    help="Show logs until timestamp (e.g., '2024-01-01 12:00:00')",
)
@cli_exception_wrapper(error_message="Failed to show host logs")
@get_storage
@get_cli_printer
def log_command(
    host_name: str,
    follow: bool,
    lines: int,
    since: str | None,
    until: str | None,
    storage: StorageManager,
    cli_printer: CliPrinter,
) -> None:
    """Display host logs with optional filtering and follow mode."""
    import subprocess
    from datetime import datetime

    log_path = storage.get_host_log_path(host_name)

    if not log_path.exists():
        cli_printer.echo(f"No log file found for host '{host_name}'")
        cli_printer.echo(f"Expected path: {log_path}")
        return

    if follow:
        # Real-time follow mode
        cli_printer.echo(f"Following logs for host '{host_name}' (Ctrl+C to stop)...")
        cli_printer.echo(f"Log file: {log_path}")
        cli_printer.echo("")

        try:
            cmd = ["tail", "-f", "-n", str(lines), str(log_path)]
            subprocess.run(cmd)
        except KeyboardInterrupt:
            cli_printer.echo("\nStopped following logs")
    else:
        # Static display mode
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                log_lines = f.readlines()

            # Filter by time range if specified
            if since or until:
                filtered_lines = []
                since_dt = datetime.fromisoformat(since) if since else None
                until_dt = datetime.fromisoformat(until) if until else None

                for line in log_lines:
                    # Parse timestamp from log line
                    # Format: "2024-01-01 10:00:00 | INFO | ..."
                    try:
                        timestamp_str = line.split(" | ")[0].strip()
                        log_dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

                        if since_dt and log_dt < since_dt:
                            continue
                        if until_dt and log_dt > until_dt:
                            continue

                        filtered_lines.append(line)
                    except (ValueError, IndexError):
                        # If timestamp parsing fails, include the line
                        filtered_lines.append(line)

                log_lines = filtered_lines

            # Show last N lines
            display_lines = log_lines[-lines:] if len(log_lines) > lines else log_lines

            cli_printer.echo(f"Showing last {len(display_lines)} lines from host '{host_name}':")
            cli_printer.echo(f"Log file: {log_path}")
            cli_printer.echo("")

            for line in display_lines:
                cli_printer.echo(line.rstrip())

        except Exception as e:
            cli_printer.echo(f"Failed to read log file: {e}")
