"""`aln update` command."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import click
from fp import get_fp_home
from fp.utils.storage import StorageManager

from .host import _start_host, _stop_host
from .misc.printer import CliPrinter
from .misc.wrappers import cli_exception_wrapper, get_cli_printer, get_storage
from .ui import UiStartError, UiStopError, _get_ui_status, start_ui, stop_ui
from .update_check import UpdateCheckResult, check_for_update


class SourceUpdateWorkflow:
    """Update a development checkout and restart its local services."""

    def __init__(
        self,
        storage: StorageManager,
        cli_printer: CliPrinter,
        repo_root: Path,
        ui_port: int,
    ) -> None:
        self._storage = storage
        self._cli_printer = cli_printer
        self._repo_root = repo_root
        self._ui_port = ui_port
        self._errors: list[str] = []
        self._ui_was_running = False

    def run(self) -> None:
        """Execute the source-checkout update flow."""
        self._ui_was_running = _get_ui_status() is not None

        self._cli_printer.echo("Stopping hosts...")
        self._run_host_stop()

        if self._ui_was_running:
            self._cli_printer.echo("Stopping UI...")
            self._run_ui_stop()

        self._cli_printer.echo(f"Pulling latest code in: {self._repo_root}")
        self._run_git_pull()

        if not self._errors:
            self._cli_printer.echo("Building Web UI...")
            self._run_web_build()

        if not self._errors:
            self._cli_printer.echo("Reinstalling aln tool...")
            self._run_tool_install()

        self._cli_printer.echo("Starting hosts...")
        self._run_host_start()

        if self._ui_was_running:
            self._cli_printer.echo("Starting UI...")
            self._run_ui_start()

        if self._errors:
            raise click.ClickException(f"Update failed: {'; '.join(self._errors)}")

        self._cli_printer.echo("Update completed")

    def _run_git_pull(self) -> None:
        result = subprocess.run(
            ["git", "pull"],
            cwd=self._repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else "unknown error"
            self._errors.append(f"git pull failed: {stderr}")
        elif result.stdout.strip():
            self._cli_printer.echo(result.stdout.strip())

    def _run_tool_install(self) -> None:
        result = subprocess.run(
            ["uv", "tool", "install", "-e", ".", "--force"],
            cwd=self._repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else "unknown error"
            self._errors.append(f"uv tool install failed: {stderr}")

    def _run_web_build(self) -> None:
        web_dir = self._repo_root / "aln" / "web"
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        if npm is None:
            self._errors.append("Web build failed: npm is not installed")
            return

        for command in ([npm, "ci"], [npm, "run", "build"]):
            result = subprocess.run(
                command,
                cwd=web_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip() if result.stderr else "unknown error"
                self._errors.append(f"Web build failed: {stderr}")
                return

    def _run_host_start(self) -> None:
        try:
            _start_host(None, self._storage, self._cli_printer)
        except SystemExit as error:
            if error.code != 0:
                self._errors.append(f"host start failed (exit code {error.code})")

    def _run_host_stop(self) -> None:
        try:
            _stop_host(None, self._storage, self._cli_printer)
        except SystemExit as error:
            if error.code != 0:
                self._errors.append(f"host stop failed (exit code {error.code})")

    def _run_ui_start(self) -> None:
        try:
            start_ui(port=self._ui_port)
        except UiStartError as error:
            self._errors.append(f"ui start failed: {error}")

    def _run_ui_stop(self) -> None:
        try:
            stop_ui()
        except UiStopError as error:
            self._errors.append(f"ui stop failed: {error}")


def _resolve_repo_root(repo_path: Path) -> Path:
    """Resolve and validate a source checkout for git pull."""
    base_path = repo_path.expanduser().resolve()
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=base_path,
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise click.ClickException(
            f"Cannot resolve git repository from {base_path}: "
            f"{stderr or 'not a git repo'}"
        )
    return Path(result.stdout.strip()).resolve()


def _format_update_status(result: UpdateCheckResult) -> str:
    """Format an explicit update-check result."""
    if result.update_available:
        return (
            f"Update available: ai-link-net {result.current_version} -> "
            f"{result.latest_version}"
        )
    return f"Already up to date: ai-link-net {result.current_version}"


def _quote_windows(value: str) -> str:
    """Quote one value for a generated Windows command script."""
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def _quote_posix(value: str) -> str:
    """Quote one value for a generated POSIX shell script."""
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _write_update_script(
    *,
    ui_was_running: bool,
    ui_port: int,
    script_dir: Path,
) -> tuple[Path, Path]:
    """Create a detached updater script and return script/log paths."""
    script_dir.mkdir(parents=True, exist_ok=True)
    log_path = script_dir / "update.log"

    if os.name == "nt":
        script_path = script_dir / "update-ai-link-net.cmd"
        quoted_log = _quote_windows(str(log_path))
        ui_command = (
            f"aln ui start --port {ui_port} >> {quoted_log} 2>&1\n"
            "if errorlevel 1 goto failed\n"
            if ui_was_running
            else ""
        )
        content = (
            "@echo off\n"
            "ping 127.0.0.1 -n 3 >nul\n"
            f"echo Updating AI-Link-Net... > {quoted_log}\n"
            f"uv tool upgrade ai-link-net >> {quoted_log} 2>&1\n"
            "if errorlevel 1 goto failed\n"
            f"aln host start >> {quoted_log} 2>&1\n"
            "if errorlevel 1 goto failed\n"
            f"{ui_command}"
            f"echo Update completed. >> {quoted_log}\n"
            "goto cleanup\n"
            ":failed\n"
            f"echo Update failed. Run uv tool upgrade ai-link-net manually. >> {quoted_log}\n"
            ":cleanup\n"
            'del "%~f0"\n'
        )
    else:
        script_path = script_dir / "update-ai-link-net.sh"
        quoted_log = _quote_posix(str(log_path))
        ui_condition = (
            f" && aln ui start --port {ui_port} >> {quoted_log} 2>&1"
            if ui_was_running
            else ""
        )
        content = (
            "#!/bin/sh\n"
            "sleep 2\n"
            f"echo 'Updating AI-Link-Net...' > {quoted_log}\n"
            f"if uv tool upgrade ai-link-net >> {quoted_log} 2>&1 "
            f"&& aln host start >> {quoted_log} 2>&1"
            f"{ui_condition}; then\n"
            f"  echo 'Update completed.' >> {quoted_log}\n"
            "else\n"
            f"  echo 'Update failed. Run uv tool upgrade ai-link-net manually.' "
            f">> {quoted_log}\n"
            "fi\n"
            'rm -- "$0"\n'
        )

    script_path.write_text(content, encoding="utf-8", newline="\n")
    if os.name != "nt":
        script_path.chmod(0o700)
    return script_path, log_path


def _launch_update_script(script_path: Path) -> None:
    """Launch the updater independently from the installed Python process."""
    popen_kwargs: dict[str, object] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
        command = ["cmd.exe", "/d", "/c", str(script_path)]
    else:
        popen_kwargs["start_new_session"] = True
        command = ["/bin/sh", str(script_path)]
    subprocess.Popen(command, **popen_kwargs)


def _stop_runtime(
    storage: StorageManager,
    cli_printer: CliPrinter,
) -> tuple[bool, int]:
    """Stop Hosts and UI before replacing the installed tool."""
    ui_status = _get_ui_status()
    ui_was_running = ui_status is not None
    ui_port = ui_status["port"] if ui_status else 5173

    cli_printer.echo("Stopping hosts...")
    _stop_host(None, storage, cli_printer)
    if ui_was_running:
        cli_printer.echo("Stopping UI...")
        stop_ui()
    return ui_was_running, ui_port


@click.command(
    name="update",
    help="Check for and install a newer AI-Link-Net release.",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--check",
    "check_only",
    is_flag=True,
    help="Check PyPI without installing the update.",
)
@click.option(
    "--source",
    "source_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Update a development checkout with git pull.",
)
@click.option(
    "--ui-port",
    type=int,
    default=5173,
    show_default=True,
    help="Fallback UI port used by the restart step.",
)
@cli_exception_wrapper(error_message="Failed to update runtime")
@get_storage
@get_cli_printer
def command(
    check_only: bool,
    source_path: Path | None,
    ui_port: int,
    storage: StorageManager,
    cli_printer: CliPrinter,
) -> None:
    """Check or update the installed package or a source checkout."""
    if source_path is not None:
        if check_only:
            raise click.ClickException("--check cannot be combined with --source")
        SourceUpdateWorkflow(
            storage=storage,
            cli_printer=cli_printer,
            repo_root=_resolve_repo_root(source_path),
            ui_port=ui_port,
        ).run()
        return

    result = check_for_update(force=True)
    if result is None:
        raise click.ClickException("Unable to check PyPI for updates")

    cli_printer.echo(_format_update_status(result))
    if check_only or not result.update_available:
        return

    if shutil.which("uv") is None:
        raise click.ClickException(
            "uv is required for automatic updates. Run "
            "`uv tool upgrade ai-link-net` after installing uv."
        )

    ui_was_running, detected_ui_port = _stop_runtime(storage, cli_printer)
    restart_port = detected_ui_port if ui_was_running else ui_port
    script_path, log_path = _write_update_script(
        ui_was_running=ui_was_running,
        ui_port=restart_port,
        script_dir=Path(get_fp_home()) / "updates",
    )
    try:
        _launch_update_script(script_path)
    except OSError:
        cli_printer.echo("Failed to launch updater; restarting local services...")
        _start_host(None, storage, cli_printer)
        if ui_was_running:
            start_ui(restart_port)
        raise

    cli_printer.echo("Update started in the background.")
    cli_printer.echo(f"Log: {log_path}")
