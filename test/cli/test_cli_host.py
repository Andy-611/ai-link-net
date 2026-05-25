"""Tests for host CLI commands."""

from __future__ import annotations

import unittest.mock
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from click.testing import CliRunner

from aln.cli.host import command as host_command, find_available_port, _resolve_target_hosts
from fp.utils.storage import HostConfigEntry


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


class TestHostInit:
    """Test host init command."""

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.host.subprocess.Popen")
    @patch("aln.cli.host.is_pid_alive")
    @patch("aln.cli.host._has_uv")
    @patch("aln.cli.host._wait_host_ready", return_value=True)
    def test_init_new_host(self, mock_wait, mock_has_uv, mock_is_pid_alive, mock_popen, mock_get_storage, runner):
        """Test initializing a new host."""
        mock_storage = MagicMock()

        # First call raises exception, subsequent calls return host entry
        new_host = HostConfigEntry(
            name="testhost",
            bind_host="0.0.0.0",
            port=7001,
            url="http://0.0.0.0:7001",
            address="new_test_addr",
            parent_url=None,
        )
        mock_storage.get_host.side_effect = [Exception("Host not found"), new_host]
        mock_storage.get_host_pid.return_value = None
        mock_storage._config_path.return_value = Path("/tmp/config.json")
        mock_storage.get_all_hosts.return_value = {"new_test_addr": new_host}
        mock_storage.resolve_host_name.return_value = "new_test_addr"
        mock_get_storage.return_value = mock_storage

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        mock_is_pid_alive.return_value = False
        mock_has_uv.return_value = True

        result = runner.invoke(
            host_command,
            ["new", "--name", "testhost", "--port", "7001"],
        )

        assert result.exit_code == 0
        assert "testhost" in result.output
        assert "initialized" in result.output.lower()
        mock_storage.create_or_update_host.assert_called()
        mock_storage.set_host_pid.assert_called_with("new_test_addr", 12345)

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.host.subprocess.Popen")
    @patch("aln.cli.host.is_pid_alive")
    def test_init_existing_running_host_with_config_change(
        self, mock_is_pid_alive, mock_popen, mock_get_storage, runner
    ):
        """Test init fails when host is running and config changes."""
        mock_storage = MagicMock()
        existing_host = HostConfigEntry(
            name="testhost",
            bind_host="0.0.0.0",
            port=7001,
            url="http://0.0.0.0:7001",
            address="test_addr",
            parent_url=None,
        )
        mock_storage.get_host.return_value = existing_host
        mock_storage.get_host_pid.return_value = 12345
        mock_get_storage.return_value = mock_storage
        mock_is_pid_alive.return_value = True

        result = runner.invoke(
            host_command,
            ["new", "--name", "testhost", "--port", "7002"],
        )

        assert result.exit_code != 0
        assert "is running" in result.output
        assert "Stop it before" in result.output


class TestHostSet:
    """Test host set command."""

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.misc.wrappers.HostClient")
    def test_set_parent_url(self, mock_host_client_cls, mock_get_storage, runner):
        """Test setting parent URL."""
        mock_storage = MagicMock()
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_client.host_update.return_value = mock_response
        mock_host_client_cls.return_value = mock_client

        result = runner.invoke(
            host_command, ["set", "--host", "default", "--parent", "http://parent:8000"]
        )

        assert result.exit_code == 0
        mock_client.host_update.assert_called_once()
        mock_storage.create_or_update_host.assert_not_called()

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.misc.wrappers.HostClient")
    def test_set_no_options(self, mock_host_client_cls, mock_get_storage, runner):
        """Test set command with no options shows help."""
        mock_storage = MagicMock()
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_client = MagicMock()
        mock_host_client_cls.return_value = mock_client

        result = runner.invoke(host_command, ["set", "--host", "default"])

        assert result.exit_code == 0
        assert "No options provided" in result.output


