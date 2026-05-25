"""Tests for pay CLI help text."""

from __future__ import annotations

from click.testing import CliRunner

from aln.cli.pay import command as pay_command


def test_collect_help_mentions_owner_can_supply_receipt() -> None:
    """Collect help should explain DIRECT owner approval receipt handoff."""
    runner = CliRunner()

    result = runner.invoke(pay_command, ["collect", "--help"])

    assert result.exit_code == 0
    assert "owner can provide or replace the" in result.output
    assert "final receipt info during approval" in result.output
    assert "so --receipt may be omitted entirely" in result.output
