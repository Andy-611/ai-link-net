"""Mail API - receive and route mail."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from loguru import logger

from fp import Host, Mail
from aln.app.misc.provider import get_host_runtime
from aln.app.schemas import StandardResponse

router = APIRouter(tags=["mail"])


@router.post("/mail", response_model=StandardResponse[dict])
async def send_mail(
    # NOTE: 使用 dict 因为 Mail 需要通过 from_dict() 注入 cryptor，不能直接用 Pydantic 自动解析
    mail_data: dict[str, Any],
    host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[dict]:
    """Receive mail and route to destination entity."""
    mail = Mail.from_dict(mail_data)
    await host.route_mail(mail)

    # Extract message_id if available
    message_id = ""
    if hasattr(mail.message, "message_id"):
        message_id = mail.message.message_id

    return StandardResponse[dict](
        success=True,
        message="Mail routed successfully",
        data={"message_id": message_id, "status": "delivered"},
    )
