"""Tests for best-effort PyPI update discovery."""

from __future__ import annotations

import json

import aln.cli as cli_module
from aln.cli import update_check


def test_recent_cache_avoids_network_and_reports_update(tmp_path, monkeypatch) -> None:
    """Reuse a recent cached version without contacting PyPI."""
    cache_path = tmp_path / "update-check.json"
    cache_path.write_text(
        json.dumps({"checked_at": 1_000.0, "latest_version": "0.2.0"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(update_check, "_get_current_version", lambda: "0.1.0")

    def fail_fetch() -> str:
        raise AssertionError("network should not be used for a recent cache")

    monkeypatch.setattr(update_check, "_fetch_latest_version", fail_fetch)

    result = update_check.check_for_update(
        now=1_000.0 + update_check.UPDATE_CHECK_INTERVAL_SECONDS - 1,
        cache_path=cache_path,
    )

    assert result is not None
    assert result.current_version == "0.1.0"
    assert result.latest_version == "0.2.0"
    assert result.update_available is True
    assert result.from_cache is True


def test_stale_cache_fetches_and_persists_latest_version(
    tmp_path,
    monkeypatch,
) -> None:
    """Refresh stale cache data and persist the successful check."""
    cache_path = tmp_path / "update-check.json"
    cache_path.write_text(
        json.dumps({"checked_at": 1_000.0, "latest_version": "0.1.0"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(update_check, "_get_current_version", lambda: "0.1.0")
    monkeypatch.setattr(update_check, "_fetch_latest_version", lambda: "0.2.0")

    result = update_check.check_for_update(
        now=1_000.0 + update_check.UPDATE_CHECK_INTERVAL_SECONDS,
        cache_path=cache_path,
    )

    assert result is not None
    assert result.update_available is True
    assert result.from_cache is False
    assert json.loads(cache_path.read_text(encoding="utf-8")) == {
        "checked_at": 1_000.0 + update_check.UPDATE_CHECK_INTERVAL_SECONDS,
        "latest_version": "0.2.0",
    }


def test_force_check_bypasses_recent_cache(tmp_path, monkeypatch) -> None:
    """Force a network refresh even when the cache is recent."""
    cache_path = tmp_path / "update-check.json"
    cache_path.write_text(
        json.dumps({"checked_at": 2_000.0, "latest_version": "0.1.0"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(update_check, "_get_current_version", lambda: "0.1.0")
    monkeypatch.setattr(update_check, "_fetch_latest_version", lambda: "0.3.0")

    result = update_check.check_for_update(
        force=True,
        now=2_001.0,
        cache_path=cache_path,
    )

    assert result is not None
    assert result.latest_version == "0.3.0"
    assert result.update_available is True
    assert result.from_cache is False


def test_equal_version_is_not_an_update(tmp_path, monkeypatch) -> None:
    """Do not report the installed version as an update."""
    monkeypatch.setattr(update_check, "_get_current_version", lambda: "0.2.0")
    monkeypatch.setattr(update_check, "_fetch_latest_version", lambda: "0.2.0")

    result = update_check.check_for_update(
        force=True,
        now=3_000.0,
        cache_path=tmp_path / "update-check.json",
    )

    assert result is not None
    assert result.update_available is False


def test_prerelease_is_not_reported_as_a_stable_update(
    tmp_path,
    monkeypatch,
) -> None:
    """Ignore prerelease versions returned by the package index."""
    monkeypatch.setattr(update_check, "_get_current_version", lambda: "0.2.0")
    monkeypatch.setattr(update_check, "_fetch_latest_version", lambda: "0.3.0rc1")

    result = update_check.check_for_update(
        force=True,
        now=4_000.0,
        cache_path=tmp_path / "update-check.json",
    )

    assert result is not None
    assert result.latest_version == "0.3.0rc1"
    assert result.update_available is False


def test_pypi_payload_selects_highest_stable_release() -> None:
    """Prefer the newest stable release when PyPI also contains prereleases."""
    payload = {
        "info": {"version": "0.3.0rc1"},
        "releases": {
            "0.1.0": [],
            "0.2.1": [],
            "0.3.0rc1": [],
            "invalid": [],
        },
    }

    assert update_check._select_latest_stable(payload) == "0.2.1"


def test_disabled_check_returns_none_without_network(
    tmp_path,
    monkeypatch,
) -> None:
    """Honor the environment switch that disables update discovery."""
    monkeypatch.setenv("ALN_DISABLE_UPDATE_CHECK", "1")

    def fail_fetch() -> str:
        raise AssertionError("network should not be used when checks are disabled")

    monkeypatch.setattr(update_check, "_fetch_latest_version", fail_fetch)

    assert (
        update_check.check_for_update(
            force=True,
            cache_path=tmp_path / "update-check.json",
        )
        is None
    )


def test_network_failure_is_silent_and_throttles_the_next_attempt(
    tmp_path,
    monkeypatch,
) -> None:
    """Keep the known version and record the failed attempt time."""
    cache_path = tmp_path / "update-check.json"
    original = {"checked_at": 1_000.0, "latest_version": "0.1.0"}
    cache_path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(update_check, "_get_current_version", lambda: "0.1.0")

    def fail_fetch() -> str:
        raise OSError("offline")

    monkeypatch.setattr(update_check, "_fetch_latest_version", fail_fetch)

    result = update_check.check_for_update(
        force=True,
        now=5_000.0,
        cache_path=cache_path,
    )

    assert result is None
    assert json.loads(cache_path.read_text(encoding="utf-8")) == {
        "checked_at": 5_000.0,
        "latest_version": original["latest_version"],
    }


def test_cli_main_prints_available_update_notice(monkeypatch, capsys) -> None:
    """Print the cached update notice after a successful command."""
    result = update_check.UpdateCheckResult(
        current_version="0.1.0",
        latest_version="0.2.0",
        update_available=True,
        from_cache=True,
    )
    monkeypatch.setattr(cli_module.cli, "main", lambda **_kwargs: None)
    monkeypatch.setattr(cli_module, "check_for_update", lambda: result)

    assert cli_module.main(["status"]) == 0
    assert "Run `aln update` to upgrade" in capsys.readouterr().err


def test_cli_main_skips_background_check_for_update_command(
    monkeypatch,
) -> None:
    """Let the explicit update command own its forced version check."""
    monkeypatch.setattr(cli_module.cli, "main", lambda **_kwargs: None)

    def fail_check():
        raise AssertionError("background check should be skipped")

    monkeypatch.setattr(cli_module, "check_for_update", fail_check)

    assert cli_module.main(["update", "--check"]) == 0
