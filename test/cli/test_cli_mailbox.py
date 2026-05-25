"""Tests for mailbox CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from aln.cli.mailbox import command as mailbox_command
from fp import EntityCard, FPAddress


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_mail_entry() -> dict:
    """Create sample mail entry."""
    return {
        "mail": {
            "message_id": "msg123",
            "sender": {"address": "host1:alice"},
            "recipient": [{"address": "host2:bob"}],
            "message": {
                "kind": "invoke",
                "payload": {"text": "Hello Bob!"},
            },
            "signature": "sig",
        },
        "metadata": {
            "timestamp": "2026-01-01T10:00:00",
            "direction": "inbound",
            "is_read": False,
            "is_handled": False,
        },
    }


@pytest.fixture
def approval_status_mail_entry() -> dict:
    """Create approval status mail entry."""
    return {
        "mail": {
            "message_id": "msg_approval_123",
            "sender": {"address": "host1:system"},
            "recipient": [{"address": "host1:entity1"}],
            "message": {
                "kind": "approval_status",
                "payload": {
                    "request_id": "req_123",
                    "original_kind": "contract_accept",
                    "message": "你收到一条合同状态消息【status update】；当前由 owner 处理或审核中；结果会通知你；你可以提醒 owner。",
                    "flow_side": "inbound",
                    "status": "pending",
                    "audience": "self",
                    "original_preview": "status update",
                },
            },
            "signature": "sig",
        },
        "metadata": {
            "timestamp": "2026-01-01T10:00:00",
            "direction": "inbound",
            "is_read": False,
            "is_handled": False,
        },
    }


def _build_entity_card() -> EntityCard:
    """Build one entity card for test stubs."""
    return EntityCard(
        name="Entity1",
        address=FPAddress(address="host1:entity1"),
        kind="agent",
        sign_public_key="key",
        encrypt_public_key="key",
        description="",
        is_public=True,
        entity_uid="entity1",
        host_uid="host1",
    )


class TestMailboxList:
    """Test mailbox list command."""

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.mailbox.Mailbox")
    @patch("aln.cli.mailbox.resolve_entity_card")
    def test_list_unread_messages(
        self,
        mock_resolve_entity_card,
        mock_mailbox_cls,
        mock_get_storage,
        runner: CliRunner,
        sample_mail_entry,
    ):
        """Test listing unread messages (default)."""
        mock_resolve_entity_card.return_value = _build_entity_card()

        mock_storage = MagicMock()
        mock_storage._entity_mailbox_path.return_value = Path("/tmp/mailbox")
        mock_get_storage.return_value = mock_storage

        mock_mailbox = MagicMock()
        mock_mailbox.list_mails.return_value = [sample_mail_entry]
        mock_mailbox_cls.return_value = mock_mailbox

        result = runner.invoke(mailbox_command, ["list", "-e", "entity1"])

        assert result.exit_code == 0
        assert "Found 1 message" in result.output
        call_kwargs = mock_mailbox.list_mails.call_args.kwargs
        assert call_kwargs["is_read"] is False

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.mailbox.Mailbox")
    @patch("aln.cli.mailbox.resolve_entity_card")
    def test_list_all_messages(
        self,
        mock_resolve_entity_card,
        mock_mailbox_cls,
        mock_get_storage,
        runner: CliRunner,
        sample_mail_entry,
    ):
        """Test listing all messages."""
        mock_resolve_entity_card.return_value = _build_entity_card()

        mock_storage = MagicMock()
        mock_storage._entity_mailbox_path.return_value = Path("/tmp/mailbox")
        mock_get_storage.return_value = mock_storage

        mock_mailbox = MagicMock()
        mock_mailbox.list_mails.return_value = [sample_mail_entry, sample_mail_entry]
        mock_mailbox_cls.return_value = mock_mailbox

        result = runner.invoke(mailbox_command, ["list", "-e", "entity1", "--all"])

        assert result.exit_code == 0
        assert "Found 2 message" in result.output
        call_kwargs = mock_mailbox.list_mails.call_args.kwargs
        assert call_kwargs["is_read"] is None

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.mailbox.Mailbox")
    @patch("aln.cli.mailbox.resolve_entity_card")
    def test_list_read_messages(
        self,
        mock_resolve_entity_card,
        mock_mailbox_cls,
        mock_get_storage,
        runner: CliRunner,
    ):
        """Test listing only read messages."""
        mock_resolve_entity_card.return_value = _build_entity_card()

        mock_storage = MagicMock()
        mock_storage._entity_mailbox_path.return_value = Path("/tmp/mailbox")
        mock_get_storage.return_value = mock_storage

        mock_mailbox = MagicMock()
        mock_mailbox.list_mails.return_value = []
        mock_mailbox_cls.return_value = mock_mailbox

        result = runner.invoke(mailbox_command, ["list", "-e", "entity1", "--read"])

        assert result.exit_code == 0
        call_kwargs = mock_mailbox.list_mails.call_args.kwargs
        assert call_kwargs["is_read"] is True

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.mailbox.Mailbox")
    @patch("aln.cli.mailbox.resolve_entity_card")
    def test_list_inbound_messages(
        self,
        mock_resolve_entity_card,
        mock_mailbox_cls,
        mock_get_storage,
        runner: CliRunner,
    ):
        """Test listing only inbound messages."""
        mock_resolve_entity_card.return_value = _build_entity_card()

        mock_storage = MagicMock()
        mock_storage._entity_mailbox_path.return_value = Path("/tmp/mailbox")
        mock_get_storage.return_value = mock_storage

        mock_mailbox = MagicMock()
        mock_mailbox.list_mails.return_value = []
        mock_mailbox_cls.return_value = mock_mailbox

        result = runner.invoke(mailbox_command, ["list", "-e", "entity1", "--inbound"])

        assert result.exit_code == 0
        call_kwargs = mock_mailbox.list_mails.call_args.kwargs
        assert call_kwargs["direction"] == "inbound"

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.mailbox.Mailbox")
    @patch("aln.cli.mailbox.resolve_entity_card")
    def test_list_no_messages(
        self,
        mock_resolve_entity_card,
        mock_mailbox_cls,
        mock_get_storage,
        runner: CliRunner,
    ):
        """Test list when no messages found."""
        mock_resolve_entity_card.return_value = _build_entity_card()

        mock_storage = MagicMock()
        mock_storage._entity_mailbox_path.return_value = Path("/tmp/mailbox")
        mock_get_storage.return_value = mock_storage

        mock_mailbox = MagicMock()
        mock_mailbox.list_mails.return_value = []
        mock_mailbox_cls.return_value = mock_mailbox

        result = runner.invoke(mailbox_command, ["list", "-e", "entity1"])

        assert result.exit_code == 0
        assert "No messages found" in result.output

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.mailbox.Mailbox")
    @patch("aln.cli.mailbox.resolve_entity_card")
    def test_list_approval_status_messages_show_notification_preview(
        self,
        mock_resolve_entity_card,
        mock_mailbox_cls,
        mock_get_storage,
        runner: CliRunner,
        approval_status_mail_entry,
    ):
        """Approval status messages should show a readable notification preview."""
        mock_resolve_entity_card.return_value = _build_entity_card()

        mock_storage = MagicMock()
        mock_storage._entity_mailbox_path.return_value = Path("/tmp/mailbox")
        mock_get_storage.return_value = mock_storage

        mock_mailbox = MagicMock()
        mock_mailbox.list_mails.return_value = [approval_status_mail_entry]
        mock_mailbox_cls.return_value = mock_mailbox

        result = runner.invoke(mailbox_command, ["list", "-e", "entity1", "--all"])

        assert result.exit_code == 0
        assert "收信审批通知: status update" in result.output


class TestMailboxCheck:
    """Test mailbox check command."""

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.mailbox.Mailbox")
    @patch("aln.cli.mailbox.resolve_entity_card")
    def test_check_mail(
        self,
        mock_resolve_entity_card,
        mock_mailbox_cls,
        mock_get_storage,
        runner: CliRunner,
        sample_mail_entry,
    ):
        """Test checking a mail."""
        mock_resolve_entity_card.return_value = _build_entity_card()

        mock_storage = MagicMock()
        mock_storage._entity_mailbox_path.return_value = Path("/tmp/mailbox")
        mock_get_storage.return_value = mock_storage

        mock_mailbox = MagicMock()
        mock_mailbox.get_mail.return_value = sample_mail_entry
        mock_mailbox_cls.return_value = mock_mailbox

        result = runner.invoke(
            mailbox_command,
            ["check", "-e", "entity1", "--mail-id", "msg123"],
        )

        assert result.exit_code == 0
        assert "Marked as read" in result.output
        mock_mailbox.mark_as_read.assert_called_once_with("msg123")

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.mailbox.Mailbox")
    @patch("aln.cli.mailbox.resolve_entity_card")
    def test_check_mail_not_found(
        self,
        mock_resolve_entity_card,
        mock_mailbox_cls,
        mock_get_storage,
        runner: CliRunner,
    ):
        """Test checking non-existent mail."""
        mock_resolve_entity_card.return_value = _build_entity_card()

        mock_storage = MagicMock()
        mock_storage._entity_mailbox_path.return_value = Path("/tmp/mailbox")
        mock_get_storage.return_value = mock_storage

        mock_mailbox = MagicMock()
        mock_mailbox.get_mail.return_value = None
        mock_mailbox_cls.return_value = mock_mailbox

        result = runner.invoke(
            mailbox_command,
            ["check", "-e", "entity1", "--mail-id", "nonexist"],
        )

        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestMailboxReply:
    """Test mailbox reply command."""

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.mailbox.Mailbox")
    @patch("aln.cli.mailbox.HostClient")
    @patch("aln.cli.mailbox.resolve_entity_card")
    def test_reply_to_mail(
        self,
        mock_resolve_entity_card,
        mock_host_client_cls,
        mock_mailbox_cls,
        mock_get_storage,
        runner: CliRunner,
        sample_mail_entry,
    ):
        """Test replying to a mail."""
        mock_resolve_entity_card.return_value = _build_entity_card()

        mock_storage = MagicMock()
        mock_storage._entity_mailbox_path.return_value = Path("/tmp/mailbox")
        mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
        mock_get_storage.return_value = mock_storage

        mock_mailbox = MagicMock()
        mock_mailbox.get_mail.return_value = sample_mail_entry
        mock_mailbox_cls.return_value = mock_mailbox

        mock_client = MagicMock()
        mock_client.send_mail.return_value = {"ok": True}
        mock_host_client_cls.return_value = mock_client

        message_json = '{"kind": "invoke", "payload": {"text": "Hi Alice!"}}'
        result = runner.invoke(
            mailbox_command,
            ["reply", "-e", "entity1", "--mail-id", "msg123", "-m", message_json],
        )

        assert result.exit_code == 0
        assert "Reply sent" in result.output
        mock_mailbox.mark_as_handled.assert_called_once_with("msg123")
        mock_mailbox.save_outbound.assert_called_once()

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.mailbox.Mailbox")
    @patch("aln.cli.mailbox.resolve_entity_card")
    def test_reply_mail_not_found(
        self,
        mock_resolve_entity_card,
        mock_mailbox_cls,
        mock_get_storage,
        runner: CliRunner,
    ):
        """Test replying to non-existent mail."""
        mock_resolve_entity_card.return_value = _build_entity_card()

        mock_storage = MagicMock()
        mock_storage._entity_mailbox_path.return_value = Path("/tmp/mailbox")
        mock_get_storage.return_value = mock_storage

        mock_mailbox = MagicMock()
        mock_mailbox.get_mail.return_value = None
        mock_mailbox_cls.return_value = mock_mailbox

        message_json = '{"kind": "invoke", "payload": {"text": "Reply"}}'
        result = runner.invoke(
            mailbox_command,
            ["reply", "-e", "entity1", "--mail-id", "nonexist", "-m", message_json],
        )

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    @patch("aln.cli.misc.wrappers.get_storage_manager")
    @patch("aln.cli.mailbox.Mailbox")
    @patch("aln.cli.mailbox.resolve_entity_card")
    def test_reply_invalid_json(
        self,
        mock_resolve_entity_card,
        mock_mailbox_cls,
        mock_get_storage,
        runner: CliRunner,
        sample_mail_entry,
    ):
        """Test replying with invalid JSON."""
        mock_resolve_entity_card.return_value = _build_entity_card()

        mock_storage = MagicMock()
        mock_storage._entity_mailbox_path.return_value = Path("/tmp/mailbox")
        mock_get_storage.return_value = mock_storage

        mock_mailbox = MagicMock()
        mock_mailbox.get_mail.return_value = sample_mail_entry
        mock_mailbox_cls.return_value = mock_mailbox

        result = runner.invoke(
            mailbox_command,
            ["reply", "-e", "entity1", "--mail-id", "msg123", "-m", "invalid json"],
        )

        assert result.exit_code == 1
        assert "Invalid JSON" in result.output
