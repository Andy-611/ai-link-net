"""Validation utilities for API layer."""

from __future__ import annotations

from fastapi import HTTPException


def normalize_parent_url(parent_url: str) -> str:
    """Normalize and validate parent URL.

    Args:
        parent_url: Raw parent URL string

    Returns:
        Normalized URL

    Raises:
        HTTPException: If URL format is invalid
    """
    value = parent_url.strip().rstrip("/")
    if value.startswith("http://") or value.startswith("https://"):
        return value
    raise HTTPException(
        status_code=400,
        detail="parent_url must start with http:// or https://"
    )
