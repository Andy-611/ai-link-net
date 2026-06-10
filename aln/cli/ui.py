"""`aln ui` command group."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

import click

from aln.web_server import get_web_root
from fp import get_fp_home
from fp.utils.storage import get_storage_manager

from .misc.common import generate_qr_lines, get_local_ip
from .misc.process import is_pid_alive, is_port_open


def _get_ui_status() -> dict | None:
    """Return the running UI process status."""
    config_dir = Path(get_fp_home())
    pid_file = config_dir / "ui.pid"
    port_file = config_dir / "ui.port"

    if not pid_file.exists():
        return None

    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)
        port = int(port_file.read_text().strip()) if port_file.exists() else 5173
        return {"pid": pid, "port": port}
    except (OSError, ValueError, ProcessLookupError):
        pid_file.unlink(missing_ok=True)
        port_file.unlink(missing_ok=True)
        return None


def _show_all_hosts_entities(ui_port: int) -> None:
    """Show enabled human entities and their UI links."""
    storage = get_storage_manager()
    config = storage.load_config()

    humans_by_host: dict[str, list[tuple[str, str]]] = {}
    for entity_uid, entity_entry in config.entities.items():
        if entity_entry.kind == "human" and entity_entry.enabled:
            humans_by_host.setdefault(entity_entry.host_uid, []).append(
                (entity_uid, entity_entry.name)
            )

    if not humans_by_host:
        click.echo("\nNo human entities found")
        return

    local_ip = get_local_ip()
    ui_base_local = f"http://localhost:{ui_port}"
    ui_base_public = f"http://{local_ip}:{ui_port}"

    for host_uid, entities in humans_by_host.items():
        host_entry = config.hosts.get(host_uid)
        if not host_entry or not host_entry.enabled:
            continue

        bind_host_local = (
            "127.0.0.1"
            if host_entry.bind_host == "0.0.0.0"
            else host_entry.bind_host
        )
        host_url_local = f"http://{bind_host_local}:{host_entry.port}"
        host_url_public = f"http://{local_ip}:{host_entry.port}"

        pid = storage.get_host_pid(host_uid)
        status_mark = "online" if pid is not None and is_pid_alive(pid) else "offline"
        click.echo(f"\nHost: {host_entry.name} [{status_mark}] ({host_url_local})")
        click.echo("=" * 80)

        for entity_uid, name in entities:
            encoded_local = quote(host_url_local)
            encoded_public = quote(host_url_public)
            local_url = (
                f"{ui_base_local}/?entity_uid={entity_uid}&host_url={encoded_local}"
            )
            public_url = (
                f"{ui_base_public}/?entity_uid={entity_uid}&host_url={encoded_public}"
            )

            click.echo(f"\n{name}")
            click.echo(f"   Entity UID: {entity_uid}")
            click.echo(f"   Local URL: {local_url}")
            if local_ip != "localhost":
                click.echo(f"   Public URL: {public_url}")
            click.echo("   QR Code:")
            for line in generate_qr_lines(public_url):
                click.echo(f"      {line}")

    click.echo("\n" + "=" * 80)
    click.echo(f"Total human entities: {sum(map(len, humans_by_host.values()))}")


@click.group(
    name="ui",
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.pass_context
def command(ctx: click.Context) -> None:
    """Manage the packaged Web UI."""
    if ctx.invoked_subcommand is not None:
        return

    status = _get_ui_status()
    if status:
        click.echo(
            f"UI is running on port {status['port']} (PID: {status['pid']})"
        )
        click.echo(f"  Local URL: http://localhost:{status['port']}")
        local_ip = get_local_ip()
        if local_ip != "localhost":
            click.echo(f"  Public URL: http://{local_ip}:{status['port']}")
        _show_all_hosts_entities(status["port"])
    else:
        click.echo("UI is not running")
        click.echo("  Run `aln ui start` to start the UI")


class UiStartError(Exception):
    """Raised when the packaged UI cannot be started."""


class UiStopError(Exception):
    """Raised when the packaged UI cannot be stopped."""


def _spawn_ui_process(port: int, log_path: Path) -> subprocess.Popen:
    """Start the packaged Web server in a detached process."""
    command_line = [
        sys.executable,
        "-m",
        "aln.web_server",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
    ]
    popen_kwargs: dict[str, object] = {
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        popen_kwargs["start_new_session"] = True

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log_file:
        return subprocess.Popen(
            command_line,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            **popen_kwargs,
        )


def _wait_until_ready(process: subprocess.Popen, port: int) -> bool:
    """Wait briefly for the UI process to bind its port."""
    for _ in range(30):
        if process.poll() is not None:
            return False
        if is_port_open("127.0.0.1", port, timeout=0.1):
            return True
        time.sleep(0.1)
    return False


def start_ui(port: int) -> int:
    """Start the packaged UI server and return its PID."""
    status = _get_ui_status()
    if status:
        raise UiStartError(
            f"UI is already running on port {status['port']} (PID: {status['pid']})"
        )

    web_root = get_web_root()
    if not (web_root / "index.html").is_file():
        raise UiStartError(
            f"Packaged Web UI not found at {web_root}. "
            "Install an official release or run `npm run build` in aln/web."
        )

    config_dir = Path(get_fp_home())
    config_dir.mkdir(parents=True, exist_ok=True)
    process = _spawn_ui_process(port, config_dir / "logs" / "ui.log")
    if not _wait_until_ready(process, port):
        process.terminate()
        raise UiStartError(
            f"UI process failed to start. See {config_dir / 'logs' / 'ui.log'}"
        )

    (config_dir / "ui.pid").write_text(str(process.pid), encoding="utf-8")
    (config_dir / "ui.port").write_text(str(port), encoding="utf-8")

    local_ip = get_local_ip()
    click.echo(f"UI started on port {port} (PID: {process.pid})")
    click.echo(f"  Local URL: http://localhost:{port}")
    if local_ip != "localhost":
        click.echo(f"  Public URL: http://{local_ip}:{port}")
    return process.pid


@command.command("start", help="Start web UI.")
@click.option("--port", type=int, default=5173, show_default=True, help="UI port")
def start_subcommand(port: int) -> None:
    """Start the packaged Web UI."""
    try:
        start_ui(port)
    except UiStartError as error:
        raise click.ClickException(str(error)) from error


def stop_ui() -> int:
    """Stop the UI server and return its PID."""
    config_dir = Path(get_fp_home())
    pid_file = config_dir / "ui.pid"
    port_file = config_dir / "ui.port"
    status = _get_ui_status()
    if not status:
        raise UiStopError("UI is not running")

    pid = status["pid"]
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise OSError(result.stderr.strip() or "taskkill failed")
        else:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (OSError, ValueError, ProcessLookupError) as error:
        raise UiStopError(f"Failed to stop UI: {error}") from error
    finally:
        pid_file.unlink(missing_ok=True)
        port_file.unlink(missing_ok=True)
    return pid


@command.command("stop", help="Stop web UI.")
def stop_subcommand() -> None:
    """Stop the packaged Web UI."""
    try:
        pid = stop_ui()
    except UiStopError as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"UI stopped (PID: {pid})")


def ensure_ui_running(port: int = 5173) -> None:
    """Start the UI when it is not already running."""
    if _get_ui_status():
        return
    try:
        start_ui(port)
    except UiStartError as error:
        click.echo(f"Failed to start UI: {error}", err=True)
