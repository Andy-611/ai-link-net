"""Tests for CLI wrapper decorators."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import click
import pytest

from aln.app import HostClientError
from aln.cli.misc.wrappers import (
    cli_exception_wrapper,
    get_cli_printer,
    get_host_client,
    get_storage,
)


class TestCliExceptionWrapper:
    """Test cli_exception_wrapper decorator."""

    def test_wrapper_success(self):
        """Test wrapper allows successful execution."""

        @cli_exception_wrapper(error_message="Test failed")
        def successful_func():
            return "success"

        result = successful_func()
        assert result == "success"

    def test_wrapper_click_exception_passthrough(self):
        """Test wrapper passes through click exceptions."""

        @cli_exception_wrapper(error_message="Test failed")
        def raise_click_exception():
            raise click.ClickException("Click error")

        with pytest.raises(click.ClickException):
            raise_click_exception()

    def test_wrapper_host_client_error(self, capsys):
        """Test wrapper handles HostClientError."""

        @cli_exception_wrapper(error_message="Test failed")
        def raise_host_error():
            raise HostClientError("Connection refused")

        with pytest.raises(SystemExit) as exc_info:
            raise_host_error()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Host Error" in captured.out
        assert "Connection refused" in captured.out

    def test_wrapper_json_decode_error(self, capsys):
        """Test wrapper handles JSONDecodeError."""

        @cli_exception_wrapper(error_message="Test failed")
        def raise_json_error():
            raise json.JSONDecodeError("Invalid JSON", "", 0)

        with pytest.raises(SystemExit) as exc_info:
            raise_json_error()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Config Error" in captured.out

    def test_wrapper_generic_error(self, capsys):
        """Test wrapper handles generic errors."""

        @cli_exception_wrapper(error_message="Test failed")
        def raise_generic_error():
            raise ValueError("Something went wrong")

        with pytest.raises(SystemExit) as exc_info:
            raise_generic_error()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out
        assert "Test failed" in captured.out
        assert "Something went wrong" in captured.out


class TestGetHostClient:
    """Test get_host_client decorator."""

    def test_injects_client(self):
        """Test decorator injects HostClient."""
        with patch("aln.cli.misc.wrappers.get_storage_manager") as mock_get_storage, \
             patch("aln.cli.misc.wrappers.HostClient") as mock_host_client_cls:

            mock_storage = MagicMock()
            mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
            mock_get_storage.return_value = mock_storage

            mock_client = MagicMock()
            mock_host_client_cls.return_value = mock_client

            @get_host_client
            def test_func(host_name: str, client: HostClientType):
                return client

            result = test_func(host_name="default")
            assert result == mock_client

    def test_uses_fallback_name(self):
        """Test decorator uses fallback parameter name."""
        with patch("aln.cli.misc.wrappers.get_storage_manager") as mock_get_storage, \
             patch("aln.cli.misc.wrappers.HostClient") as mock_host_client_cls:

            mock_storage = MagicMock()
            mock_storage.get_host_url.return_value = "http://0.0.0.0:7001"
            mock_get_storage.return_value = mock_storage

            mock_client = MagicMock()
            mock_host_client_cls.return_value = mock_client

            @get_host_client
            def test_func(host_name: str, host_client: HostClientType):
                return host_client

            result = test_func(host_name="default")
            assert result == mock_client


class TestGetCliPrinter:
    """Test get_cli_printer decorator."""

    def test_injects_printer(self):
        """Test decorator injects CliPrinter."""

        @get_cli_printer
        def test_func(cli_printer):
            return cli_printer

        result = test_func()
        from aln.cli.misc.printer import CliPrinter

        assert isinstance(result, CliPrinter)


class TestGetStorage:
    """Test get_storage decorator."""

    def test_injects_storage(self):
        """Test decorator injects StorageManager."""
        with patch("aln.cli.misc.wrappers.get_storage_manager") as mock_get_storage:
            mock_storage = MagicMock()
            mock_get_storage.return_value = mock_storage

            @get_storage
            def test_func(storage):
                return storage

            result = test_func()
            assert result == mock_storage


class TestInjectKeywordArgument:
    """Test _inject_keyword_argument helper."""

    def test_inject_preferred_name(self):
        """Test injecting with preferred name."""
        from aln.cli.misc.wrappers import _inject_keyword_argument

        def func(preferred: str, other: int):
            pass

        kwargs = {"other": 42}
        result = _inject_keyword_argument(
            func, kwargs, "value", "preferred", "fallback"
        )

        assert result == {"other": 42, "preferred": "value"}

    def test_inject_fallback_name(self):
        """Test injecting with fallback name."""
        from aln.cli.misc.wrappers import _inject_keyword_argument

        def func(fallback: str, other: int):
            pass

        kwargs = {"other": 42}
        result = _inject_keyword_argument(
            func, kwargs, "value", "preferred", "fallback"
        )

        assert result == {"other": 42, "fallback": "value"}

    def test_inject_when_neither_exists(self):
        """Test injecting when neither name exists in function signature."""
        from aln.cli.misc.wrappers import _inject_keyword_argument

        def func(other: int):
            pass

        kwargs = {"other": 42}
        result = _inject_keyword_argument(
            func, kwargs, "value", "preferred", "fallback"
        )

        assert result == {"other": 42, "preferred": "value"}


# Type hint for testing
HostClientType = type(MagicMock())
