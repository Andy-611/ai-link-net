"""Best-effort PyPI update discovery."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib import request

from fp import get_fp_home
from packaging.version import InvalidVersion, Version

PACKAGE_NAME = "ai-link-net"
PYPI_JSON_URL = f"https://pypi.org/pypi/{PACKAGE_NAME}/json"
UPDATE_CHECK_INTERVAL_SECONDS = 24 * 60 * 60
UPDATE_CHECK_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True, slots=True)
class UpdateCheckResult:
    """Result of comparing the installed and published package versions."""

    current_version: str
    latest_version: str
    update_available: bool
    from_cache: bool


def _get_current_version() -> str:
    """Return the installed AI-Link-Net version."""
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return "0.1.0"


def _default_cache_path() -> Path:
    """Return the update-check cache path."""
    return Path(get_fp_home()) / "update-check.json"


def _fetch_latest_version() -> str:
    """Fetch the latest published version from PyPI."""
    req = request.Request(
        PYPI_JSON_URL,
        headers={"Accept": "application/json", "User-Agent": f"{PACKAGE_NAME}-update-check"},
    )
    with request.urlopen(req, timeout=UPDATE_CHECK_TIMEOUT_SECONDS) as response:
        payload = json.load(response)
    return _select_latest_stable(payload)


def _select_latest_stable(payload: dict) -> str:
    """Select the newest stable version from a PyPI project response."""
    stable_versions: list[Version] = []
    for raw_version in payload.get("releases", {}):
        try:
            parsed = Version(str(raw_version))
        except InvalidVersion:
            continue
        if not parsed.is_prerelease:
            stable_versions.append(parsed)

    if stable_versions:
        return str(max(stable_versions))

    fallback = Version(str(payload["info"]["version"]))
    return str(fallback)


def _read_cache(cache_path: Path) -> tuple[float, str] | None:
    """Read a valid update cache entry."""
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        return float(payload["checked_at"]), str(payload["latest_version"])
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None


def _write_cache(cache_path: Path, checked_at: float, latest_version: str) -> None:
    """Persist a successful update check."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {"checked_at": checked_at, "latest_version": latest_version},
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def _is_update_available(current_version: str, latest_version: str) -> bool:
    """Return whether latest is a newer stable version."""
    try:
        current = Version(current_version)
        latest = Version(latest_version)
    except InvalidVersion:
        return False
    return not latest.is_prerelease and latest > current


def check_for_update(
    *,
    force: bool = False,
    now: float | None = None,
    cache_path: Path | None = None,
) -> UpdateCheckResult | None:
    """Check PyPI for a newer version without raising user-facing errors."""
    if os.getenv("ALN_DISABLE_UPDATE_CHECK") == "1":
        return None

    checked_at = time.time() if now is None else now
    resolved_cache_path = cache_path or _default_cache_path()
    current_version = _get_current_version()
    cached = _read_cache(resolved_cache_path)

    if not force:
        if cached is not None:
            cached_at, latest_version = cached
            if checked_at - cached_at < UPDATE_CHECK_INTERVAL_SECONDS:
                return UpdateCheckResult(
                    current_version=current_version,
                    latest_version=latest_version,
                    update_available=_is_update_available(
                        current_version,
                        latest_version,
                    ),
                    from_cache=True,
                )

    try:
        latest_version = _fetch_latest_version()
        _write_cache(resolved_cache_path, checked_at, latest_version)
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        previous_latest = cached[1] if cached is not None else current_version
        try:
            _write_cache(resolved_cache_path, checked_at, previous_latest)
        except OSError:
            pass
        return None

    return UpdateCheckResult(
        current_version=current_version,
        latest_version=latest_version,
        update_available=_is_update_available(current_version, latest_version),
        from_cache=False,
    )


def format_update_notice(result: UpdateCheckResult) -> str | None:
    """Format the CLI notice for an available update."""
    if not result.update_available:
        return None
    return (
        f"Update available: ai-link-net {result.current_version} -> "
        f"{result.latest_version}. Run `aln update` to upgrade."
    )
