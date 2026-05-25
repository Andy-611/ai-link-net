"""`aln update` command."""

from __future__ import annotations

import subprocess
from pathlib import Path

import click
from fp.utils.storage import StorageManager

from .host import _start_host, _stop_host
from .misc.printer import CliPrinter
from .misc.wrappers import cli_exception_wrapper, get_cli_printer, get_storage
from .ui import UiStartError, UiStopError, _get_ui_status, start_ui, stop_ui


class UpdateWorkflow:
    """Orchestrate stop/pull/start update flow for local runtime services."""

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
        """Execute update flow with best-effort restart."""
        self._ui_was_running = _get_ui_status() is not None

        self._cli_printer.echo("Stopping hosts...")
        self._run_host_stop()

        if self._ui_was_running:
            self._cli_printer.echo("Stopping UI...")
            self._run_ui_stop()

        self._cli_printer.echo(f"Pulling latest code in: {self._repo_root}")
        self._run_git_pull()

        self._cli_printer.echo("Reinstalling aln tool...")
        self._run_tool_install()

        self._cli_printer.echo("Starting hosts...")
        self._run_host_start()

        if self._ui_was_running:
            self._cli_printer.echo("Starting UI...")
            self._run_ui_start()

        if self._errors:
            joined_errors = "; ".join(self._errors)
            raise click.ClickException(f"Update failed: {joined_errors}")

        self._cli_printer.echo("✓ Update completed")

    def _run_git_pull(self) -> None:
        """Run git pull in repository root."""
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
        else:
            self._cli_printer.echo(result.stdout.strip())

    def _run_tool_install(self) -> None:
        """Reinstall aln tool globally via uv."""
        result = subprocess.run(
            ["uv", "tool", "install", "-e", "."],
            cwd=self._repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else "unknown error"
            self._errors.append(f"uv tool install failed: {stderr}")

    def _run_host_start(self) -> None:
        """Start hosts and collect failures."""
        try:
            _start_host(None, self._storage, self._cli_printer)
        except SystemExit as error:
            if error.code != 0:
                self._errors.append(f"host start failed (exit code {error.code})")

    def _run_host_stop(self) -> None:
        """Stop hosts and collect failures."""
        try:
            _stop_host(None, self._storage, self._cli_printer)
        except SystemExit as error:
            if error.code != 0:
                self._errors.append(f"host stop failed (exit code {error.code})")

    def _run_ui_start(self) -> None:
        """Start UI and verify runtime status."""
        try:
            start_ui(port=self._ui_port)
        except UiStartError as e:
            self._errors.append(f"ui start failed: {e}")

    def _run_ui_stop(self) -> None:
        """Stop UI and collect failures."""
        try:
            stop_ui()
        except UiStopError as e:
            self._errors.append(f"ui stop failed: {e}")


def _resolve_repo_root(repo_path: Path | None) -> Path:
    """Resolve and validate repository root for git pull."""
    base_path = repo_path or Path(__file__).resolve().parent.parent.parent
    base_path = base_path.expanduser().resolve()

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
            f"Cannot resolve git repository from {base_path}: {stderr or 'not a git repo'}"
        )

    return Path(result.stdout.strip()).resolve()


@click.command(
    name="update",
    help="Stop host/UI, run git pull, then restart host/UI.",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--repo",
    "repo_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Repository path for git pull (default: current project root).",
)
@click.option(
    "--ui-port",
    type=int,
    default=5173,
    show_default=True,
    help="UI port used by restart step.",
)
@cli_exception_wrapper(error_message="Failed to update runtime")
@get_storage
@get_cli_printer
def command(
    repo_path: Path | None,
    ui_port: int,
    storage: StorageManager,
    cli_printer: CliPrinter,
) -> None:
    """Update runtime by restarting services around a git pull."""
    repo_root = _resolve_repo_root(repo_path)
    workflow = UpdateWorkflow(
        storage=storage,
        cli_printer=cli_printer,
        repo_root=repo_root,
        ui_port=ui_port,
    )
    workflow.run()
