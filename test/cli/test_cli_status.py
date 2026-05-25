"""Tests for status CLI command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from aln.cli.status import command as status_command
from aln.app.schemas import HealthResponse


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


class TestHealth:
    """Test health command."""

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.misc.wrappers.HostClient")
    def test_health_check_ok(self, mock_host_client_cls, mock_get_storage, runner):
        """Test health check when host is healthy."""
        mock_storage = MagicMock()
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_client = MagicMock()
        mock_client.check_health.return_value = HealthResponse(ok=True, host_name="default")
        mock_host_client_cls.return_value = mock_client

        result = runner.invoke(status_command, ["--host", "default"])

        assert result.exit_code == 0
        mock_client.check_health.assert_called_once()

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.misc.wrappers.HostClient")
    def test_health_check_failed(self, mock_host_client_cls, mock_get_storage, runner):
        """Test health check when host is unhealthy."""
        mock_storage = MagicMock()
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_client = MagicMock()
        mock_client.check_health.return_value = HealthResponse(ok=False, host_name="default")
        mock_host_client_cls.return_value = mock_client

        result = runner.invoke(status_command, ["--host", "default"])

        assert result.exit_code == 0
        mock_client.check_health.assert_called_once()

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.misc.wrappers.HostClient")
    def test_health_check_connection_error(
        self, mock_host_client_cls, mock_get_storage, runner
    ):
        """Test health check when connection fails."""
        mock_storage = MagicMock()
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_client = MagicMock()
        from aln.app import HostClientError

        mock_client.check_health.side_effect = HostClientError("Connection refused")
        mock_host_client_cls.return_value = mock_client

        result = runner.invoke(status_command, ["--host", "default"])

        assert result.exit_code == 1
        assert "Host Error" in result.output
