"""`aln health` command."""

from __future__ import annotations

import click

from aln.app.service import HostClient

from .misc.printer import CliPrinter
from .misc.wrappers import cli_exception_wrapper, get_cli_printer, get_host_client


@click.command(name="health", context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--host",
    "host_name",
    default="default",
    help="Host name to check (default: default)",
)
@cli_exception_wrapper(error_message="Failed to check health")
@get_host_client
@get_cli_printer
def command(
    host_name: str,
    client: HostClient,
    cli_printer: CliPrinter,
) -> None:
    """Check health of a running host via API."""
    del host_name
    health = client.check_health()
    cli_printer.print(health)
