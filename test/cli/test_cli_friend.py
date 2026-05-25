"""Tests for friend CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from aln.cli.friend import command as friend_command
from fp import EntityCard, FPAddress


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


def _build_entity_card(
    *,
    name: str,
    entity_uid: str,
    host_uid: str,
    kind: str = "agent",
) -> EntityCard:
    """Build one entity card for test stubs."""
    return EntityCard(
        name=name,
        address=FPAddress(address=f"{host_uid}:{entity_uid}"),
        kind=kind,
        sign_public_key="key",
        encrypt_public_key="key",
        description="",
        is_public=True,
        entity_uid=entity_uid,
        host_uid=host_uid,
    )


class TestFriendAdd:
    """Test friend add command."""

    @patch("fp.utils.storage.get_storage_manager")
    @patch("aln.cli.friend.HostClient")
    @patch("aln.cli.friend.resolve_entity_card")
    def test_add_friend_by_address(
        self,
        mock_resolve_entity_card,
        mock_host_client_cls,
        mock_get_storage,
        runner: CliRunner,
    ):
        """Test adding friend by resolved entity address."""
        from_card = _build_entity_card(name="alice", entity_uid="alice_uid", host_uid="host1")
        to_card = _build_entity_card(
            name="bob",
            entity_uid="bob_uid",
            host_uid="host2",
            kind="human",
        )
        mock_resolve_entity_card.side_effect = [from_card, to_card]

        mock_storage = MagicMock()
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_client = MagicMock()
        mock_client.friend_add.return_value = {"status": "success"}
        mock_host_client_cls.return_value = mock_client

        result = runner.invoke(
            friend_command,
            ["add", "--entity", "alice", "--to", "host2:bob"],
        )

        assert result.exit_code == 0
        assert "delivered to recipient mailbox" in result.output
        call_kwargs = mock_client.friend_add.call_args.kwargs
        assert call_kwargs["from_entity"] == "alice_uid"
        assert call_kwargs["to_address"] == "host2:bob_uid"

    @patch("fp.utils.storage.get_storage_manager")
    @patch("aln.cli.friend.HostClient")
    @patch("aln.cli.friend.resolve_entity_card")
    def test_add_friend_by_name(
        self,
        mock_resolve_entity_card,
        mock_host_client_cls,
        mock_get_storage,
        runner: CliRunner,
    ):
        """Test adding friend with name-like target input."""
        from_card = _build_entity_card(name="alice", entity_uid="alice_uid", host_uid="host1")
        to_card = _build_entity_card(
            name="Bob",
            entity_uid="bob_uid",
            host_uid="host2",
            kind="human",
        )
        mock_resolve_entity_card.side_effect = [from_card, to_card]

        mock_storage = MagicMock()
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_client = MagicMock()
        mock_client.friend_add.return_value = {"status": "success"}
        mock_host_client_cls.return_value = mock_client

        result = runner.invoke(
            friend_command,
            ["add", "--entity", "alice", "--to", "Bob"],
        )

        assert result.exit_code == 0
        assert "recipient-side owner review" in result.output
        call_kwargs = mock_client.friend_add.call_args.kwargs
        assert call_kwargs["to_address"] == "host2:bob_uid"

    @patch("aln.cli.friend.resolve_entity_card")
    def test_add_friend_name_not_found(self, mock_resolve_entity_card, runner: CliRunner):
        """Test adding friend when target entity is not found."""
        from_card = _build_entity_card(name="alice", entity_uid="alice_uid", host_uid="host1")
        mock_resolve_entity_card.side_effect = [
            from_card,
            click.ClickException("Entity not found: NonExistent"),
        ]

        result = runner.invoke(
            friend_command,
            ["add", "--entity", "alice", "--to", "NonExistent"],
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    @patch("aln.cli.friend.resolve_entity_card")
    def test_add_friend_multiple_matches(self, mock_resolve_entity_card, runner: CliRunner):
        """Test adding friend when target input maps to multiple entities."""
        from_card = _build_entity_card(name="alice", entity_uid="alice_uid", host_uid="host1")
        mock_resolve_entity_card.side_effect = [
            from_card,
            click.ClickException("Multiple entities matched 'Bob'."),
        ]

        result = runner.invoke(
            friend_command,
            ["add", "--entity", "alice", "--to", "Bob"],
        )

        assert result.exit_code != 0
        assert "Multiple" in result.output

    @patch("fp.utils.storage.get_storage_manager")
    @patch("aln.cli.friend.HostClient")
    @patch("aln.cli.friend.resolve_entity_card")
    def test_add_friend_with_text(
        self,
        mock_resolve_entity_card,
        mock_host_client_cls,
        mock_get_storage,
        runner: CliRunner,
    ):
        """Test adding friend with custom text."""
        from_card = _build_entity_card(name="alice", entity_uid="alice_uid", host_uid="host1")
        to_card = _build_entity_card(name="bob", entity_uid="bob_uid", host_uid="host2")
        mock_resolve_entity_card.side_effect = [from_card, to_card]

        mock_storage = MagicMock()
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_client = MagicMock()
        mock_client.friend_add.return_value = {"status": "success"}
        mock_host_client_cls.return_value = mock_client

        result = runner.invoke(
            friend_command,
            ["add", "--entity", "alice", "--to", "host2:bob", "--text", "Let's be friends!"],
        )

        assert result.exit_code == 0
        call_kwargs = mock_client.friend_add.call_args.kwargs
        assert call_kwargs["text"] == "Let's be friends!"


class TestFriendList:
    """Test friend list command."""

    @patch("fp.utils.storage.get_storage_manager")
    @patch("aln.cli.friend.HostClient")
    @patch("aln.cli.friend.resolve_entity_card")
    def test_list_friends(
        self,
        mock_resolve_entity_card,
        mock_host_client_cls,
        mock_get_storage,
        runner: CliRunner,
    ):
        """Test listing friends for an entity."""
        from_card = _build_entity_card(name="alice", entity_uid="alice_uid", host_uid="host1")
        mock_resolve_entity_card.return_value = from_card

        mock_storage = MagicMock()
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_client = MagicMock()
        friend1 = _build_entity_card(name="Bob", entity_uid="bob", host_uid="host1", kind="human")
        friend2 = _build_entity_card(name="Charlie", entity_uid="charlie", host_uid="host1")
        mock_client.entity_friends.return_value = [friend1, friend2]
        mock_host_client_cls.return_value = mock_client

        result = runner.invoke(friend_command, ["list", "-e", "alice"])

        assert result.exit_code == 0
        mock_client.entity_friends.assert_called_once_with(entity_uid="alice_uid")

    @patch("fp.utils.storage.get_storage_manager")
    @patch("aln.cli.friend.HostClient")
    @patch("aln.cli.friend.resolve_entity_card")
    def test_list_no_friends(
        self,
        mock_resolve_entity_card,
        mock_host_client_cls,
        mock_get_storage,
        runner: CliRunner,
    ):
        """Test list when entity has no friends."""
        from_card = _build_entity_card(name="alice", entity_uid="alice_uid", host_uid="host1")
        mock_resolve_entity_card.return_value = from_card

        mock_storage = MagicMock()
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_client = MagicMock()
        mock_client.entity_friends.return_value = []
        mock_host_client_cls.return_value = mock_client

        result = runner.invoke(friend_command, ["list", "-e", "alice"])

        assert result.exit_code == 0
