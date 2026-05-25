"""Root .well-known discovery endpoint for host metadata."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from fp import Host, HostWellKnown
from aln.app.misc.provider import get_host_runtime
from aln.app.schemas import StandardResponse
from aln.app.endpoint import ENDPOINT

router = APIRouter(tags=["well-known"])


@router.get(
    ENDPOINT.WELL_KNOWN,
    response_model=StandardResponse[HostWellKnown],
    summary="Host discovery document",
)
def well_known(
    host_server: Host = Depends(get_host_runtime),
) -> StandardResponse[HostWellKnown]:
    return StandardResponse[HostWellKnown](
        # NOTE:按照我的 FORMATTER 规范，比较简短的内容，最后不要加 , 这样会自动格式化为一行，如果比较长，想要多行，你再加 ,
        success=True,
        message="ok",
        data=host_server.get_wellknown(),
    )
