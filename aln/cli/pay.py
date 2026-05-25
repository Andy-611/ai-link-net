"""`aln pay` command group — payment operations."""

from __future__ import annotations

from uuid import uuid4

import click
from fp.utils.storage import EntityMeta, get_storage_manager

from .misc.clistyle import PayCLIStyle
from .misc.printer import CliPrinter
from .misc.wrappers import (
    cli_exception_wrapper,
    get_cli_printer,
    resolve_arbiter_client,
    resolve_entity_card,
    trade_send,
)


@click.group(
    name="pay",
    cls=PayCLIStyle,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.pass_context
def command(ctx: click.Context) -> None:
    """Payment operations — collect, confirm, balance.

\b
Examples:
  # Initiate payment collection
  aln pay collect -e bd19e57d --payer a552e88d --amount 100 --receipt "https://pay.me/alice"
  # Confirm payment received
  aln pay confirm -e bd19e57d --id pay_abc123
  # Check balance
  aln pay balance -e bd19e57d
  # List all payments
  aln pay list -e bd19e57d

\b
Owner Approval:
  Payment actions may enter an owner approval flow.
  When you see a message saying the message needs owner review, it means:
    owner 通过后会自动继续发送
    owner 驳回则终止发送
    结果会再通过 mail 通知你
  不要轮询，等待后续通知即可。

  DIRECT collect special case:
    如果当前 Entity 有 owner，DIRECT 模式下 owner 可以在审批时补充或替换最终收款信息。
    也就是说，Entity 不必先拿到最终收款链接/二维码才能发起 collect。
    当前 CLI 已支持省略 --receipt；如果该 Entity 有 owner，
    则会自动使用 owner 审批占位并在审批时补充最终收款信息。
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _print_payments(cli_printer: CliPrinter, data: dict) -> None:
    """Print payments from trade_send response."""
    payments = data.get("payments", {})
    if not payments:
        return
    for pid, p in payments.items():
        status = p.get("status", "?")
        amount = p.get("amount", 0)
        method = p.get("method", "?")
        cli_printer.echo(f"  [{pid}] {method} | {status} | amount={amount}")


def _new_direct_payment_id() -> str:
    """Generate one unique payment id for a direct collection."""
    return f"pay_{uuid4().hex[:12]}"


def _load_entity_meta(entity_uid: str) -> EntityMeta | None:
    """Load one local entity metadata record."""
    return get_storage_manager().load_entity_meta(entity_uid)


def _resolve_receipt_info(
    *,
    receipt: str | None,
    escrow: bool,
    payee_entity_uid: str,
) -> str:
    """Resolve final receipt info for one pay collect invocation."""
    normalized = receipt.strip() if isinstance(receipt, str) else ""
    if normalized:
        return normalized

    if escrow:
        raise click.ClickException("--receipt is required in ESCROW mode.")

    payee_meta = _load_entity_meta(payee_entity_uid)
    if payee_meta is not None and payee_meta.owner:
        return "owner_will_provide"

    raise click.ClickException(
        "--receipt is required for DIRECT mode unless the payee entity has an owner who will provide it during approval."
    )


@command.command("collect")
@click.option("-e", "--entity", "entity_spec", required=True, help="Payee entity (who collects)")
@click.option("--payer", required=True, help="Payer entity name or uid")
@click.option("--amount", required=True, type=float, help="Payment amount")
@click.option("--method", type=click.Choice(["qr_code", "pay_link", "bank", "crypto", "gateway"], case_sensitive=False), default="pay_link", help="Payment method")
@click.option(
    "--receipt",
    required=False,
    help=(
        "Receipt info (link, QR data, etc.). "
        "Required in ESCROW mode and in DIRECT mode without owner approval. "
        "Optional in DIRECT owner-approval flow, where owner may provide or replace the final receipt info."
    ),
)
@click.option("--contract", "contract_id", default=None, help="Associated contract ID")
@click.option("--escrow", is_flag=True, default=False, help="ESCROW mode: send PAY_COLLECT to Arbiter (default is DIRECT to payer)")
@cli_exception_wrapper(error_message="Failed to collect payment")
@get_cli_printer
def collect_command(
    entity_spec: str,
    payer: str,
    amount: float,
    method: str,
    receipt: str,
    contract_id: str | None,
    escrow: bool,
    cli_printer: CliPrinter,
) -> None:
    """Initiate payment collection (payee sends receipt info to payer).

    Default is DIRECT mode — PAY_COLLECT goes directly to payer.
    Use --escrow to send through Arbiter instead.
    If this entity has an owner, DIRECT mode may enter owner approval first.
    In that flow, owner can provide or replace the final receipt info during approval,
    so --receipt may be omitted entirely.

    Examples:

    \b
      # Payee collects 100 from payer (direct, default)
      aln pay collect -e 1e988b99 --payer 4e591b23 --amount 100 \\
          --receipt "https://pay.me/bob"

    \b
      # Collect via QR code
      aln pay collect -e 1e988b99 --payer 4e591b23 --amount 200 \\
          --method qr_code --receipt "weixin://wxpay/s/abc123"

    \b
      # Escrow mode: send to Arbiter
      aln pay collect -e 4e591b23 --payer 4e591b23 --amount 1000 \\
          --receipt "deposit" --escrow

    \b
      # Collect linked to a contract
      aln pay collect -e 1e988b99 --payer 4e591b23 --amount 300 \\
          --receipt "https://pay.me/bob" --contract ctr_9d3f1a

    \b
      # Owner will provide the final receipt info during DIRECT approval
      aln pay collect -e 1e988b99 --payer 4e591b23 --amount 300 \\
          --contract ctr_9d3f1a
    """
    payer_card = resolve_entity_card(payer)
    payee_card = resolve_entity_card(entity_spec)
    receipt_info = _resolve_receipt_info(
        receipt=receipt,
        escrow=escrow,
        payee_entity_uid=payee_card.entity_uid,
    )

    payload: dict = {
        "payer": {"address": payer_card.address.address},
        "payee": {"address": payee_card.address.address},
        "amount": amount,
        "method": method,
        "receipt_info": receipt_info,
    }
    if contract_id:
        payload["contract_id"] = contract_id

    if escrow:
        result = trade_send(entity_spec, "pay_collect", payload)
        if result.get("status_message"):
            cli_printer.echo(result["status_message"])
        else:
            cli_printer.echo("Payment created:")
            _print_payments(cli_printer, result)
    else:
        payload["payment_id"] = _new_direct_payment_id()
        result = trade_send(entity_spec, "pay_collect", payload, to_entity=payer_card.entity_uid)
        if result.get("status_message"):
            cli_printer.echo(result["status_message"])
        else:
            cli_printer.echo(f"PAY_COLLECT sent to payer ({payer_card.name}):")
            cli_printer.echo(f"  payment_id={payload['payment_id']}, amount={amount}, method={method}")


@command.command("confirm")
@click.option("-e", "--entity", "entity_spec", required=True, help="Entity confirming receipt")
@click.option("--id", "payment_id", required=True, help="Payment ID")
@cli_exception_wrapper(error_message="Failed to confirm payment")
@get_cli_printer
def confirm_command(entity_spec: str, payment_id: str, cli_printer: CliPrinter) -> None:
    """Confirm receipt of payment (PAY_CONFIRM_RECEIPT).

    Examples:

    \b
      # Payee confirms they received the payment
      aln pay confirm -e 1e988b99 --id pay_abc123

    \b
      # Arbiter confirms a deposit was received
      aln pay confirm -e 7c3d5e9a --id pay_xyz
    """
    result = trade_send(entity_spec, "pay_confirm_receipt", {"payment_id": payment_id})
    status_message = result.get("status_message")
    if isinstance(status_message, str) and status_message:
        cli_printer.echo(status_message)
    else:
        cli_printer.echo("Payment confirmation sent:")
        _print_payments(cli_printer, result)


@command.command("list")
@click.option("-e", "--entity", "entity_spec", required=True, help="Entity to query payments for")
@cli_exception_wrapper(error_message="Failed to list payments")
@get_cli_printer
def list_command(entity_spec: str, cli_printer: CliPrinter) -> None:
    """List all payments.

    Examples:

    \b
      # List all payments visible to this entity
      aln pay list -e 4e591b23
    """
    card = resolve_entity_card(entity_spec)
    client = resolve_arbiter_client(card)
    payments = client.trade_payments()
    if not payments:
        cli_printer.echo("No payments")
        return
    cli_printer.echo(f"Payments ({len(payments)}):")
    for p in payments:
        pid = p.get("payment_id", "?")
        status = p.get("status", "?")
        amount = p.get("amount", 0)
        method = p.get("method", "?")
        contract_id = p.get("contract_id", "")
        cli_printer.echo(f"  [{pid}] {method} | {status} | amount={amount} | contract={contract_id}")


@command.command("balance")
@click.option("-e", "--entity", "entity_spec", required=True, help="Entity to check balance for")
@cli_exception_wrapper(error_message="Failed to get balance")
@get_cli_printer
def balance_command(entity_spec: str, cli_printer: CliPrinter) -> None:
    """Query entity balance on Arbiter's ledger.

    Shows balance, available, and frozen amounts.

    Examples:

    \b
      # Check entity balance
      aln pay balance -e 4e591b23

    \b
      # Check an agent's balance (full address)
      aln pay balance -e a3b7c9d0:7c3d5e9a
    """
    card = resolve_entity_card(entity_spec)
    client = resolve_arbiter_client(card)
    data = client.trade_balance(card.name)
    cli_printer.echo(
        f"  {data['entity_name']}: "
        f"balance={data['balance']}, available={data['available']}, frozen={data['frozen']}"
    )