class TestHostStartStop:
    """Test host start/stop commands."""

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.host.subprocess.Popen")
    @patch("aln.cli.host.is_pid_alive")
    @patch("aln.cli.host._has_uv")
    @patch("aln.cli.host._wait_host_ready", return_value=True)
    def test_start_host(self, mock_wait, mock_has_uv, mock_is_pid_alive, mock_popen, mock_get_storage, runner):
        """Test starting a host."""
        mock_storage = MagicMock()
        host_entry = HostConfigEntry(
            name="default",
            bind_host="0.0.0.0",
            port=7001,
            url="http://0.0.0.0:7001",
            address="test_addr",
            parent_url=None,
        )
        mock_storage.get_host.return_value = host_entry
        mock_storage.get_all_hosts.return_value = {"test_uid": host_entry}
        mock_storage.resolve_host_name.return_value = "test_uid"
        mock_storage.get_host_pid.return_value = None
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_process = MagicMock()
        mock_process.pid = 99999
        mock_popen.return_value = mock_process
        mock_is_pid_alive.return_value = False
        mock_has_uv.return_value = True

        result = runner.invoke(host_command, ["start", "--host", "default"])

        assert result.exit_code == 0
        assert "started" in result.output.lower()
        mock_storage.set_host_pid.assert_called_once_with("test_uid", 99999)

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.host.subprocess.Popen")
    @patch("aln.cli.host.is_pid_alive")
    @patch("aln.cli.host._has_uv")
    @patch("aln.cli.host._wait_host_ready", return_value=True)
    def test_start_host_dev_mode(
        self, mock_wait, mock_has_uv, mock_is_pid_alive, mock_popen, mock_get_storage, runner
    ):
        """Test starting a host in dev mode with reload."""
        mock_storage = MagicMock()
        host_entry = HostConfigEntry(
            name="default",
            bind_host="0.0.0.0",
            port=7001,
            url="http://0.0.0.0:7001",
            address="test_addr",
            parent_url=None,
        )
        mock_storage.get_host.return_value = host_entry
        mock_storage.get_all_hosts.return_value = {"test_uid": host_entry}
        mock_storage.resolve_host_name.return_value = "test_uid"
        mock_storage.get_host_pid.return_value = None
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_process = MagicMock()
        mock_process.pid = 99999
        mock_popen.return_value = mock_process
        mock_is_pid_alive.return_value = False
        mock_has_uv.return_value = True

        result = runner.invoke(host_command, ["start", "--host", "default"])

        assert result.exit_code == 0
        cmd = mock_popen.call_args[0][0]
        assert "--reload" in cmd

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.host.is_pid_alive")
    @patch("aln.cli.host.stop_pid")
    def test_stop_host(self, mock_stop_pid, mock_is_pid_alive, mock_get_storage, runner):
        """Test stopping a host."""
        mock_storage = MagicMock()
        host_entry = HostConfigEntry(
            name="default",
            bind_host="0.0.0.0",
            port=7001,
            url="http://0.0.0.0:7001",
            address="test_addr",
            parent_url=None,
        )
        mock_storage.get_host.return_value = host_entry
        mock_storage.get_all_hosts.return_value = {"test_uid": host_entry}
        mock_storage.resolve_host_name.return_value = "test_uid"
        mock_storage.get_host_pid.return_value = 12345
        mock_get_storage.return_value = mock_storage

        mock_is_pid_alive.return_value = True
        mock_stop_pid.return_value = True

        result = runner.invoke(host_command, ["stop"])

        assert result.exit_code == 0
        assert "stopped" in result.output.lower()
        mock_stop_pid.assert_called_once()
        mock_storage.delete_host_pid.assert_called_once()


class TestHostList:
    """Test host list command."""

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.host.is_pid_alive")
    def test_list_hosts(self, mock_is_pid_alive, mock_get_storage, runner):
        """Test listing all hosts."""
        mock_storage = MagicMock()
        host1 = HostConfigEntry(
            name="host1",
            bind_host="0.0.0.0",
            port=7001,
            url="http://0.0.0.0:7001",
            address="uid1",
            parent_url=None,
        )
        host2 = HostConfigEntry(
            name="host2",
            bind_host="0.0.0.0",
            port=7001,
            url="http://0.0.0.0:7001",
            address="uid2",
            parent_url=None,
        )
        mock_storage.get_all_hosts.return_value = {"uid1": host1, "uid2": host2}
        mock_storage.get_default_host.return_value = "uid1"
        mock_storage.get_host_pid.side_effect = [12345, None]
        mock_get_storage.return_value = mock_storage
        mock_is_pid_alive.return_value = True

        result = runner.invoke(host_command, ["list"])

        assert result.exit_code == 0
        assert "host1" in result.output
        assert "host2" in result.output
        assert "Default host" in result.output

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    def test_list_no_hosts(self, mock_get_storage, runner):
        """Test list when no hosts configured."""
        mock_storage = MagicMock()
        mock_storage.get_all_hosts.return_value = {}
        mock_get_storage.return_value = mock_storage

        result = runner.invoke(host_command, ["list"])

        assert result.exit_code == 0
        assert "No hosts configured" in result.output


