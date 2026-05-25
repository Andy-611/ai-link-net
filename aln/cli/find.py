"""`aln find` command - discover entities across the network."""

from __future__ import annotations

import click

from .misc.printer import CliPrinter
from .misc.wrappers import cli_exception_wrapper, get_cli_printer, resolve_entity_card

from aln.app import HostClient
from fp.utils.storage import get_storage_manager


@click.command(
    name="find",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option("-e", "--entity", "entity_spec", required=True, help="Entity whose host perspective to search from")
@click.option("--uid", help="Search by entity UID")
@click.option("--name", help="Search by entity name")
@click.option("--address", help="Search by entity address (host_uid:entity_uid)")
@click.option("--kind", help="Filter by entity kind (human, agent, host, etc)")
@cli_exception_wrapper(error_message="Failed to find entities")
@get_cli_printer
def command(
    entity_spec: str,
    uid: str | None,
    name: str | None,
    address: str | None,
    kind: str | None,
    cli_printer: CliPrinter,
) -> None:
    """Discover entities across the network from an entity's host perspective.

    -e takes FP address: host_uid:entity_uid or entity_uid (default host).

    Examples:

    \b
      # List all discoverable entities
      aln find -e bd19e57d

    \b
      # Search by name
      aln find -e bd19e57d --name Coder

    \b
      # Search by UID
      aln find -e bd19e57d --uid a552e88d

    \b
      # Search by full address
      aln find -e bd19e57d --address 12c9067b:a552e88d

    \b
      # Filter by kind
      aln find -e bd19e57d --kind agent

    \b
      # Full address format + kind filter
      aln find -e 1ec0ed94:bd19e57d --kind human
    """
    card = resolve_entity_card(entity_spec)
    storage = get_storage_manager()
    host_url = storage.get_host_url(card.host_uid)
    client = HostClient(base_url=host_url)

    entities = client.entity_search(uid=uid, name=name, address=address)

    if kind:
        entities = [e for e in entities if e.kind.lower() == kind.lower()]

    if not entities:
        cli_printer.echo("No entities found")
        return

    cli_printer.echo(f"Found {len(entities)} entit{'y' if len(entities) == 1 else 'ies'}:\n")
    cli_printer.print(entities)
