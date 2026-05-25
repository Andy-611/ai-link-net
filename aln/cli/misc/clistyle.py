from __future__ import annotations

import os
from pathlib import Path

import click


class CLIStyle(click.Group):
    """Render top-level help in git-like style with workflow guidance."""

    _HIDDEN_GROUPS = {"system management"}

    _COMMAND_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
        (
            "messaging",
            "",
            ("mail", "mailbox"),
        ),
        (
            "social & discovery",
            "",
            ("find", "friend"),
        ),
        (
            "trade & payment",
            "",
            ("market", "pay", "contract"),
        ),
        (
            "system management",
            "",
            ("host", "entity", "health", "ui", "reset", "init", "update"),
        ),
    )

    def format_help(
        self,
        ctx: click.Context,
        formatter: click.HelpFormatter,
    ) -> None:
        import sys
        show_full = "--full" in sys.argv

        # Usage
        self.format_usage(ctx, formatter)
        formatter.write_paragraph()

        # Description (dynamic based on host status)
        description_lines = self._get_dynamic_description().split("\n")
        for line in description_lines:
            formatter.write_text(line)
        formatter.write_paragraph()

        # Build command map
        command_map: dict[str, click.Command] = {}
        for name in self.list_commands(ctx):
            command = self.get_command(ctx, name)
            if command is None or command.hidden:
                continue
            command_map[name] = command

        # Commands grouped by category (git style)
        formatter.write_text("These are common commands used in various situations:")
        formatter.write_paragraph()

        rendered: set[str] = set()
        for group_name, _, command_names in self._COMMAND_GROUPS:
            if not show_full and group_name in self._HIDDEN_GROUPS:
                for name in command_names:
                    rendered.add(name)
                continue
            if show_full and group_name in self._HIDDEN_GROUPS:
                formatter.write_text(
                    f"{group_name} (requires explicit owner permission)"
                )
            else:
                formatter.write_text(f"{group_name}")
            formatter.indent()
            rows: list[tuple[str, str]] = []
            for name in command_names:
                command = command_map.get(name)
                if command is None:
                    continue
                rows.append((name, (command.help or "").split("\n")[0]))
                rendered.add(name)
            if rows:
                formatter.write_dl(rows)
            formatter.dedent()
            formatter.write_paragraph()

        if not show_full:
            formatter.write_text(
                "System commands are hidden — only the owner can run them."
            )
            formatter.write_text("Use `aln -h --full` to see all commands.")
            formatter.write_paragraph()

        other_rows: list[tuple[str, str]] = []
        for name in self.list_commands(ctx):
            if name in rendered:
                continue
            command = command_map.get(name)
            if command is None:
                continue
            other_rows.append((name, (command.help or "").split("\n")[0]))

        if other_rows:
            formatter.write_text("Other Commands:")
            formatter.indent()
            formatter.write_dl(other_rows)
            formatter.dedent()
            formatter.write_paragraph()

        # Format options in groups
        self._format_options_grouped(ctx, formatter)

        # Footer
        formatter.write_text("Use `aln <command> -h` for detailed help on each command.")

    def _get_dynamic_description(self) -> str:
        """Generate description based on current host status."""
        from fp.utils.path import get_config_path

        config_path = get_config_path()

        base = "AI-Link-Net: A entity-to-entity communication system base on Foundation Protocol.\n"

        if not config_path.exists():
            return base + "\n→ No hosts configured yet. Start with: aln host init"

        try:
            import json

            with open(config_path) as f:
                config = json.load(f)

            hosts = config.get("hosts", {})
            if not hosts:
                return base + "\n→ No hosts configured yet. Start with: aln host init"

            # Collect running hosts info
            from fp.utils.storage import get_storage_manager
            storage = get_storage_manager()

            running_hosts = []
            for host_uid, host_data in hosts.items():
                pid = storage.get_host_pid(host_uid)
                is_alive = self._is_pid_alive(pid) if pid else False
                if pid and is_alive:
                    running_hosts.append((host_uid, host_data))

            if not running_hosts:
                return base + "\n→ Hosts configured but not running. Start with: aln host start"

            # Check if any host has entities
            has_entities = False
            entity_summary = []

            for host_name, host_data in running_hosts:
                # Count entities for this host from config
                host_uid = host_data.get("address", "").split(":")[0] if "address" in host_data else None
                if not host_uid:
                    continue

                entity_count = sum(
                    1 for e in config.get("entities", {}).values()
                    if e.get("host_uid") == host_uid
                )

                if entity_count > 0:
                    has_entities = True
                    entity_summary.append(f"  • {host_name}: {entity_count} entities")

            if not has_entities:
                hosts_list = ", ".join([h[0] for h in running_hosts])
                return (
                    f"{base}\n"
                    f"→ Running hosts: {hosts_list}"
                )

            # Has hosts and entities
            summary = base + "\n"
            summary += "→ Active hosts:\n"
            for host_name, _ in running_hosts:
                summary += f"  • {host_name}\n"
            if entity_summary:
                summary += "\n→ Entities:\n"
                summary += "\n".join(entity_summary)
            summary += "\n\n→ Next steps:\n"
            summary += "  • Search entities:  aln entity search\n"
            summary += (
                "  • Add friend:       "
                "aln friend add --from <uid> --to <address>\n"
            )
            summary += (
                "  • Send message:     "
                "aln mail --from <addr> --to <addr> -m '...'"
            )

            return summary

        except Exception as e:
            import traceback
            return base + f"\n→ Error checking status: {e}\n{traceback.format_exc()}"

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        """Check if process is alive."""
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def _format_options_grouped(
        self,
        ctx: click.Context,
        formatter: click.HelpFormatter,
    ) -> None:
        """Format options in groups like uv does."""
        opts = []
        for param in self.get_params(ctx):
            rv = param.get_help_record(ctx)
            if rv is not None:
                opts.append(rv)

        if not opts:
            return

        # Separate options into categories
        global_opts = []
        other_opts = []

        global_option_names = [
            "--host",
            "--entity-name",
            "-v",
            "--verbose",
            "-q",
            "--quiet",
        ]
        for opt_names, opt_help in opts:
            # Check if it's a global option we care about
            if any(name in opt_names for name in global_option_names):
                global_opts.append((opt_names, opt_help))
            else:
                other_opts.append((opt_names, opt_help))

        # Write Global options section
        if global_opts:
            formatter.write_text("Global options:")
            formatter.write_paragraph()
            formatter.indent()
            formatter.write_dl(global_opts)
            formatter.dedent()
            formatter.write_paragraph()

        # Write Other options section (like --version, --help)
        if other_opts:
            formatter.indent()
            formatter.write_dl(other_opts)
            formatter.dedent()
            formatter.write_paragraph()


