"""`aln friend` command group for friend management."""

from __future__ import annotations

import click

from aln.app import HostClient

from .misc.clistyle import FriendCLIStyle
from .misc.printer import CliPrinter
from .misc.wrappers import cli_exception_wrapper, get_cli_printer, resolve_entity_card


@click.group(
    name="friend",
    cls=FriendCLIStyle,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.pass_context
def command(ctx: click.Context) -> None:
    """Friend management - entity-initiated social connections.

\b
Examples:
  # Add a friend
  aln friend add -e bd19e57d --to a552e88d
  # List friends
  aln friend list -e bd19e57d
  # Remove a friend
  aln friend delete -e bd19e57d --friend a552e88d
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@command.command("add", help="Send a friend request from one local entity.")
@click.option(
    "-e",
    "--entity",
    "from_entity_spec",
    required=True,
    help="Sender entity (host:entity or entity). Examples: 'Alice', 'default:Alice'",
)
@click.option(
    "--to",
    "to_target_spec",
    required=True,
    help="Recipient entity (host:entity or entity). Examples: 'Bob', 'default:Bob'",
)
@click.option(
    "--text",
    default=None,
    help="Friend request text. Uses default text when omitted.",
)
@cli_exception_wrapper(error_message="Failed to add friend")
@get_cli_printer
def add_command(
    from_entity_spec: str,
    to_target_spec: str,
    text: str | None,
    cli_printer: CliPrinter,
) -> None:
    """Send friend request from local sender to recipient.

    -e and --to take FP address: host_uid:entity_uid or entity_uid.

    Examples:

    \b
      # Same-host friend request
      aln friend add -e 4e591b23 --to 1e988b99

    \b
      # Cross-host friend request
      aln friend add -e a3b7c9d0:4e591b23 --to f5d2a1b8:1e988b99

    \b
      # With custom greeting text
      aln friend add -e 4e591b23 --to 1e988b99 --text "Hi, let's connect!"
    """
    from fp.utils.storage import get_storage_manager

    # 解析发送方和接收方的 entity cards
    from_card = resolve_entity_card(from_entity_spec)
    to_card = resolve_entity_card(to_target_spec)

    # 创建发送方的 client
    storage = get_storage_manager()
    from_host_url = storage.get_host_url(from_card.host_uid)
    client = HostClient(base_url=from_host_url)

    # 使用 to_card 的完整地址
    to_address = to_card.address.address

    client.friend_add(
        from_entity=from_card.entity_uid,
        to_address=to_address,
        text=text,
    )
    cli_printer.echo("✓ Friend request delivered to recipient mailbox")
    cli_printer.echo(f"  From: {from_card.address.address}")
    cli_printer.echo(f"  To:   {to_address}")
    cli_printer.echo("  Note: Any recipient-side owner review will notify them separately.")


@command.command("list", help="List all friends for one entity.")
@click.option(
    "-e",
    "--entity",
    "entity_spec",
    required=True,
    help="Entity to query (host:entity or entity). Examples: 'default:Alice', 'Alice'",
)
@cli_exception_wrapper(error_message="Failed to list friends")
@get_cli_printer
def list_command(
    entity_spec: str,
    cli_printer: CliPrinter,
) -> None:
    """List all friends for one entity.

    Examples:

    \b
      # entity_uid only (uses default host)
      aln friend list -e 4e591b23

    \b
      # Full address: host_uid:entity_uid
      aln friend list -e a3b7c9d0:4e591b23
    """
    from fp.utils.storage import get_storage_manager

    # 解析 entity card
    entity_card = resolve_entity_card(entity_spec)

    # 创建 client
    storage = get_storage_manager()
    host_url = storage.get_host_url(entity_card.host_uid)
    client = HostClient(base_url=host_url)

    # 查询 friends
    friends = client.entity_friends(entity_uid=entity_card.entity_uid)
    cli_printer.print(friends)


@command.command("delete", help="Remove a friend from one entity's friend list.")
@click.option(
    "-e",
    "--entity",
    "from_entity_spec",
    required=True,
    help="Entity whose friend list to modify. Examples: 'Alice', 'default:Alice'",
)
@click.option(
    "--friend",
    "friend_spec",
    required=True,
    help="Friend to remove (name or uid). Examples: 'Bob', '1e988b99'",
)
@cli_exception_wrapper(error_message="Failed to delete friend")
@get_cli_printer
def delete_command(
    from_entity_spec: str,
    friend_spec: str,
    cli_printer: CliPrinter,
) -> None:
    """Remove a friend from one entity's friend list (one-sided).

    This only removes the friend from your side. The other party
    will still have you in their friend list until they remove you.

    Examples:

    \b
      # Remove by friend name
      aln friend delete -e 4e591b23 --friend Bob

    \b
      # Remove by friend UID
      aln friend delete -e 4e591b23 --friend 1e988b99

    \b
      # Full address format
      aln friend delete -e a3b7c9d0:4e591b23 --friend 1e988b99
    """
    from fp.utils.storage import get_storage_manager

    # 解析发送方 entity card
    from_card = resolve_entity_card(from_entity_spec)

    # 创建发送方的 client
    storage = get_storage_manager()
    from_host_url = storage.get_host_url(from_card.host_uid)
    client = HostClient(base_url=from_host_url)

    # 获取 friends 列表来解析 friend_spec
    friends = client.entity_friends(entity_uid=from_card.entity_uid)

    # 尝试通过 uid 或 name 查找 friend
    friend_uid = None
    for friend in friends:
        if friend.entity_uid == friend_spec or friend.name == friend_spec:
            friend_uid = friend.entity_uid
            break

    if friend_uid is None:
        cli_printer.echo(f"Friend not found: {friend_spec}")
        cli_printer.echo("Available friends:")
        for friend in friends:
            cli_printer.echo(f"  • {friend.name} ({friend.entity_uid[:8]})")
        return

    result = client.friend_delete(
        from_entity=from_card.entity_uid,
        friend_uid=friend_uid,
    )
    cli_printer.echo(f"✓ Friend removed: {friend_spec}")
