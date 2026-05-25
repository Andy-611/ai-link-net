"""Tests for pay CLI command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from aln.cli.pay import command as pay_command
from fp import EntityCard, FPAddress
from fp.utils.storage import EntityKeyInfo, EntityMeta


def _build_entity_card(
    *,
    name: str,
    entity_uid: str,
    host_uid: str,
) -> EntityCard:
    """Build one entity card for pay CLI tests."""
    return EntityCard(
        name=name,
        address=FPAddress(address=f"{host_uid}:{entity_uid}"),
        kind="agent",
        sign_public_key="key",
        encrypt_public_key="key",
        description="",
        is_public=True,
        entity_uid=entity_uid,
        host_uid=host_uid,
    )


class _FixedUuid:
    hex = "1234567890abcdef1234567890abcdef"


def _build_entity_meta(*, entity_uid: str, host_uid: str, owner: str | None) -> EntityMeta:
    """Build one entity metadata record for CLI tests."""
    return EntityMeta(
        uid=entity_uid,
        name="Codex-1",
        kind="agent",
        host_uid=host_uid,
        address=f"{host_uid}:{entity_uid}",
        keys=EntityKeyInfo(
            sign_public_key="sign",
            encrypt_public_key="encrypt",
            key_file=f"keys/entities/{entity_uid}.key",
        ),
        mailbox_path=f"/tmp/{entity_uid}.jsonl",
        owner=owner,
    )


@patch("aln.cli.pay.trade_send")
@patch("aln.cli.pay.resolve_entity_card")
@patch("aln.cli.pay.uuid4", return_value=_FixedUuid())
def test_collect_command_uses_unique_direct_payment_id(
    _mock_uuid4: MagicMock,
    mock_resolve_entity_card: MagicMock,
    mock_trade_send: MagicMock,
) -> None:
    """Direct collect should use a fresh payment id instead of a deterministic one."""
    runner = CliRunner()
    payee_card = _build_entity_card(name="Codex-1", entity_uid="a261b2fc", host_uid="7135169c")
    payer_card = _build_entity_card(name="Claude-1", entity_uid="183fb458", host_uid="7135169c")
    mock_resolve_entity_card.side_effect = [payer_card, payee_card]
    mock_trade_send.return_value = {}

    result = runner.invoke(
        pay_command,
        [
            "collect",
            "-e",
            "7135169c:a261b2fc",
            "--payer",
            "7135169c:183fb458",
            "--amount",
            "100",
            "--receipt",
            "https://pay.example.com/codex",
        ],
    )

    assert result.exit_code == 0
    mock_trade_send.assert_called_once()
    call_args = mock_trade_send.call_args
    payload = call_args.args[2]
    assert call_args.kwargs["to_entity"] == "183fb458"
    assert payload["payment_id"] == "pay_1234567890ab"
    assert payload["payment_id"] != "pay_a261b2fc_100"


@patch("aln.cli.pay.trade_send")
@patch("aln.cli.pay.resolve_entity_card")
@patch("aln.cli.pay.get_storage_manager")
@patch("aln.cli.pay.uuid4", return_value=_FixedUuid())
def test_collect_command_allows_missing_receipt_when_owner_can_provide(
    _mock_uuid4: MagicMock,
    mock_get_storage_manager: MagicMock,
    mock_resolve_entity_card: MagicMock,
    mock_trade_send: MagicMock,
) -> None:
    """DIRECT collect may omit receipt when payee owner will provide it."""
    runner = CliRunner()
    payee_card = _build_entity_card(name="Codex-1", entity_uid="a261b2fc", host_uid="7135169c")
    payer_card = _build_entity_card(name="Claude-1", entity_uid="183fb458", host_uid="7135169c")
    mock_resolve_entity_card.side_effect = [payer_card, payee_card]
    mock_trade_send.return_value = {}
    mock_get_storage_manager.return_value.load_entity_meta.return_value = _build_entity_meta(
        entity_uid="a261b2fc",
        host_uid="7135169c",
        owner="7135169c:owner0001",
    )

    result = runner.invoke(
        pay_command,
        [
            "collect",
            "-e",
            "7135169c:a261b2fc",
            "--payer",
            "7135169c:183fb458",
            "--amount",
            "100",
        ],
    )

    assert result.exit_code == 0
    payload = mock_trade_send.call_args.args[2]
    assert payload["receipt_info"] == "owner_will_provide"


@patch("aln.cli.pay.trade_send")
@patch("aln.cli.pay.resolve_entity_card")
@patch("aln.cli.pay.get_storage_manager")
def test_collect_command_requires_receipt_without_owner(
    mock_get_storage_manager: MagicMock,
    mock_resolve_entity_card: MagicMock,
    mock_trade_send: MagicMock,
) -> None:
    """DIRECT collect still requires receipt when payee has no owner."""
    runner = CliRunner()
    payee_card = _build_entity_card(name="Codex-1", entity_uid="a261b2fc", host_uid="7135169c")
    payer_card = _build_entity_card(name="Claude-1", entity_uid="183fb458", host_uid="7135169c")
    mock_resolve_entity_card.side_effect = [payer_card, payee_card]
    mock_get_storage_manager.return_value.load_entity_meta.return_value = _build_entity_meta(
        entity_uid="a261b2fc",
        host_uid="7135169c",
        owner=None,
    )

    result = runner.invoke(
        pay_command,
        [
            "collect",
            "-e",
            "7135169c:a261b2fc",
            "--payer",
            "7135169c:183fb458",
            "--amount",
            "100",
        ],
    )

    assert result.exit_code != 0
    assert "--receipt is required for DIRECT mode" in result.output
    mock_trade_send.assert_not_called()
