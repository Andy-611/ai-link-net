"""`aln init` command."""

from __future__ import annotations

import time
import urllib.request
import webbrowser
from urllib.parse import quote

import click
from fp import FPAddress
from fp.utils.storage import StorageManager

from aln.app import HostClient
from aln.app.schemas import HostUpdateRequest

from .host import _start_host, find_available_port
from .misc.common import generate_qr_lines, get_local_ip
from .misc.process import is_pid_alive
from .misc.printer import CliPrinter
from .misc.wrappers import cli_exception_wrapper, get_cli_printer, get_storage
from .ui import ensure_ui_running


DEFAULT_PARENT_URL = "https://fp.metadl.com/"


@click.command(name="init", help="Initialize FP system (create default host, register human entity, and start UI)")
@click.option("--no-human", is_flag=True, default=False, help="Skip automatic human entity registration")
@cli_exception_wrapper(error_message="Failed to initialize FP system")
@get_storage
@get_cli_printer
def command(
    no_human: bool,
    storage: StorageManager,
    cli_printer: CliPrinter,
) -> None:
    """Initialize FP system with default configuration."""
    cli_printer.echo("🚀 Initializing FP system...")
    cli_printer.echo("")

    # Check if system is already initialized
    host_entry = None
    try:
        host_entry = storage.get_host("default")
    except Exception:
        pass

    if host_entry:
        # Check if human entity exists
        host_url = f"http://{host_entry.bind_host}:{host_entry.port}"
        if host_entry.bind_host == "0.0.0.0":
            host_url = f"http://127.0.0.1:{host_entry.port}"

        try:
            pid = storage.get_host_pid("default")
            if pid and is_pid_alive(pid):
                client = HostClient(base_url=host_url, timeout=10.0)
                entities = client.entity_list()
                human_entities = [e for e in entities if e.kind == "human"]

                if human_entities:
                    cli_printer.echo("❌ FP system is already initialized!")
                    cli_printer.echo("")
                    cli_printer.echo(f"   Default host: {host_entry.bind_host}:{host_entry.port}")
                    cli_printer.echo(f"   Human entity: {human_entities[0].name}")
                    cli_printer.echo("")
                    cli_printer.echo("💡 Tips:")
                    cli_printer.echo("   - Use 'aln status' to check system status")
                    cli_printer.echo("   - Use 'aln ui' to start the Web UI")
                    cli_printer.echo("   - Use 'aln reset' to reset the system")
                    return
        except Exception:
            pass

    # 1. Check if default host exists, create if not
    if host_entry:
        cli_printer.echo("✓ Default host already exists")
    else:
        host_entry = None

    if host_entry is None:
        # Create default host
        cli_printer.echo("Creating default host...")

        bind_host = "0.0.0.0"
        port = find_available_port()
        url = f"http://{bind_host}:{port}"
        address = FPAddress.create().address

        storage.create_or_update_host(
            host_name="default",
            bind_host=bind_host,
            port=port,
            url=url,
            address=address,
            parent_url=None,
        )
        cli_printer.echo(f"✓ Default host created at {bind_host}:{port}")

    # 2. Start default host
    pid = storage.get_host_pid("default")
    if pid and is_pid_alive(pid):
        cli_printer.echo(f"✓ Default host is already running (PID: {pid})")
    else:
        cli_printer.echo("Starting default host...")
        _start_host("default", storage, cli_printer)

    # 3. Wait for host to be ready with health check
    host_entry = storage.get_host("default")
    host_url = f"http://{host_entry.bind_host}:{host_entry.port}"
    if host_entry.bind_host == "0.0.0.0":
        host_url = f"http://127.0.0.1:{host_entry.port}"

    cli_printer.echo("Waiting for host to be ready...")
    max_retries = 30  # 最多等待 30 秒
    for i in range(max_retries):
        try:
            # 绕过代理直接访问本地服务
            no_proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(no_proxy_handler)
            opener.open(f"{host_url}/health", timeout=1)
            cli_printer.echo("✓ Host is ready")
            break
        except Exception:
            if i == max_retries - 1:
                cli_printer.echo("⚠️  Host startup timeout")
                cli_printer.echo("You can manually register later with: aln entity register -k human -n <name>")
                return
            time.sleep(1)

    # 3.5. Set default parent if not configured
    client = HostClient(base_url=host_url, timeout=10.0)
    _set_default_parent(host_entry.parent_url, client, cli_printer)

    # 4. Register a human entity
    entity_card = None
    if no_human:
        cli_printer.echo("⏭️  Skipping human entity registration (--no-human)")
        try:
            entities = client.entity_list()
            human_entities = [e for e in entities if e.kind == "human"]
            if human_entities:
                entity_card = human_entities[0]
        except Exception:
            pass
    else:
        cli_printer.echo("Registering human entity...")
        client = HostClient(base_url=host_url, timeout=10.0)

        try:
            entities = client.entity_list()
            human_entities = [e for e in entities if e.kind == "human"]
            if human_entities:
                cli_printer.echo(f"✓ Human entity already exists: {human_entities[0].name}")
                entity_card = human_entities[0]
            else:
                entity_card = client.entity_register(
                    kind="human",
                    name=None,
                    is_private=False,
                )
                cli_printer.echo(f"✓ Human entity registered: {entity_card.name}")
        except Exception as e:
            cli_printer.echo(f"⚠️  Failed to register human entity: {e}")
            cli_printer.echo("You can manually register later with: aln entity register -k human -n <name>")

    # 5. Start UI
    cli_printer.echo("Starting Web UI...")
    ensure_ui_running(port=5173)
    time.sleep(1)

    # 6. Display access information
    local_ip = get_local_ip()

    ui_port = 5173
    encoded_host_url_local = quote(host_url)
    encoded_host_url_public = quote(f"http://{local_ip}:{host_entry.port}")

    if entity_card:
        local_url = f"http://localhost:{ui_port}/?entity_uid={entity_card.entity_uid}&host_url={encoded_host_url_local}"
        public_url = f"http://{local_ip}:{ui_port}/?entity_uid={entity_card.entity_uid}&host_url={encoded_host_url_public}"
    else:
        local_url = f"http://localhost:{ui_port}/?host_url={encoded_host_url_local}"
        public_url = f"http://{local_ip}:{ui_port}/?host_url={encoded_host_url_public}"

    try:
        webbrowser.open(local_url)
        cli_printer.echo("\n🌐 Opening browser...")
    except Exception as e:
        cli_printer.echo(f"\n⚠️  Could not open browser automatically: {e}")

    qr_display = generate_qr_lines(public_url)
    label = entity_card.name if entity_card else "host"

    cli_printer.echo("\n" + "=" * 80)
    cli_printer.echo("✅ FP system initialized successfully!")
    cli_printer.echo("")
    cli_printer.echo(f"🔗 Web UI URL for {label}:")
    cli_printer.echo(f"   Local:  {local_url}")
    if local_ip != "localhost":
        cli_printer.echo(f"   Public: {public_url}")
    cli_printer.echo("\n📱 QR Code:")
    for line in qr_display:
        cli_printer.echo(f"   {line}")
    cli_printer.echo("=" * 80 + "\n")


def _set_default_parent(
    current_parent_url: str | None,
    client: HostClient,
    cli_printer: CliPrinter,
) -> None:
    """Set init-only default parent when the host has no parent."""
    if current_parent_url:
        return

    try:
        client.host_update(
            HostUpdateRequest(host_name="default", parent_url=DEFAULT_PARENT_URL)
        )
        cli_printer.echo(f"✓ Parent host configured: {DEFAULT_PARENT_URL}")
    except Exception as e:
        cli_printer.echo(f"⚠️  Failed to set parent: {e}")
