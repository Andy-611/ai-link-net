"""Serve the packaged AI-Link-Net Web application."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


def get_web_root() -> Path:
    """Return the packaged production Web directory."""
    return Path(__file__).resolve().parent / "web" / "dist"


class SPARequestHandler(SimpleHTTPRequestHandler):
    """Serve static assets and fall back to index.html for client routes."""

    def __init__(self, *args, directory: str, **kwargs) -> None:
        self.web_root = Path(directory).resolve()
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self) -> None:
        request_path = unquote(urlparse(self.path).path).lstrip("/")
        requested_file = (self.web_root / request_path).resolve()
        try:
            requested_file.relative_to(self.web_root)
        except ValueError:
            self.send_error(404, "File not found")
            return

        if requested_file.exists():
            super().do_GET()
            return

        if Path(request_path).suffix:
            self.send_error(404, "File not found")
            return

        self.path = "/index.html"
        super().do_GET()


def serve(host: str, port: int, web_root: Path | None = None) -> None:
    """Serve the production Web build until the process is stopped."""
    root = (web_root or get_web_root()).resolve()
    index_path = root / "index.html"
    if not index_path.is_file():
        raise FileNotFoundError(
            f"Packaged Web UI not found at {index_path}. "
            "Install an official AI-Link-Net release or run `npm run build`."
        )

    handler = partial(SPARequestHandler, directory=str(root))
    server = ThreadingHTTPServer((host, port), handler)
    server.serve_forever()


def main(argv: list[str] | None = None) -> int:
    """Run the packaged Web server from the command line."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5173)
    args = parser.parse_args(argv)
    serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
