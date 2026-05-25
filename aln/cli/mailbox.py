"""`aln mailbox` command group."""
# TODO: Create MailEntry and MailMetadata types to replace dict[str, Any]

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from fp.utils.storage import StorageManager

from aln.app import HostClient
from fp import FPAddress, Mail, Mailbox, Message

from .misc.clistyle import MailboxCLIStyle
from .misc.printer import CliPrinter
from .misc.wrappers import cli_exception_wrapper, get_cli_printer, get_storage, resolve_entity_card


def _get_mailbox_path(storage: StorageManager, entity_uid: str) -> Path:
    """Get mailbox path for entity."""
    return storage._entity_mailbox_path(entity_uid)


@click.group(
    name="mailbox",
    cls=MailboxCLIStyle,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.pass_context
def command(ctx: click.Context) -> None:
    """View conversation history and manage messages. Use this to recall context when unsure what was discussed.

\b
Examples:
  # List unread messages (default)
  aln mailbox list -e bd19e57d
  # List all messages
  aln mailbox list -e bd19e57d --all
  # List inbound messages only
  aln mailbox list -e bd19e57d --inbound
  # View message details and mark as read
  aln mailbox check -e bd19e57d --mail-id msg_4f8a2b
  # Reply to a message
  aln mailbox reply -e bd19e57d --mail-id msg_4f8a2b -m '{"text": "Got it"}'
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@command.command("list", help="List messages in mailbox.")
@click.option(
    "-e",
    "--entity",
    "entity_spec",
    required=True,
    help="Entity to query (host:entity or entity). Examples: 'Alice', 'default:Alice'",
)
@click.option(
    "--all",
    "show_all",
    is_flag=True,
    help="Show all messages (default: unread only)",
)
@click.option(
    "--read",
    "filter_read",
    is_flag=True,
    help="Show only read messages",
)
@click.option(
    "--unread",
    "filter_unread",
    is_flag=True,
    help="Show only unread messages",
)
@click.option(
    "--handled",
    "filter_handled",
    is_flag=True,
    help="Show only handled messages",
)
@click.option(
    "--unhandled",
    "filter_unhandled",
    is_flag=True,
    help="Show only unhandled messages",
)
@click.option(
    "--inbound",
    "filter_inbound",
    is_flag=True,
    help="Show only inbound messages",
)
@click.option(
    "--outbound",
    "filter_outbound",
    is_flag=True,
    help="Show only outbound messages",
)
@cli_exception_wrapper(error_message="Failed to list mailbox")
@get_storage
@get_cli_printer
def list_command(
    entity_spec: str,
    show_all: bool,
    filter_read: bool,
    filter_unread: bool,
    filter_handled: bool,
    filter_unhandled: bool,
    filter_inbound: bool,
    filter_outbound: bool,
    storage: StorageManager,
    cli_printer: CliPrinter,
) -> None:
    """List messages in entity's mailbox.

    By default only unread messages are shown.

    Examples:

    \b
      # Show unread messages (default)
      aln mailbox list -e 4e591b23

    \b
      # Show all messages
      aln mailbox list -e 4e591b23 --all

    \b
      # Show only inbound unread messages
      aln mailbox list -e 4e591b23 --inbound --unread

    \b
      # Show only outbound messages
      aln mailbox list -e 4e591b23 --outbound

    \b
      # Show read / handled messages
      aln mailbox list -e 4e591b23 --read
      aln mailbox list -e 4e591b23 --unhandled

    \b
      # Full address format
      aln mailbox list -e a3b7c9d0:4e591b23 --all
    """
    # 解析 entity card
    entity_card = resolve_entity_card(entity_spec)

    mailbox_path = _get_mailbox_path(storage, entity_card.entity_uid)

    # Determine filters
    is_read = None
    is_handled = None
    direction = None

    if not show_all and not any([filter_read, filter_unread, filter_handled, filter_unhandled, filter_inbound, filter_outbound]):
        # Default: unread only
        is_read = False

    if filter_read:
        is_read = True
    elif filter_unread:
        is_read = False

    if filter_handled:
        is_handled = True
    elif filter_unhandled:
        is_handled = False

    if filter_inbound:
        direction = "inbound"
    elif filter_outbound:
        direction = "outbound"

    mailbox = Mailbox(entity_card.entity_uid, mailbox_path)

    # List mails
    mails = mailbox.list_mails(is_read=is_read, is_handled=is_handled, direction=direction)

    if not mails:
        cli_printer.echo("No messages found")
        return

    cli_printer.echo(f"Found {len(mails)} message(s):\n")
    for i, mail_entry in enumerate(mails, 1):
        cli_printer.echo(f"[{i}]")
        cli_printer.print_mail(mail_entry, show_full=False)
        cli_printer.echo("")


@command.command("check", help="View mail details and mark as read.")
@click.option(
    "-e",
    "--entity",
    "entity_spec",
    required=True,
    help="Entity to query (host:entity or entity). Examples: 'Alice', 'default:Alice'",
)
@click.option(
    "--mail-id",
    required=True,
    help="Message ID to check",
)
@cli_exception_wrapper(error_message="Failed to check mail")
@get_storage
@get_cli_printer
def check_command(
    entity_spec: str,
    mail_id: str,
    storage: StorageManager,
    cli_printer: CliPrinter,
) -> None:
    """View full mail details and mark as read.

    Examples:

    \b
      # View a message and mark it as read
      aln mailbox check -e 4e591b23 --mail-id msg_4f8a2b

    \b
      # Full address format
      aln mailbox check -e a3b7c9d0:4e591b23 --mail-id msg_4f8a2b
    """
    # 解析 entity card
    entity_card = resolve_entity_card(entity_spec)

    mailbox_path = _get_mailbox_path(storage, entity_card.entity_uid)
    mailbox = Mailbox(entity_card.entity_uid, mailbox_path)

    # Get mail
    mail_entry = mailbox.get_mail(mail_id)
    if not mail_entry:
        cli_printer.echo(f"Mail not found: {mail_id}")
        sys.exit(1)

    # Display full mail
    cli_printer.print_mail(mail_entry, show_full=True)

    # Mark as read
    mailbox.mark_as_read(mail_id)
    cli_printer.echo("\n✓ Marked as read")


@command.command("reply", help="Reply to a message.")
@click.option(
    "-e",
    "--entity",
    "entity_spec",
    required=True,
    help="Entity to reply from (host:entity or entity). Examples: 'Alice', 'default:Alice'",
)
@click.option(
    "--mail-id",
    required=True,
    help="Message ID to reply to",
)
@click.option(
    "-m",
    "--message",
    "message_json",
    required=True,
    help='Message content as JSON string',
)
@cli_exception_wrapper(error_message="Failed to reply to mail")
@get_storage
@get_cli_printer
def reply_command(
    entity_spec: str,
    mail_id: str,
    message_json: str,
    storage: StorageManager,
    cli_printer: CliPrinter,
) -> None:
    """Reply to a message.

    Automatically sends reply to the original sender and marks
    the original message as handled.

    Examples:

    \b
      # Reply to a message
      aln mailbox reply -e 4e591b23 --mail-id msg_4f8a2b -m '{"text": "Thanks!"}'

    \b
      # Full address format
      aln mailbox reply -e a3b7c9d0:4e591b23 --mail-id msg_4f8a2b -m '{"text": "Got it"}'
    """
    # 解析 entity card
    entity_card = resolve_entity_card(entity_spec)

    mailbox_path = _get_mailbox_path(storage, entity_card.entity_uid)
    mailbox = Mailbox(entity_card.entity_uid, mailbox_path)

    # Get original mail
    mail_entry = mailbox.get_mail(mail_id)
    if not mail_entry:
        cli_printer.echo(f"Mail not found: {mail_id}")
        sys.exit(1)

    original_mail = mail_entry.get("mail", {})

    # Get from/to from original mail
    # Reply: from becomes to, to becomes from
    to_address = original_mail.get("sender", {}).get("address")
    from_address = original_mail.get("recipient", [{}])[0].get("address")

    if not to_address or not from_address:
        cli_printer.echo("Cannot determine sender/recipient from original mail")
        sys.exit(1)

    # Parse message JSON
    try:
        message_data = json.loads(message_json)
    except json.JSONDecodeError as e:
        cli_printer.echo(f"Invalid JSON message: {e}")
        sys.exit(1)

    # Create Message object
    try:
        message = Message(**message_data)
    except Exception as e:
        cli_printer.echo(f"Invalid message format: {e}")
        sys.exit(1)

    # Create Mail
    sender = FPAddress(address=from_address)
    recipient = [FPAddress(address=to_address)]
    mail = Mail(sender=sender, recipient=recipient, message=message, signature="")

    # Send via host client
    host_url = storage.get_host_url(entity_card.host_uid)
    client = HostClient(base_url=host_url)
    result = client.send_mail(mail)

    cli_printer.echo("✓ Reply sent")
    cli_printer.print(result)

    # Save to outbound mailbox
    mailbox.save_outbound(mail)

    # Mark original as handled
    mailbox.mark_as_handled(mail_id)
