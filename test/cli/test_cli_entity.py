"""Tests for entity CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from aln.cli.entity import command as entity_command
from fp import EntityCard, FPAddress


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


def _build_entity_card(
    *,
    name: str = "TestEntity",
    entity_uid: str = "entity1",
    host_uid: str = "host1",
    is_public: bool = True,
) -> EntityCard:
    """Build one entity card for test stubs."""
    return EntityCard(
        name=name,
        address=FPAddress(address=f"{host_uid}:{entity_uid}"),
        kind="agent",
        sign_public_key="sign_key",
        encrypt_public_key="encrypt_key",
        description="",
        is_public=is_public,
        entity_uid=entity_uid,
        host_uid=host_uid,
    )


class TestEntityRegister:
    """Test entity register command."""

    @patch("fp.utils.storage.get_storage_manager")
    @patch("aln.cli.entity.HostClient")
    def test_register_agent(self, mock_host_client_cls, mock_get_storage, runner: CliRunner):
        """Test registering a new agent entity."""
        mock_storage = MagicMock()
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_client = MagicMock()
        mock_client.entity_register.return_value = _build_entity_card(name="TestAgent")
        mock_host_client_cls.return_value = mock_client

        result = runner.invoke(
            entity_command,
            ["register", "-k", "agent", "-n", "TestAgent"],
        )

        assert result.exit_code == 0
        mock_client.entity_register.assert_called_once()

    @patch("fp.utils.storage.get_storage_manager")
    @patch("aln.cli.entity.HostClient")
    def test_register_with_provider(
        self,
        mock_host_client_cls,
        mock_get_storage,
        runner: CliRunner,
    ):
        """Test registering agent with provider."""
        mock_storage = MagicMock()
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_client = MagicMock()
        mock_client.entity_register.return_value = _build_entity_card(name="ClaudeAgent")
        mock_host_client_cls.return_value = mock_client

        result = runner.invoke(
            entity_command,
            ["register", "-k", "agent", "-n", "ClaudeAgent", "--provider", "claude"],
        )

        assert result.exit_code == 0
        call_kwargs = mock_client.entity_register.call_args.kwargs
        assert call_kwargs["provider"] == "claude"

    @patch("fp.utils.storage.get_storage_manager")
    @patch("aln.cli.entity.HostClient")
    def test_register_private_entity(
        self,
        mock_host_client_cls,
        mock_get_storage,
        runner: CliRunner,
    ):
        """Test registering a private entity."""
        mock_storage = MagicMock()
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_client = MagicMock()
        mock_client.entity_register.return_value = _build_entity_card(
            name="PrivateAgent",
            is_public=False,
        )
        mock_host_client_cls.return_value = mock_client

        result = runner.invoke(
            entity_command,
            ["register", "-k", "agent", "-n", "PrivateAgent", "--private"],
        )

        assert result.exit_code == 0
        call_kwargs = mock_client.entity_register.call_args.kwargs
        assert call_kwargs["is_private"] is True


class TestEntityDelete:
    """Test entity delete command."""

    @patch("fp.utils.storage.get_storage_manager")
    @patch("aln.cli.entity.HostClient")
    @patch("aln.cli.entity.resolve_entity_card")
    def test_delete_entity(
        self,
        mock_resolve_entity_card,
        mock_host_client_cls,
        mock_get_storage,
        runner: CliRunner,
    ):
        """Test deleting an entity."""
        entity_card = _build_entity_card(name="Entity1")
        mock_resolve_entity_card.return_value = entity_card

        mock_storage = MagicMock()
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_client = MagicMock()
        mock_client.entity_delete.return_value = None
        mock_host_client_cls.return_value = mock_client

        result = runner.invoke(entity_command, ["delete", "-e", "entity1"])

        assert result.exit_code == 0
        assert "deleted successfully" in result.output
        mock_client.entity_delete.assert_called_once_with("entity1")


class TestEntitySet:
    """Test entity set command."""

    @patch("fp.utils.storage.get_storage_manager")
    @patch("aln.cli.entity.HostClient")
    @patch("aln.cli.entity.resolve_entity_card")
    def test_set_visible(
        self,
        mock_resolve_entity_card,
        mock_host_client_cls,
        mock_get_storage,
        runner: CliRunner,
    ):
        """Test setting entity visibility."""
        entity_card = _build_entity_card()
        mock_resolve_entity_card.return_value = entity_card

        mock_storage = MagicMock()
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_client = MagicMock()
        mock_client.entity_update.return_value = entity_card
        mock_host_client_cls.return_value = mock_client

        result = runner.invoke(
            entity_command,
            ["set", "-e", "entity1", "--visible", "true"],
        )

        assert result.exit_code == 0
        call_kwargs = mock_client.entity_update.call_args.kwargs
        assert call_kwargs["entity_uid"] == "entity1"
        assert call_kwargs["update_request"].visible is True

    @patch("aln.cli.entity.HostClient")
    @patch("aln.cli.entity.resolve_entity_card")
    def test_set_no_options(self, mock_resolve_entity_card, mock_host_client_cls, runner: CliRunner):
        """Test set command with no options shows help."""
        mock_resolve_entity_card.return_value = _build_entity_card()
        mock_host_client_cls.return_value = MagicMock()

        result = runner.invoke(entity_command, ["set", "-e", "entity1"])

        assert result.exit_code == 0
        assert "No updates provided" in result.output

    @patch("fp.utils.storage.get_storage_manager")
    @patch("aln.cli.entity.HostClient")
    @patch("aln.cli.entity.resolve_entity_card")
    def test_set_with_json_payload(
        self,
        mock_resolve_entity_card,
        mock_host_client_cls,
        mock_get_storage,
        runner: CliRunner,
    ):
        """Test set command with JSON payload."""
        entity_card = _build_entity_card()
        mock_resolve_entity_card.return_value = entity_card

        mock_storage = MagicMock()
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_client = MagicMock()
        mock_client.entity_update.return_value = entity_card
        mock_host_client_cls.return_value = mock_client

        result = runner.invoke(
            entity_command,
            ["set", "-e", "entity1", "-p", '{"visible": true, "enabled": false}'],
        )

        assert result.exit_code == 0
        call_kwargs = mock_client.entity_update.call_args.kwargs
        assert call_kwargs["update_request"].visible is True
        assert call_kwargs["update_request"].enabled is False
