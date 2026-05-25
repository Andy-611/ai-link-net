"""Tests for update CLI command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from aln.cli.ui import UiStartError
from aln.cli.update import command as update_command


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


class TestUpdateCommand:
    """Test `aln update` workflow."""

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.update._resolve_repo_root")
    @patch("aln.cli.update._stop_host")
    @patch("aln.cli.update.stop_ui")
    @patch("aln.cli.update.subprocess.run")
    @patch("aln.cli.update._start_host")
    @patch("aln.cli.update.start_ui")
    @patch("aln.cli.update._get_ui_status")
    def test_update_success(
        self,
        mock_get_ui_status,
        mock_start_ui,
        mock_start_host,
        mock_subprocess_run,
        mock_stop_ui,
        mock_stop_host,
        mock_resolve_repo_root,
        mock_get_storage,
        runner: CliRunner,
    ) -> None:
        """Run full update workflow successfully."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_resolve_repo_root.return_value = Path("/tmp/repo")
        mock_subprocess_run.return_value = MagicMock(
            returncode=0, stdout="Already up to date.\n", stderr=""
        )
        mock_get_ui_status.return_value = {"pid": 1234, "port": 5173}

        result = runner.invoke(update_command, [])

        assert result.exit_code == 0
        assert "Update completed" in result.output
        assert mock_subprocess_run.call_count == 2
        mock_stop_host.assert_called_once()
        mock_start_host.assert_called_once()
        mock_stop_ui.assert_called_once()
        mock_start_ui.assert_called_once_with(port=5173)

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.update._resolve_repo_root")
    @patch("aln.cli.update._stop_host")
    @patch("aln.cli.update.stop_ui")
    @patch("aln.cli.update.subprocess.run")
    @patch("aln.cli.update._start_host")
    @patch("aln.cli.update.start_ui")
    @patch("aln.cli.update._get_ui_status")
    def test_update_git_pull_failed_but_restart_attempted(
        self,
        mock_get_ui_status,
        mock_start_ui,
        mock_start_host,
        mock_subprocess_run,
        mock_stop_ui,
        mock_stop_host,
        mock_resolve_repo_root,
        mock_get_storage,
        runner: CliRunner,
    ) -> None:
        """Continue restart even if git pull fails, then return non-zero."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_resolve_repo_root.return_value = Path("/tmp/repo")

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("cmd", [])
            if "git" in cmd:
                return MagicMock(returncode=1, stdout="", stderr="fatal: not a git repo")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_subprocess_run.side_effect = subprocess_side_effect
        mock_get_ui_status.return_value = {"pid": 3456, "port": 5173}

        result = runner.invoke(update_command, [])

        assert result.exit_code != 0
        assert "git pull failed" in result.output
        mock_stop_host.assert_called_once()
        mock_start_host.assert_called_once()
        mock_stop_ui.assert_called_once()
        mock_start_ui.assert_called_once_with(port=5173)

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.update._resolve_repo_root")
    @patch("aln.cli.update._stop_host")
    @patch("aln.cli.update.stop_ui")
    @patch("aln.cli.update.subprocess.run")
    @patch("aln.cli.update._start_host")
    @patch("aln.cli.update.start_ui")
    @patch("aln.cli.update._get_ui_status")
    def test_update_ui_start_failed(
        self,
        mock_get_ui_status,
        mock_start_ui,
        mock_start_host,
        mock_subprocess_run,
        mock_stop_ui,
        mock_stop_host,
        mock_resolve_repo_root,
        mock_get_storage,
        runner: CliRunner,
    ) -> None:
        """Return non-zero when UI start fails."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_resolve_repo_root.return_value = Path("/tmp/repo")
        mock_subprocess_run.return_value = MagicMock(
            returncode=0, stdout="Success\n", stderr=""
        )
        mock_get_ui_status.return_value = {"pid": 1234, "port": 5173}
        mock_start_ui.side_effect = UiStartError("npm failed")

        result = runner.invoke(update_command, [])

        assert result.exit_code != 0
        assert "ui start failed" in result.output
        mock_stop_host.assert_called_once()
        mock_start_host.assert_called_once()
        mock_stop_ui.assert_called_once()
        mock_start_ui.assert_called_once_with(port=5173)

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.update._resolve_repo_root")
    @patch("aln.cli.update._stop_host")
    @patch("aln.cli.update.stop_ui")
    @patch("aln.cli.update.subprocess.run")
    @patch("aln.cli.update._start_host")
    @patch("aln.cli.update.start_ui")
    @patch("aln.cli.update._get_ui_status")
    def test_update_ui_not_running_initially(
        self,
        mock_get_ui_status,
        mock_start_ui,
        mock_start_host,
        mock_subprocess_run,
        mock_stop_ui,
        mock_stop_host,
        mock_resolve_repo_root,
        mock_get_storage,
        runner: CliRunner,
    ) -> None:
        """Skip UI start/stop when UI was not running."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_resolve_repo_root.return_value = Path("/tmp/repo")
        mock_subprocess_run.return_value = MagicMock(
            returncode=0, stdout="Success\n", stderr=""
        )
        mock_get_ui_status.return_value = None

        result = runner.invoke(update_command, [])

        assert result.exit_code == 0
        assert "Update completed" in result.output
        assert "Stopping UI" not in result.output
        assert "Starting UI" not in result.output
        mock_stop_ui.assert_not_called()
        mock_start_ui.assert_not_called()

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.update._resolve_repo_root")
    @patch("aln.cli.update._stop_host")
    @patch("aln.cli.update.stop_ui")
    @patch("aln.cli.update.subprocess.run")
    @patch("aln.cli.update._start_host")
    @patch("aln.cli.update.start_ui")
    @patch("aln.cli.update._get_ui_status")
    def test_update_tool_install_failed(
        self,
        mock_get_ui_status,
        mock_start_ui,
        mock_start_host,
        mock_subprocess_run,
        mock_stop_ui,
        mock_stop_host,
        mock_resolve_repo_root,
        mock_get_storage,
        runner: CliRunner,
    ) -> None:
        """Continue even if uv tool install fails, but report error."""
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_resolve_repo_root.return_value = Path("/tmp/repo")

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("cmd", [])
            if "git" in cmd:
                return MagicMock(returncode=0, stdout="Success\n", stderr="")
            if "uv" in cmd and "tool" in cmd:
                return MagicMock(returncode=1, stdout="", stderr="uv tool install failed")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_subprocess_run.side_effect = subprocess_side_effect
        mock_get_ui_status.return_value = {"pid": 1234, "port": 5173}

        result = runner.invoke(update_command, [])

        assert result.exit_code != 0
        assert "uv tool install failed" in result.output
