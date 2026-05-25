"""Default handler for HUMAN entities."""

from __future__ import annotations

from loguru import logger

from fp.handler import BaseHandler
from fp.message import Message


class HumanHandler(BaseHandler):
    """Human entities receive messages and notify web UI via host."""

    async def handle(self, message: Message) -> None:
        self._log_message(message, handler_name="HumanHandler")
        await self.entity.host.push_to_web(self.entity.uid, message)
