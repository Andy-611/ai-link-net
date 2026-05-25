"""`aln contract` command group — contract lifecycle operations."""

from __future__ import annotations

import json
import time

import click

from .misc.clistyle import ContractCLIStyle
from .misc.printer import CliPrinter
from .misc.wrappers import (
    cli_exception_wrapper,
    get_cli_printer,
    resolve_arbiter_client,
    resolve_entity_card,
    trade_send,
)


def _parse_artifact_specs(artifact_specs: tuple[str, ...]) -> list[dict]:
    artifacts: list[dict] = []
    for raw in artifact_specs:
        parts = [part.strip() for part in raw.split("|")]
        if len(parts) < 2 or not parts[0] or not parts[1]:
            raise click.ClickException(
                "Invalid --artifact. Expected format: kind|uri|label|digest",
            )
        artifact: dict[str, object] = {
            "kind": parts[0],
            "uri": parts[1],
        }
        if len(parts) >= 3 and parts[2]:
            artifact["label"] = parts[2]
        if len(parts) >= 4 and parts[3]:
            artifact["digest"] = parts[3]
        artifacts.append(artifact)
    return artifacts


def _build_execution_cost_payload(
    *,
    actor_address: str,
    recorded_at: float,
    provider: str | None,
    model: str | None,
    phase: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    cost_usd: float | None,
    runtime_ms: int | None,
    notes: str | None,
) -> list[dict]:
    if all(
        value is None
        for value in (
            provider,
            model,
            phase,
            input_tokens,
            output_tokens,
            cost_usd,
            runtime_ms,
            notes,
        )
    ):
        return []

    payload: dict[str, object] = {
        "actor": {"address": actor_address},
        "recorded_at": recorded_at,
    }
    if provider is not None:
        payload["provider"] = provider
    if model is not None:
        payload["model"] = model
    if phase is not None:
        payload["phase"] = phase
    if input_tokens is not None:
        payload["input_tokens"] = input_tokens
    if output_tokens is not None:
        payload["output_tokens"] = output_tokens
    if cost_usd is not None:
        payload["cost_usd"] = cost_usd
    if runtime_ms is not None:
        payload["runtime_ms"] = runtime_ms
    if notes is not None:
        payload["notes"] = notes
    return [payload]


