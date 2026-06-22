"""Tests for the packaged Web UI runtime."""

from __future__ import annotations

import threading
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib import error, request

import pytest

from aln.cli import ui
from aln.web_server import SPARequestHandler


@pytest.fixture
def web_root(tmp_path: Path) -> Path:
    """Create a minimal production-style Web build."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<main>AI-Link-Net</main>")
    (tmp_path / "assets" / "app.js").write_text("console.log('aln')")
    return tmp_path


@pytest.fixture
def web_server(web_root: Path):
    """Run the static handler on an ephemeral local port."""
    handler = partial(SPARequestHandler, directory=str(web_root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_static_server_serves_assets(web_server: str) -> None:
    """Serve compiled assets directly from the packaged directory."""
    with request.urlopen(f"{web_server}/assets/app.js") as response:
        assert response.read() == b"console.log('aln')"


def test_static_server_falls_back_for_spa_routes(web_server: str) -> None:
    """Return index.html for React Router paths."""
    with request.urlopen(f"{web_server}/trade/contracts/abc") as response:
        assert response.read() == b"<main>AI-Link-Net</main>"


def test_static_server_returns_404_for_missing_assets(web_server: str) -> None:
    """Do not hide broken asset URLs behind the SPA entry point."""
    with pytest.raises(error.HTTPError) as exc_info:
        request.urlopen(f"{web_server}/assets/missing.js")
    assert exc_info.value.code == 404


@patch("aln.cli.ui.get_local_ip", return_value="localhost")
@patch("aln.cli.ui._wait_until_ready", return_value=True)
@patch("aln.cli.ui._spawn_ui_process")
@patch("aln.cli.ui._get_ui_status", return_value=None)
@patch("aln.cli.ui.get_fp_home")
@patch("aln.cli.ui.get_web_root")
def test_start_ui_uses_packaged_build_without_npm(
    mock_get_web_root,
    mock_get_fp_home,
    _mock_status,
    mock_spawn,
    _mock_wait,
    _mock_local_ip,
    web_root: Path,
    tmp_path: Path,
) -> None:
    """Start the Python static server without installing Node dependencies."""
    process = MagicMock(pid=4321)
    mock_get_web_root.return_value = web_root
    mock_get_fp_home.return_value = tmp_path
    mock_spawn.return_value = process

    assert ui.start_ui(5199) == 4321
    mock_spawn.assert_called_once_with(5199, tmp_path / "logs" / "ui.log")
    assert (tmp_path / "ui.pid").read_text() == "4321"
    assert (tmp_path / "ui.port").read_text() == "5199"


@patch("aln.cli.ui.subprocess.Popen")
def test_spawn_ui_process_runs_python_module(mock_popen, tmp_path: Path) -> None:
    """Launch `aln.web_server`, never npm or Vite."""
    mock_popen.return_value = MagicMock()

    ui._spawn_ui_process(5173, tmp_path / "ui.log")

    command = mock_popen.call_args.args[0]
    assert command[1:] == [
        "-m",
        "aln.web_server",
        "--host",
        "0.0.0.0",
        "--port",
        "5173",
    ]
    assert "npm" not in command
