"""Tests for the `aln update` command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from aln.cli.update import _write_update_script, command as update_command
from aln.cli.update_check import UpdateCheckResult


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


def update_result(*, available: bool) -> UpdateCheckResult:
    """Build a stable update-check result for command tests."""
    return UpdateCheckResult(
        current_version="0.1.0",
        latest_version="0.2.0" if available else "0.1.0",
        update_available=available,
        from_cache=False,
    )


class TestInstalledUpdate:
    """Test the installed-package update path."""

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.update.check_for_update")
    def test_check_reports_available_version(
        self,
        mock_check,
        mock_get_storage,
        runner: CliRunner,
    ) -> None:
        mock_get_storage.return_value = MagicMock()
        mock_check.return_value = update_result(available=True)

        result = runner.invoke(update_command, ["--check"])

        assert result.exit_code == 0
        assert "0.1.0 -> 0.2.0" in result.output
        mock_check.assert_called_once_with(force=True)

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.update.check_for_update")
    def test_update_exits_when_already_current(
        self,
        mock_check,
        mock_get_storage,
        runner: CliRunner,
    ) -> None:
        mock_get_storage.return_value = MagicMock()
        mock_check.return_value = update_result(available=False)

        result = runner.invoke(update_command, [])

        assert result.exit_code == 0
        assert "Already up to date" in result.output

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.update._launch_update_script")
    @patch("aln.cli.update._write_update_script")
    @patch("aln.cli.update._stop_runtime")
    @patch("aln.cli.update.shutil.which")
    @patch("aln.cli.update.check_for_update")
    def test_update_stops_runtime_and_launches_external_script(
        self,
        mock_check,
        mock_which,
        mock_stop_runtime,
        mock_write_script,
        mock_launch_script,
        mock_get_storage,
        runner: CliRunner,
    ) -> None:
        storage = MagicMock()
        mock_get_storage.return_value = storage
        mock_check.return_value = update_result(available=True)
        mock_which.return_value = "C:/tools/uv.exe"
        mock_stop_runtime.return_value = (True, 5199)
        mock_write_script.return_value = (
            Path("C:/tmp/update.cmd"),
            Path("C:/tmp/update.log"),
        )

        result = runner.invoke(update_command, [])

        assert result.exit_code == 0
        assert "Update started in the background" in result.output
        mock_stop_runtime.assert_called_once()
        mock_write_script.assert_called_once()
        assert mock_write_script.call_args.kwargs["ui_was_running"] is True
        assert mock_write_script.call_args.kwargs["ui_port"] == 5199
        mock_launch_script.assert_called_once_with(Path("C:/tmp/update.cmd"))

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.update.shutil.which", return_value=None)
    @patch("aln.cli.update.check_for_update")
    def test_update_requires_uv_before_stopping_services(
        self,
        mock_check,
        _mock_which,
        mock_get_storage,
        runner: CliRunner,
    ) -> None:
        mock_get_storage.return_value = MagicMock()
        mock_check.return_value = update_result(available=True)

        result = runner.invoke(update_command, [])

        assert result.exit_code != 0
        assert "uv is required" in result.output


class TestSourceUpdate:
    """Test the opt-in source-checkout update path."""

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.update.SourceUpdateWorkflow")
    @patch("aln.cli.update._resolve_repo_root")
    def test_source_option_runs_checkout_workflow(
        self,
        mock_resolve_repo_root,
        mock_workflow_class,
        mock_get_storage,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        storage = MagicMock()
        workflow = MagicMock()
        mock_get_storage.return_value = storage
        mock_resolve_repo_root.return_value = tmp_path
        mock_workflow_class.return_value = workflow

        result = runner.invoke(update_command, ["--source", str(tmp_path)])

        assert result.exit_code == 0
        mock_workflow_class.assert_called_once()
        workflow.run.assert_called_once_with()

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    def test_check_and_source_are_mutually_exclusive(
        self,
        mock_get_storage,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        mock_get_storage.return_value = MagicMock()

        result = runner.invoke(
            update_command,
            ["--check", "--source", str(tmp_path)],
        )

        assert result.exit_code != 0
        assert "cannot be combined" in result.output


def test_generated_update_script_upgrades_and_restarts_ui(tmp_path) -> None:
    """Generate an external script that upgrades and restores the runtime."""
    script_path, log_path = _write_update_script(
        ui_was_running=True,
        ui_port=5199,
        script_dir=tmp_path,
    )

    content = script_path.read_text(encoding="utf-8")

    assert "uv tool upgrade ai-link-net" in content
    assert "aln host start" in content
    assert "aln ui start --port 5199" in content
    assert str(log_path) in content