@click.group(
    name="contract",
    cls=ContractCLIStyle,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.pass_context
def command(ctx: click.Context) -> None:
    """Contract lifecycle management.

\b
Lifecycle: create → approve (both parties) → complete → accept → settle
Examples:
  # Create a contract (party_a hires party_b)
  aln contract create -e bd19e57d --to a552e88d --title "Build website" --amount 1000
  # Counterparty approves
  aln contract approve -e a552e88d --id ctr_9d3f1a
  # Worker submits completion
  aln contract complete -e a552e88d --id ctr_9d3f1a
  # Client accepts deliverables
  aln contract accept -e bd19e57d --id ctr_9d3f1a
  # List all contracts
  aln contract list -e bd19e57d
  # View contract details
  aln contract status -e bd19e57d --id ctr_9d3f1a

\b
Owner Approval:
  Contract actions (create, approve, complete, accept, etc.) may enter
  an owner approval flow. When you see a message saying the message
  needs owner review, it means:
    owner 通过后会自动继续发送
    owner 驳回则终止发送
    结果会再通过 mail 通知你
  不要轮询，等待后续通知即可。
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _print_contracts(cli_printer: CliPrinter, data: dict) -> None:
    """Print contracts from trade_send response."""
    contracts = data.get("contracts", {})
    if not contracts:
        return
    for cid, c in contracts.items():
        status = c.get("status", "?")
        title = c.get("title", "")
        amount = c.get("amount", 0)
        cli_printer.echo(f"  [{cid}] {title} | {status} | amount={amount}")


def _print_trade_result(cli_printer: CliPrinter, data: dict, default_message: str) -> None:
    """Print trade result with server status message when present."""
    status_message = data.get("status_message")
    cli_printer.echo(status_message if isinstance(status_message, str) and status_message else default_message)
    _print_contracts(cli_printer, data)


@command.command("create")
@click.option("-e", "--entity", "entity_spec", required=True, help="Creator entity")
@click.option("--to", "to_spec", required=True, help="Counterparty entity (party_b)")
@click.option("--title", required=True, help="Contract title")
@click.option("--amount", required=True, type=float, help="Contract amount")
@click.option("--mode", type=click.Choice(["escrow", "direct"], case_sensitive=False), default="direct", help="Funding mode")
@click.option("--description", "-d", default="", help="Contract description")
@cli_exception_wrapper(error_message="Failed to create contract")
@get_cli_printer
def create_command(
    entity_spec: str,
    to_spec: str,
    title: str,
    amount: float,
    mode: str,
    description: str,
    cli_printer: CliPrinter,
) -> None:
    """Create a new contract.

    party_a (creator) hires party_b (counterparty) to do work.

    Examples:

    \b
      # Create a direct-pay contract (default mode)
      aln contract create -e 4e591b23 --to 1e988b99 \\
          --title "Build website" --amount 1000 \\
          -d "Responsive landing page with 3 sections"

    \b
      # Create an escrow contract (currently unsupported by default Arbiter)
      aln contract create -e 4e591b23 --to 7c3d5e9a \\
          --title "Data analysis" --amount 500 --mode escrow

    \b
      # Cross-host contract
      aln contract create -e a3b7c9d0:4e591b23 --to f5d2a1b8:1e988b99 \\
          --title "Logo design" --amount 300
    """
    creator_card = resolve_entity_card(entity_spec)
    to_card = resolve_entity_card(to_spec)

    payload = {
        "party_a": {"address": creator_card.address.address},
        "party_b": {"address": to_card.address.address},
        "title": title,
        "description": description,
        "amount": amount,
        "funding_mode": mode,
    }

    result = trade_send(entity_spec, "contract_create", payload)
    _print_trade_result(cli_printer, result, "Contract created:")


@command.command("approve")
@click.option("-e", "--entity", "entity_spec", required=True, help="Approver entity")
@click.option("--id", "contract_id", required=True, help="Contract ID")
@cli_exception_wrapper(error_message="Failed to approve contract")
@get_cli_printer
def approve_command(entity_spec: str, contract_id: str, cli_printer: CliPrinter) -> None:
    """Approve a contract (DRAFT → PENDING → ACTIVE).

    Both parties must approve before the contract becomes ACTIVE.

    Examples:

    \b
      # Counterparty approves the draft
      aln contract approve -e 1e988b99 --id ctr_9d3f1a

    \b
      # Creator approves (after counterparty)
      aln contract approve -e 4e591b23 --id ctr_9d3f1a
    """
    result = trade_send(entity_spec, "contract_approve", {"contract_id": contract_id})
    _print_trade_result(cli_printer, result, "Contract approved:")


@command.command("complete")
@click.option("-e", "--entity", "entity_spec", required=True, help="Completer entity (party_b)")
@click.option("--id", "contract_id", required=True, help="Contract ID")
@click.option("--reason", default=None, help="Delivery note / completion reason")
@click.option("--delivery-version", default=None, help="Structured delivery version, e.g. v1.0.0")
@click.option("--delivery-summary", default=None, help="Structured delivery summary")
@click.option(
    "--artifact",
    "artifact_specs",
    multiple=True,
    help="Delivery artifact as kind|uri|label|digest",
)
@click.option("--cost-provider", default=None, help="Execution cost provider, e.g. codex")
@click.option("--cost-model", default=None, help="Execution cost model")
@click.option("--cost-phase", default=None, help="Execution phase, e.g. implementation")
@click.option("--input-tokens", type=int, default=None, help="Input tokens used")
@click.option("--output-tokens", type=int, default=None, help="Output tokens used")
@click.option("--cost-usd", type=float, default=None, help="Execution cost in USD")
@click.option("--runtime-ms", type=int, default=None, help="Execution runtime in milliseconds")
@click.option("--cost-notes", default=None, help="Execution cost notes")
@cli_exception_wrapper(error_message="Failed to complete contract")
@get_cli_printer
def complete_command(
    entity_spec: str,
    contract_id: str,
    reason: str | None,
    delivery_version: str | None,
    delivery_summary: str | None,
    artifact_specs: tuple[str, ...],
    cost_provider: str | None,
    cost_model: str | None,
    cost_phase: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    cost_usd: float | None,
    runtime_ms: int | None,
    cost_notes: str | None,
    cli_printer: CliPrinter,
) -> None:
    """Submit work completion (ACTIVE → COMPLETING).

    Called by party_b (the worker) when work is done.

    Examples:

    \b
      # Worker (party_b) submits completed work
      aln contract complete -e 1e988b99 --id ctr_9d3f1a
    """
    sender_card = resolve_entity_card(entity_spec)
    now = time.time()
    payload = {"contract_id": contract_id}
    if reason:
        payload["reason"] = reason
    artifacts = _parse_artifact_specs(artifact_specs)
    if delivery_version or delivery_summary or artifacts:
        payload["delivery"] = {
            "delivery_id": "",
            "version": delivery_version or "delivery",
            "summary": delivery_summary or reason or "Delivery submitted",
            "artifacts": artifacts,
            "produced_by": {"address": sender_card.address.address},
            "produced_at": now,
        }
    execution_costs = _build_execution_cost_payload(
        actor_address=sender_card.address.address,
        recorded_at=now,
        provider=cost_provider,
        model=cost_model,
        phase=cost_phase,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        runtime_ms=runtime_ms,
        notes=cost_notes,
    )
    if execution_costs:
        payload["execution_costs"] = execution_costs
    result = trade_send(entity_spec, "contract_complete", payload)
    _print_trade_result(cli_printer, result, "Work submitted:")


@command.command("accept")
@click.option("-e", "--entity", "entity_spec", required=True, help="Acceptor entity (party_a)")
@click.option("--id", "contract_id", required=True, help="Contract ID")
@click.option("--reason", default=None, help="Acceptance note")
@cli_exception_wrapper(error_message="Failed to accept contract")
@get_cli_printer
def accept_command(
    entity_spec: str,
    contract_id: str,
    reason: str | None,
    cli_printer: CliPrinter,
) -> None:
    """Accept delivered work (COMPLETING → SETTLING).

    Called by party_a (the client) to approve the deliverables.

    Examples:

    \b
      # Client (party_a) accepts delivered work
      aln contract accept -e 4e591b23 --id ctr_9d3f1a
    """
    payload = {"contract_id": contract_id}
    if reason:
        payload["reason"] = reason
    result = trade_send(entity_spec, "contract_accept", payload)
    _print_trade_result(cli_printer, result, "Work accepted:")


@command.command("rework")
@click.option("-e", "--entity", "entity_spec", required=True, help="Entity requesting rework")
@click.option("--id", "contract_id", required=True, help="Contract ID")
@click.option("--reason", default=None, help="Rework reason")
@cli_exception_wrapper(error_message="Failed to request rework")
@get_cli_printer
def rework_command(entity_spec: str, contract_id: str, reason: str | None, cli_printer: CliPrinter) -> None:
    """Request rework (COMPLETING → ACTIVE).

    Called by party_a when deliverables need revision.

    Examples:

    \b
      # Request rework with a reason
      aln contract rework -e 4e591b23 --id ctr_9d3f1a \\
          --reason "Colors don't match the brand guide"

    \b
      # Request rework without reason
      aln contract rework -e 4e591b23 --id ctr_9d3f1a
    """
    result = trade_send(
        entity_spec, "contract_rework",
        {"contract_id": contract_id, "reason": reason or ""},
    )
    _print_trade_result(cli_printer, result, "Rework requested:")


@command.command("rate")
@click.option("-e", "--entity", "entity_spec", required=True, help="Rating entity")
@click.option("--id", "contract_id", required=True, help="Contract ID")
@click.option("--rating", required=True, type=click.IntRange(1, 5), help="Rating (1-5)")
@click.option("--review", default=None, help="Review text")
@cli_exception_wrapper(error_message="Failed to rate contract")
@get_cli_printer
def rate_command(
    entity_spec: str, contract_id: str, rating: int, review: str | None, cli_printer: CliPrinter,
) -> None:
    """Rate a contract.

    Either party can rate after settlement.

    Examples:

    \b
      # Rate with review text
      aln contract rate -e 4e591b23 --id ctr_9d3f1a --rating 5 \\
          --review "Excellent work, delivered on time"

    \b
      # Rate without review
      aln contract rate -e 1e988b99 --id ctr_9d3f1a --rating 4
    """
    result = trade_send(
        entity_spec, "contract_rate",
        {"contract_id": contract_id, "rating": rating, "review": review or ""},
    )
    _print_trade_result(cli_printer, result, f"Rated {rating}/5")


@command.command("amend")
@click.option("-e", "--entity", "entity_spec", required=True, help="Amender entity")
@click.option("--id", "contract_id", required=True, help="Contract ID")
@click.option("--amount", type=float, default=None, help="New amount")
@click.option("--title", default=None, help="New title")
@click.option("--description", "-d", default=None, help="New description")
@cli_exception_wrapper(error_message="Failed to amend contract")
@get_cli_printer
def amend_command(
    entity_spec: str, contract_id: str, amount: float | None, title: str | None,
    description: str | None, cli_printer: CliPrinter,
) -> None:
    """Amend a draft contract.

    Only DRAFT contracts can be amended.

    Examples:

    \b
      # Change the amount
      aln contract amend -e 4e591b23 --id ctr_9d3f1a --amount 1200

    \b
      # Change title and description
      aln contract amend -e 4e591b23 --id ctr_9d3f1a \\
          --title "Build website v2" -d "Updated scope with blog section"

    \b
      # Change multiple fields at once
      aln contract amend -e 4e591b23 --id ctr_9d3f1a \\
          --amount 1500 --title "Full website redesign"
    """
    payload: dict = {"contract_id": contract_id}
    if amount is not None:
        payload["amount"] = amount
    if title is not None:
        payload["title"] = title
    if description is not None:
        payload["description"] = description

    result = trade_send(entity_spec, "contract_amend", payload)
    _print_trade_result(cli_printer, result, "Contract amended:")


@command.command("cancel")
@click.option("-e", "--entity", "entity_spec", required=True, help="Canceller entity")
@click.option("--id", "contract_id", required=True, help="Contract ID")
@click.option("--reason", default=None, help="Cancel reason")
@cli_exception_wrapper(error_message="Failed to cancel contract")
@get_cli_printer
def cancel_command(entity_spec: str, contract_id: str, reason: str | None, cli_printer: CliPrinter) -> None:
    """Cancel a contract.

    Examples:

    \b
      # Cancel with a reason
      aln contract cancel -e 4e591b23 --id ctr_9d3f1a \\
          --reason "Project requirements changed"

    \b
      # Cancel without reason
      aln contract cancel -e 4e591b23 --id ctr_9d3f1a
    """
    result = trade_send(
        entity_spec, "contract_cancel",
        {"contract_id": contract_id, "reason": reason or ""},
    )
    _print_trade_result(cli_printer, result, "Contract cancelled:")


@command.command("list")
@click.option("-e", "--entity", "entity_spec", required=True, help="Entity to query contracts for")
@cli_exception_wrapper(error_message="Failed to list contracts")
@get_cli_printer
def list_command(entity_spec: str, cli_printer: CliPrinter) -> None:
    """List all contracts.

    Examples:

    \b
      # List all contracts visible to this entity
      aln contract list -e 4e591b23
    """
    card = resolve_entity_card(entity_spec)
    client = resolve_arbiter_client(card)
    contracts = client.trade_contracts()
    if not contracts:
        cli_printer.echo("No contracts")
        return
    cli_printer.echo(f"Contracts ({len(contracts)}):")
    for c in contracts:
        cid = c.get("contract_id", "?")
        status = c.get("status", "?")
        title = c.get("title", "")
        amount = c.get("amount", 0)
        mode = c.get("funding_mode", "?")
        cli_printer.echo(f"  [{cid}] {title} | {status} | {mode} | amount={amount}")


@command.command("status")
@click.option("-e", "--entity", "entity_spec", required=True, help="Entity to query contract for")
@click.option("--id", "contract_id", required=True, help="Contract ID")
@cli_exception_wrapper(error_message="Failed to get contract status")
@get_cli_printer
def status_command(entity_spec: str, contract_id: str, cli_printer: CliPrinter) -> None:
    """Get contract details.

    Examples:

    \b
      # View full contract details
      aln contract status -e 4e591b23 --id ctr_9d3f1a
    """
    card = resolve_entity_card(entity_spec)
    client = resolve_arbiter_client(card)
    contract = client.trade_contract(contract_id)
    cli_printer.echo(json.dumps(contract, indent=2, ensure_ascii=False))
