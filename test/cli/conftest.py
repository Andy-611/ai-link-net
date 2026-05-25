"""Shared fixtures for CLI tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner
from fp import EntityCard, FPAddress
from fp.utils.storage import HostConfigEntry, StorageManager

from aln.app import HostClient
from aln.app.schemas import HealthResponse


@pytest.fixture
def cli_runner():
    """Create Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_storage():
    """Create mock StorageManager."""
    storage = MagicMock(spec=StorageManager)

    # Default host entry
    default_host = HostConfigEntry(
        name="default",
        bind_host="0.0.0.0",
        port=7001,
        url="http://0.0.0.0:7001",
        address="test_host_uid_123",
        parent_url=None,
    )

    storage.get_host.return_value = default_host
    storage.get_all_hosts.return_value = {"test_host_uid_123": default_host}
    storage.get_default_host.return_value = "test_host_uid_123"
    storage.get_host_url.return_value = "http://0.0.0.0:7001"
    storage.resolve_host_name.return_value = "test_host_uid_123"
    storage.get_host_pid.return_value = None
    storage.exists.return_value = True
    storage._config_path.return_value = Path("/tmp/config.json")
    storage.get_host_state_path.return_value = Path("/tmp/state.json")
    storage.get_host_log_path.return_value = Path("/tmp/host.log")
    storage._entity_mailbox_path.return_value = Path("/tmp/mailbox")

    return storage


@pytest.fixture
def mock_host_client():
    """Create mock HostClient."""
    client = MagicMock(spec=HostClient)

    # Default health response
    client.check_health.return_value = HealthResponse(ok=True, host_name="default")

    # Default entity card
    entity_card = EntityCard(
        name="TestEntity",
        address=FPAddress(address="test_host:entity1"),
        kind="agent",
        sign_public_key="test_sign_key",
        encrypt_public_key="test_encrypt_key",
        description="Test entity",
        is_public=True,
        entity_uid="entity1",
        host_uid="test_host",
    )
    client.entity_register.return_value = entity_card
    client.entity_search.return_value = [entity_card]

    return client


@pytest.fixture
def mock_cli_printer():
    """Create mock CliPrinter."""
    from aln.cli.misc.printer import CliPrinter

    printer = MagicMock(spec=CliPrinter)
    return printer