class TestHostDetail:
    """Test host detail command."""

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.host.HostClient")
    @patch("aln.cli.misc.process.is_pid_alive")
    def test_detail_running_host(
        self, mock_is_pid_alive, mock_host_client_cls, mock_get_storage, runner
    ):
        """Test showing details of a running host."""
        mock_storage = MagicMock()
        host_entry = HostConfigEntry(
            name="default",
            bind_host="0.0.0.0",
            port=7001,
            url="http://0.0.0.0:7001",
            address="test_addr",
            parent_url="http://parent:8000",
        )
        mock_storage.get_all_hosts.return_value = {"test_uid": host_entry}
        mock_storage.get_default_host.return_value = "test_uid"
        mock_storage.resolve_host_name.return_value = "test_uid"
        mock_storage.get_host_pid.return_value = 12345
        mock_storage.get_host_state_path.return_value = Path("/tmp/nonexist_test.json")
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage
        mock_is_pid_alive.return_value = True

        mock_client = MagicMock()
        mock_client.check_health.return_value = MagicMock(ok=True)
        mock_client.get_wellknown.return_value = {}
        mock_client.entity_search.return_value = []
        mock_host_client_cls.return_value = mock_client

        result = runner.invoke(host_command, ["detail", "--host", "default"])

        assert result.exit_code == 0
        assert "default" in result.output
        assert "Running" in result.output
        assert "http://parent:8000" in result.output


class TestHostLog:
    """Test host log command."""

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    def test_log_file_not_found(self, mock_get_storage, runner):
        """Test log command when log file doesn't exist."""
        mock_storage = MagicMock()
        mock_storage.get_host_log_path.return_value = Path("/tmp/nonexist_test_log.log")
        mock_get_storage.return_value = mock_storage

        result = runner.invoke(host_command, ["log", "--host", "default"])

        assert result.exit_code == 0
        assert "No log file found" in result.output


class TestHostReset:
    """Test host reset command."""

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.host.subprocess.Popen")
    @patch("aln.cli.host.is_pid_alive")
    @patch("aln.cli.host.stop_pid")
    @patch("aln.cli.host._has_uv")
    @patch("aln.cli.host._wait_host_ready", return_value=True)
    def test_reset_host(
        self, mock_wait, mock_has_uv, mock_stop_pid, mock_is_pid_alive, mock_popen, mock_get_storage, runner
    ):
        """Test resetting a host (stop then start)."""
        mock_storage = MagicMock()
        host_entry = HostConfigEntry(
            name="default",
            bind_host="0.0.0.0",
            port=7001,
            url="http://0.0.0.0:7001",
            address="test_addr",
            parent_url=None,
        )
        mock_storage.get_host.return_value = host_entry
        mock_storage.get_all_hosts.return_value = {"test_uid": host_entry}
        mock_storage.resolve_host_name.return_value = "test_uid"
        mock_storage.get_host_pid.side_effect = [12345, None]
        mock_storage._config_path.return_value = Path("/tmp/config.json")
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_is_pid_alive.return_value = True
        mock_stop_pid.return_value = True

        mock_process = MagicMock()
        mock_process.pid = 99999
        mock_popen.return_value = mock_process
        mock_has_uv.return_value = True

        result = runner.invoke(host_command, ["reset", "--host", "default"])

        assert result.exit_code == 0
        assert "stopped" in result.output.lower()
        assert "started" in result.output.lower()


class TestHostHelpers:
    """Test host helper functions."""

    def test_find_available_port(self):
        """Test finding available port."""
        port = find_available_port(start_port=9000)
        assert 9000 <= port < 9100

    def test_resolve_target_hosts_all(self):
        """Test resolving 'all' hosts."""
        mock_storage = MagicMock()
        mock_storage.get_all_hosts.return_value = {"uid1": MagicMock(), "uid2": MagicMock()}

        result = _resolve_target_hosts(None, mock_storage)
        assert len(result) == 2
        assert "uid1" in result
        assert "uid2" in result

    def test_resolve_target_hosts_specific(self):
        """Test resolving specific host."""
        mock_storage = MagicMock()
        mock_storage.resolve_host_name.return_value = "uid1"

        result = _resolve_target_hosts("myhost", mock_storage)
        assert result == ["uid1"]
