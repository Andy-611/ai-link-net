"""Tests for CLI printer utilities."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from aln.cli.misc.printer import CliPrinter


class SampleModel(BaseModel):
    """Sample model for testing."""

    name: str
    value: int


class TestCliPrinter:
    """Test CliPrinter class."""

    def test_echo(self, capsys):
        """Test echo method."""
        printer = CliPrinter()
        printer.echo("Hello world")

        captured = capsys.readouterr()
        assert "Hello world" in captured.out

    def test_echo_empty(self, capsys):
        """Test echo with no message."""
        printer = CliPrinter()
        printer.echo()

        captured = capsys.readouterr()
        assert captured.out == "\n"

    def test_print_lines(self, capsys):
        """Test print_lines method."""
        printer = CliPrinter()
        text = """
        Line 1
        Line 2
        Line 3
        """
        printer.print_lines(text)

        captured = capsys.readouterr()
        assert "Line 1" in captured.out
        assert "Line 2" in captured.out
        assert "Line 3" in captured.out

    def test_print_basemodel(self, capsys):
        """Test print method with BaseModel."""
        printer = CliPrinter()
        model = SampleModel(name="test", value=42)
        printer.print(model)

        captured = capsys.readouterr()
        output_data = json.loads(captured.out)
        assert output_data["name"] == "test"
        assert output_data["value"] == 42

    def test_print_list_of_basemodel(self, capsys):
        """Test print method with list of BaseModel."""
        printer = CliPrinter()
        models = [
            SampleModel(name="model1", value=1),
            SampleModel(name="model2", value=2),
        ]
        printer.print(models)

        captured = capsys.readouterr()
        output_data = json.loads(captured.out)
        assert len(output_data) == 2
        assert output_data[0]["name"] == "model1"
        assert output_data[1]["name"] == "model2"

    def test_print_string(self, capsys):
        """Test print method with string."""
        printer = CliPrinter()
        printer.print("Simple string")

        captured = capsys.readouterr()
        assert "Simple string" in captured.out

    def test_print_mail_summary(self, capsys):
        """Test print_mail method with summary."""
        printer = CliPrinter()
        mail_entry = {
            "mail": {
                "message_id": "msg123",
                "sender": {"address": "host1:alice"},
                "recipient": [{"address": "host2:bob"}],
                "message": {
                    "kind": "text",
                    "content": "Hello Bob, this is a test message",
                },
                "signature": "sig",
            },
            "metadata": {
                "timestamp": "2026-01-01T10:00:00",
                "direction": "inbound",
                "is_read": False,
                "is_handled": False,
            },
        }
        printer.print_mail(mail_entry, show_full=False)

        captured = capsys.readouterr()
        assert "msg123" in captured.out
        assert "host1:alice" in captured.out
        assert "inbound" in captured.out or "📩" in captured.out

    def test_print_mail_full(self, capsys):
        """Test print_mail method with full display."""
        printer = CliPrinter()
        mail_entry = {
            "mail": {
                "message_id": "msg456",
                "sender": {"address": "host1:alice"},
                "recipient": [{"address": "host2:bob"}],
                "message": {
                    "kind": "text",
                    "content": "Full message",
                },
                "signature": "sig",
            },
            "metadata": {
                "timestamp": "2026-01-01T11:00:00",
                "direction": "outbound",
                "is_read": True,
                "is_handled": True,
            },
        }
        printer.print_mail(mail_entry, show_full=True)

        captured = capsys.readouterr()
        assert "Full Mail:" in captured.out
        assert "msg456" in captured.out

    def test_print_mail_invoke_message(self, capsys):
        """Test print_mail with invoke message."""
        printer = CliPrinter()
        mail_entry = {
            "mail": {
                "message_id": "msg789",
                "sender": {"address": "host1:agent"},
                "recipient": [{"address": "host2:tool"}],
                "message": {
                    "kind": "invoke",
                    "payload": {
                        "tool": "search",
                        "params": {"text": "query text"},
                    },
                },
                "signature": "sig",
            },
            "metadata": {
                "timestamp": "2026-01-01T12:00:00",
                "direction": "outbound",
                "is_read": False,
                "is_handled": False,
            },
        }
        printer.print_mail(mail_entry, show_full=False)

        captured = capsys.readouterr()
        assert "invoke" in captured.out
        assert "query text" in captured.out or "search" in captured.out

    def test_print_mail_read_handled_status(self, capsys):
        """Test print_mail shows read and handled status correctly."""
        printer = CliPrinter()
        mail_entry = {
            "mail": {
                "message_id": "msg999",
                "sender": {"address": "host1:sender"},
                "recipient": [{"address": "host2:receiver"}],
                "message": {
                    "kind": "text",
                    "content": "Status test",
                },
                "signature": "sig",
            },
            "metadata": {
                "timestamp": "2026-01-01T13:00:00",
                "direction": "inbound",
                "is_read": True,
                "is_handled": True,
            },
        }
        printer.print_mail(mail_entry, show_full=False)

        captured = capsys.readouterr()
        # Should show read and handled indicators
        assert "Read:" in captured.out
        assert "Handled:" in captured.out
