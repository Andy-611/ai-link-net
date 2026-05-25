"""`fp entity` command group for entity discovery."""

from __future__ import annotations

import json
import sys

import click

from aln.app import HostClient
from aln.app.schemas import EntityUpdateRequest

from .misc.clistyle import EntityCLIStyle
from .misc.common import generate_qr_lines, get_local_ip
from .misc.printer import CliPrinter
from .misc.wrappers import cli_exception_wrapper, get_cli_printer, resolve_entity_card


@click.group(
    name="entity",
    cls=EntityCLIStyle,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.pass_context
def command(ctx: click.Context) -> None:
    """Entity lifecycle management - host operations on entities."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@command.command("register", help="Register a new entity on host.")
@click.option(
    "-k",
    "--kind",
    required=True,
    type=click.Choice(
        ["host", "human", "agent", "arbiter", "tool", "resource", "service"], case_sensitive=False
    ),
    help="Entity kind (required)",
)
@click.option(
    "-n",
    "--name",
    required=False,
    default=None,
    help="Entity name (defaults to entity_uid if not provided)",
)
@click.option(
    "-d",
    "--description",
    default="",
    help="Entity description (for agents: appended to system prompt as role/identity)",
)
@click.option(
    "--provider",
    type=click.Choice(
        ["codex", "claude", "claudecode", "autowork", "openclaw", "hermes"], case_sensitive=False
    ),
    default=None,
    help="Agent provider (codex/claude/claudecode/autowork/openclaw/hermes)",
)
@click.option(
    "--host",
    "host_name",
    default="default",
    help="Host name to register on (default: default)",
)
@click.option(
    "--url",
    "host_url",
    default=None,
    help="Direct host URL (e.g., http://172.31.0.5:7001). Overrides --host",
)
@click.option(
    "--private",
    "is_private",
    is_flag=True,
    default=False,
    help="Make entity private (default: False)",
)
@click.option(
    "--workdir",
    default=None,
    help="Agent working directory on host (only for kind=agent)",
)
@cli_exception_wrapper(error_message="Failed to register entity")
@get_cli_printer
def register_command(
    kind: str,
    name: str | None,
    description: str,
    provider: str | None,
    host_name: str,
    host_url: str | None,
    is_private: bool,
    workdir: str | None,
    cli_printer: CliPrinter,
) -> None:
    """Register a new entity on host."""
    from fp.utils.storage import get_storage_manager

    # 确定使用哪个 client
    if host_url:
        # 直接使用提供的 URL
        client = HostClient(base_url=host_url)
        target_host_display = host_url
    elif host_name.startswith("http://") or host_name.startswith("https://"):
        # --host 参数传的是 URL，直接使用
        client = HostClient(base_url=host_name)
        target_host_display = host_name
    else:
        # 使用 host_name 查找本地配置
        storage = get_storage_manager()
        target_url = storage.get_host_url(host_name)
        client = HostClient(base_url=target_url)
        target_host_display = f"{host_name} ({target_url})"

    cli_printer.echo(f"Registering entity on: {target_host_display}")

    entity_card = client.entity_register(
        kind=kind,
        name=name,
        is_private=is_private,
        description=description,
        provider=provider,
        workdir=workdir,
    )
    cli_printer.print(entity_card)

    # 如果是 human 类型，自动启动 UI 并显示访问链接
    if kind.lower() == "human":
        from urllib.parse import quote

        from aln.cli.ui import ensure_ui_running

        # 确保 UI 正在运行
        ensure_ui_running()

        # 获取当前 host_url 用于生成登录链接
        if not host_url:
            if host_name.startswith("http://") or host_name.startswith("https://"):
                # --host 传的是 URL
                host_url = host_name
            else:
                storage = get_storage_manager()
                host_url = storage.get_host_url(host_name)

        # 判断是否是远程 host
        from urllib.parse import urlparse

        parsed = urlparse(host_url)
        is_remote_host = parsed.hostname not in ("localhost", "127.0.0.1", "0.0.0.0")

        ui_port = 5173  # 默认端口

        if is_remote_host:
            # 远程 host：UI 和 host 都在远程服务器，使用 host 的 IP
            remote_ip = parsed.hostname
            encoded_host_url = quote(host_url)
            public_url = f"http://{remote_ip}:{ui_port}/?entity_uid={entity_card.entity_uid}&host_url={encoded_host_url}"
            local_url = None
        else:
            # 本地 host：UI 在本地，host 也在本地
            local_ip = get_local_ip()

            # 本地 URL 用 127.0.0.1，公网 URL 用局域网 IP
            host_url_public = f"http://{local_ip}:{parsed.port}"
            encoded_host_url_local = quote(host_url)
            encoded_host_url_public = quote(host_url_public)

            local_url = f"http://localhost:{ui_port}/?entity_uid={entity_card.entity_uid}&host_url={encoded_host_url_local}"
            public_url = f"http://{local_ip}:{ui_port}/?entity_uid={entity_card.entity_uid}&host_url={encoded_host_url_public}"

        qr_display = generate_qr_lines(public_url)

        cli_printer.echo("\n" + "=" * 80)
        if is_remote_host:
            cli_printer.echo(f"🔗 Web UI URL for {name}:")
            cli_printer.echo(f"   🌐 Public URL: {public_url}")
        else:
            cli_printer.echo(f"🔗 Web UI URL for {name}:")
            cli_printer.echo(f"   Local: {local_url}")
            if local_url != public_url:
                cli_printer.echo(f"   Public: {public_url}")
        cli_printer.echo("\n📱 QR Code:")
        for line in qr_display:
            cli_printer.echo(f"   {line}")
        cli_printer.echo("=" * 80 + "\n")


@command.command("delete", help="Delete an entity from host.")
@click.option(
    "-e",
    "--entity",
    "entity_spec",
    required=True,
    help="Entity to delete (host:entity or entity). Examples: 'Alice', 'default:Alice'",
)
@cli_exception_wrapper(error_message="Failed to delete entity")
@get_cli_printer
def delete_command(
    entity_spec: str,
    cli_printer: CliPrinter,
) -> None:
    """Delete an entity from host.

    Examples:
      aln entity delete -e Alice
      aln entity delete -e default:Alice
      aln entity delete -e 4e591b23:1e988b99
    """
    from fp.utils.storage import get_storage_manager

    # 解析 entity card
    entity_card = resolve_entity_card(entity_spec)

    # 创建 client
    storage = get_storage_manager()
    host_url = storage.get_host_url(entity_card.host_uid)
    client = HostClient(base_url=host_url)

    # 删除 entity
    client.entity_delete(entity_card.entity_uid)
    cli_printer.echo(
        f"✓ Entity '{entity_card.name}' ({entity_card.entity_uid}) deleted successfully"
    )


@command.command("set", help="Update entity configuration.")
@click.option(
    "-e",
    "--entity",
    "entity_spec",
    required=True,
    help="Entity to update (host:entity or entity). Examples: 'Alice', 'default:Alice'",
)
@click.option(
    "--visible",
    type=bool,
    help="Set entity visibility (true/false)",
)
@click.option(
    "--enabled",
    type=bool,
    help="Set entity enabled state (true/false)",
)
@click.option(
    "--payload",
    "-p",
    "payload_json",
    help='Full JSON payload to update (e.g., \'{"visible": true, "enabled": false}\')',
)
@cli_exception_wrapper(error_message="Failed to set entity config")
@get_cli_printer
def set_command(
    entity_spec: str,
    visible: bool | None,
    enabled: bool | None,
    payload_json: str | None,
    cli_printer: CliPrinter,
) -> None:
    """Update entity configuration.

    Examples:
      aln entity set -e Alice --visible true
      aln entity set -e Bob --enabled false
      aln entity set -e Alice -p '{"visible": true, "enabled": true}'
    """
    # Check if any update is provided
    if not any([visible is not None, enabled is not None, payload_json]):
        lines = """
No updates provided. Use --help to see usage:

  --visible BOOL         Set visibility (true/false)
  --enabled BOOL         Set enabled state (true/false)
  --payload/-p JSON      Set full payload

Examples:
  aln entity set -e Alice --visible true
  aln entity set -e Bob --enabled false
  aln entity set -e Alice -p '{"visible": true, "enabled": true}'
        """
        cli_printer.print_lines(lines)
        return

    from fp.utils.storage import get_storage_manager

    # 解析 entity card
    entity_card = resolve_entity_card(entity_spec)

    # 创建 client
    storage = get_storage_manager()
    host_url = storage.get_host_url(entity_card.host_uid)
    client = HostClient(base_url=host_url)

    # Parse payload if provided
    if payload_json:
        try:
            payload_dict = json.loads(payload_json)
        except json.JSONDecodeError as e:
            cli_printer.echo(f"Invalid JSON payload: {e}")
            sys.exit(1)

        if not isinstance(payload_dict, dict):
            cli_printer.echo("Payload must be a JSON object")
            sys.exit(1)

        update_request = EntityUpdateRequest(**payload_dict)
    else:
        update_request = EntityUpdateRequest(
            visible=visible,
            enabled=enabled,
        )

    # Update entity via API
    updated_entity = client.entity_update(
        entity_uid=entity_card.entity_uid,
        update_request=update_request,
    )

    cli_printer.print(updated_entity)
