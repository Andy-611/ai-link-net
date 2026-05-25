"""Filesystem browsing API for directory selection."""

from pathlib import Path

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/fs", tags=["filesystem"])


class DirListResponse(BaseModel):
    """Response for directory listing."""
    current: str
    parent: str | None
    dirs: list[str]


@router.get("/dirs", response_model=DirListResponse)
async def list_dirs(path: str = Query("~", description="Directory path to list")) -> DirListResponse:
    """List subdirectories of a given path."""
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_dir():
        resolved = resolved.parent

    dirs: list[str] = sorted(
        d.name for d in resolved.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )
    parent = str(resolved.parent) if resolved != resolved.parent else None
    return DirListResponse(current=str(resolved), parent=parent, dirs=dirs)
