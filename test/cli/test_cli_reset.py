"""Tests for reset CLI command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
from click.testing import CliRunner

from aln.cli.reset import command as reset_command


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


class TestReset:
    """Test reset command."""

    @patch("aln.cli.reset.get_storage_manager")
    @patch("aln.cli.reset.stop_pid")
    @patch("aln.cli.reset.is_pid_alive")
    @patch("aln.cli.reset.shutil.rmtree")
    @patch("aln.cli.reset.Path.exists")
    def test_reset_with_yes_flag(
        self,
        mock_exists,
        mock_rmtree,
        mock_is_pid_alive,
        mock_stop_pid,
        mock_get_storage,
        runner,
    ):
        """Test reset with --yes flag (skip confirmation)."""
        mock_storage = MagicMock()
        from fp.utils.storage import HostConfigEntry

        host_entry = HostConfigEntry(
            name="default",
            bind_host="0.0.0.0",
            port=7001,
            url="http://0.0.0.0:7001",
            address="host_addr",
            parent_url=None,
        )
        mock_storage.get_all_hosts.return_value = {"host_uid": host_entry}
        mock_storage.get_host_pid.return_value = 12345
        mock_storage.exists.return_value = True
        mock_get_storage.return_value = mock_storage

        mock_is_pid_alive.return_value = False
        mock_stop_pid.return_value = True
        mock_exists.return_value = True

        result = runner.invoke(reset_command, ["--yes"])

        assert result.exit_code == 0
        assert "Reset complete" in result.output
        mock_rmtree.assert_called_once()

    @patch("aln.cli.reset.get_storage_manager")
    @patch("aln.cli.reset.stop_pid")
    @patch("aln.cli.reset.is_pid_alive")
    @patch("aln.cli.reset.shutil.rmtree")
    @patch("aln.cli.reset.Path.exists")
    @patch("aln.cli.reset.Path.read_text")
    def test_reset_stops_ui_process(
        self,
        mock_read_text,
        mock_exists,
        mock_rmtree,
        mock_is_pid_alive,
        mock_stop_pid,
        mock_get_storage,
        runner,
    ):
        """Test reset stops UI process if running."""
        mock_storage = MagicMock()
        mock_storage.get_all_hosts.return_value = {}
        mock_storage.exists.return_value = True
        mock_get_storage.return_value = mock_storage

        mock_exists.side_effect = [True, True]
        mock_read_text.return_value = "54321"
        mock_is_pid_alive.return_value = False
        mock_stop_pid.return_value = True

        result = runner.invoke(reset_command, ["--yes"])

        assert result.exit_code == 0
        assert "UI stopped" in result.output

    @patch("aln.cli.reset.get_storage_manager")
    @patch("aln.cli.reset.stop_pid")
    @patch("aln.cli.reset.is_pid_alive")
    @patch("aln.cli.reset.shutil.rmtree")
    @patch("aln.cli.reset.Path.exists")
    @patch("aln.cli.reset.subprocess.run")
    def test_reset_stops_orphan_hosts(
        self,
        mock_subprocess_run,
        mock_exists,
        mock_rmtree,
        mock_is_pid_alive,
        mock_stop_pid,
        mock_get_storage,
        runner,
    ):
        """Test reset stops orphan host processes."""
        mock_storage = MagicMock()
        mock_storage.get_all_hosts.return_value = {}
        mock_storage.exists.return_value = True
        mock_get_storage.return_value = mock_storage

        mock_exists.side_effect = [False, True]
        mock_is_pid_alive.return_value = True
        mock_stop_pid.return_value = True

        # Mock ps output with orphan uvicorn process
        ps_output = "12345 uvicorn aln.app.main:app --host 0.0.0.0 --port 7001\n"
        mock_subprocess_run.return_value = MagicMock(
            returncode=0, stdout=ps_output
        )

        result = runner.invoke(reset_command, ["--yes"])

        assert result.exit_code == 0
        assert "Stopped orphan hosts" in result.output

    def test_reset_requires_confirmation(self, runner):
        """Test reset requires confirmation when --yes not provided."""
        result = runner.invoke(reset_command, [], input="n\n")

        assert result.exit_code == 0
        assert "Aborted" in result.output


class TestResetHelpers:
    """Test reset helper functions."""

    @patch("aln.cli.reset.Path.exists")
    @patch("aln.cli.reset.Path.read_text")
    @patch("aln.cli.reset.stop_pid")
    def test_stop_ui_process_success(self, mock_stop_pid, mock_read_text, mock_exists):
        """Test stopping UI process."""
        from aln.cli.reset import _stop_ui_process

        mock_exists.return_value = True
        mock_read_text.return_value = "12345"
        mock_stop_pid.return_value = True

        result = _stop_ui_process(Path("/tmp"))

        assert result is True
        mock_stop_pid.assert_called_once_with(12345)

    @patch("aln.cli.reset.Path.exists")
    def test_stop_ui_process_no_pid_file(self, mock_exists):
        """Test stopping UI when no pid file."""
        from aln.cli.reset import _stop_ui_process

        mock_exists.return_value = False

        result = _stop_ui_process(Path("/tmp"))

        assert result is False

    def test_delete_all_hosts(self):
        """Test deleting hosts from config when host is not running."""
        from aln.cli.reset import _delete_all_hosts
        from fp.utils.storage import HostConfigEntry

        mock_storage = MagicMock()
        host1 = HostConfigEntry(
            name="host1",
            bind_host="0.0.0.0",
            port=7001,
            url="http://0.0.0.0:7001",
            address="uid1",
            parent_url=None,
        )
        mock_storage.get_all_hosts.return_value = {"uid1": host1}
        mock_storage.get_entities_for_host.return_value = []
        mock_storage.get_host_pid.return_value = None

        deleted, failed = _delete_all_hosts(mock_storage)

        assert deleted == 1
        assert failed == 0
        mock_storage.delete_host_from_config.assert_called_once_with("uid1")

    @patch("aln.cli.reset.subprocess.run")
    @patch("aln.cli.reset.is_pid_alive")
    def test_find_orphan_host_pids(self, mock_is_pid_alive, mock_subprocess_run):
        """Test finding orphan host processes."""
        from aln.cli.reset import _find_orphan_host_pids

        ps_output = """
        12345 uvicorn aln.app.main:app --host 0.0.0.0
        67890 python script.py
        11111 uvicorn aln.app.main:app --port 7001
        """
        mock_subprocess_run.return_value = MagicMock(
            returncode=0, stdout=ps_output
        )
        mock_is_pid_alive.return_value = True

        result = _find_orphan_host_pids(exclude_pids={67890})

        assert 12345 in result
        assert 11111 in result
        assert 67890 not in result
