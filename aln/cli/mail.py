"""`aln mail` command - Send text messages between entities."""

from __future__ import annotations

import json
import sys

import click

from aln.app import HostClient

from .misc.printer import CliPrinter
from .misc.wrappers import cli_exception_wrapper, get_cli_printer, resolve_entity_card


@click.command(
    name="mail",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "-e",
    "--entity",
    "from_entity_spec",
    required=True,
    help="Sender entity (host:entity or entity). Examples: 'Alice', 'default:Alice'",
)
@click.option(
    "--to",
    "to_address_spec",
    required=True,
    help="Recipient ADDRESS (use 'host:entity' or registered entity name, NOT arbitrary names). Examples: 'Bob' (if registered), 'default:Bob', 'test1:Alice'",
)
@click.option(
    "-m",
    "--message",
    "message_json",
    required=True,
    help='Message JSON (supports legacy format or simple {"text": "..."})',
)
@cli_exception_wrapper(error_message="Failed to send mail")
@get_cli_printer
def command(
    from_entity_spec: str,
    to_address_spec: str,
    message_json: str,
    cli_printer: CliPrinter,
) -> None:
    """Send message — the ONLY way to reply to others and report to your owner.

    -e and --to take FP address: host_uid:entity_uid or entity_uid (default host).
    --to must be a valid entity address, use 'aln find' to discover entities first.

    Examples:

    \b
      # Send a text message (same host)
      aln mail -e bd19e57d --to 7d276024 -m '{"text": "Hello!"}'

    \b
      # Cross-host messaging
      aln mail -e 1ec0ed94:bd19e57d --to 12c9067b:a552e88d -m '{"text": "Hi!"}'

    \b
      # Discover first, then send
      aln find -e bd19e57d --name Coder
      aln mail -e bd19e57d --to a552e88d -m '{"text": "Write a sort algorithm"}'
    """
    from fp.utils.storage import get_storage_manager

    # 解析发送方和接收方的 entity cards
    from_card = resolve_entity_card(from_entity_spec)
    to_card = resolve_entity_card(to_address_spec)

    # 创建发送方的 client
    storage = get_storage_manager()
    from_host_url = storage.get_host_url(from_card.host_uid)
    client = HostClient(base_url=from_host_url)

    # 使用 to_card 的完整地址
    to_address = to_card.address.address

    # Parse message JSON
    try:
        message_data = json.loads(message_json)
    except json.JSONDecodeError as e:
        cli_printer.echo(f"✗ Invalid JSON message: {e}")
        sys.exit(1)

    if not isinstance(message_data, dict):
        cli_printer.echo("✗ Message must be a JSON object")
        sys.exit(1)

    # Extract text from message
    text = None
    session_id = None
    if "text" in message_data:
        text = message_data["text"]
    elif "payload" in message_data and isinstance(message_data["payload"], dict):
        text = message_data["payload"].get("text")
        raw_session_id = message_data["payload"].get("session_id")
        if isinstance(raw_session_id, str) and raw_session_id.strip():
            session_id = raw_session_id.strip()

    if session_id is None:
        raw_session_id = message_data.get("session_id")
        if isinstance(raw_session_id, str) and raw_session_id.strip():
            session_id = raw_session_id.strip()

    if not text:
        cli_printer.echo('✗ Message must contain "text" field or payload.text')
        sys.exit(1)

    # Use the new messages API endpoint
    try:
        send_kwargs = {
            "from_entity": from_card.entity_uid,
            "to_address": to_address,
            "text": text,
        }
        if session_id is not None:
            send_kwargs["session_id"] = session_id
        result = client.send_message(**send_kwargs)
        cli_printer.echo("✓ Message sent successfully")
        cli_printer.echo(f"  Message ID: {result.get('message_id', 'N/A')}")
        cli_printer.echo(f"  From: {from_entity_spec}")
        cli_printer.echo(f"  To: {to_address_spec}")
    except Exception as e:
        cli_printer.echo(f"✗ Failed to send message: {e}")
        sys.exit(1)