class GroupedCommandStyle(click.Group):
    """Render sub-command help with grouped sections. Subclass and set _COMMAND_GROUPS."""

    _COMMAND_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def format_help(
        self,
        ctx: click.Context,
        formatter: click.HelpFormatter,
    ) -> None:
        self.format_usage(ctx, formatter)
        formatter.write_paragraph()
        formatter.write_text(self.help or "")
        formatter.write_paragraph()
        self._format_options_only(ctx, formatter)

        command_map: dict[str, click.Command] = {}
        for name in self.list_commands(ctx):
            command = self.get_command(ctx, name)
            if command is None or command.hidden:
                continue
            command_map[name] = command

        formatter.write_text("Commands:")
        formatter.write_paragraph()
        rendered: set[str] = set()
        formatter.indent()
        for group_name, command_names in self._COMMAND_GROUPS:
            rows: list[tuple[str, str]] = []
            for name in command_names:
                command = command_map.get(name)
                if command is None:
                    continue
                rows.append((name, (command.help or "").split("\n")[0]))
                rendered.add(name)

            if rows:
                formatter.write_text(f"{group_name}:")
                formatter.indent()
                formatter.write_dl(rows)
                formatter.dedent()
                formatter.write_paragraph()

        other_rows: list[tuple[str, str]] = []
        for name in self.list_commands(ctx):
            if name in rendered:
                continue
            command = command_map.get(name)
            if command is None:
                continue
            other_rows.append((name, command.get_short_help_str()))

        if other_rows:
            formatter.write_text("Other:")
            formatter.indent()
            formatter.write_dl(other_rows)
            formatter.dedent()
        formatter.dedent()

    def _format_options_only(
        self,
        ctx: click.Context,
        formatter: click.HelpFormatter,
    ) -> None:
        """Render only options section."""
        opts: list[tuple[str, str]] = []
        for param in self.get_params(ctx):
            help_record = param.get_help_record(ctx)
            if help_record is not None:
                opts.append(help_record)

        if not opts:
            return

        formatter.write_text("Options:")
        formatter.indent()
        formatter.write_dl(opts)
        formatter.dedent()
        formatter.write_paragraph()


class HostCLIStyle(GroupedCommandStyle):
    """Grouped help for `aln host`."""

    _COMMAND_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("Lifecycle", ("init", "start", "stop", "reset", "restart", "set")),
        ("Query", ("list", "detail", "entities", "log")),
    )


class PayCLIStyle(GroupedCommandStyle):
    """Grouped help for `aln pay`."""

    _COMMAND_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("Actions", ("collect", "transfer", "confirm")),
        ("Query", ("balance", "list")),
    )


class ContractCLIStyle(GroupedCommandStyle):
    """Grouped help for `aln contract`."""

    _COMMAND_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("Create", ("create", "amend")),
        ("Lifecycle", ("approve", "complete", "accept", "rework", "cancel")),
        ("Query", ("list", "status", "rate")),
    )


class MarketCLIStyle(GroupedCommandStyle):
    """Grouped help for `aln market`."""

    _COMMAND_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("Actions", ("publish", "archive", "delete")),
        ("Query", ("list",)),
        ("Help", ("guide",)),
    )


class FriendCLIStyle(GroupedCommandStyle):
    """Grouped help for `aln friend`."""

    _COMMAND_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("Actions", ("add", "delete")),
        ("Query", ("list",)),
    )


class MailboxCLIStyle(GroupedCommandStyle):
    """Grouped help for `aln mailbox`."""

    _COMMAND_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("Actions", ("check", "reply")),
        ("Query", ("list",)),
    )


class EntityCLIStyle(GroupedCommandStyle):
    """Grouped help for `aln entity`."""

    _COMMAND_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("Lifecycle", ("register", "delete", "set")),
    )
