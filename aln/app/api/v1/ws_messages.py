"""WebSocket endpoint for real-time message updates."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

router = APIRouter(prefix="/ws", tags=["websocket"])


class ConnectionManager:
    """Manage WebSocket connections for entities."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(
        self,
        entity_uid: str,
        websocket: WebSocket,
        entity_kind: str,
        host_runtime,
    ) -> None:
        """Add websocket to active connections."""
        if entity_uid not in self.active_connections:
            self.active_connections[entity_uid] = []
        self.active_connections[entity_uid].append(websocket)
        logger.info(f"[WS] Entity {entity_uid} connected, total: {len(self.active_connections[entity_uid])}")
        _ = entity_kind, host_runtime

    async def disconnect(
        self,
        entity_uid: str,
        websocket: WebSocket,
        entity_kind: str,
        host_runtime,
    ) -> None:
        """Remove websocket from active connections."""
        if entity_uid in self.active_connections:
            self.active_connections[entity_uid].remove(websocket)
            if not self.active_connections[entity_uid]:
                del self.active_connections[entity_uid]
                logger.info(f"[WS] Entity {entity_uid} disconnected (all connections closed)")
            else:
                logger.info(f"[WS] Entity {entity_uid} disconnected (remaining: {len(self.active_connections[entity_uid])})")
        _ = entity_kind, host_runtime

    async def send_message(self, entity_uid: str, message: dict):
        """Send message to all connections of an entity."""
        if entity_uid not in self.active_connections:
            logger.debug(f"[WS] 无活跃连接 for {entity_uid}, 消息类型: {message.get('type')}")
            return

        logger.debug(
            f"[WS] 📡 发送消息 to {entity_uid} | "
            f"类型: {message.get('type')} | 连接数: {len(self.active_connections[entity_uid])}"
        )

        disconnected = []
        for connection in self.active_connections[entity_uid]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"[WS] Failed to send to {entity_uid}: {e}")
                disconnected.append(connection)

        for conn in disconnected:
            # Note: We can't notify parent here since we don't have entity_kind/host_runtime
            # This is just cleanup, actual disconnect notification happens in ws_messages_endpoint
            if entity_uid in self.active_connections:
                self.active_connections[entity_uid].remove(conn)
                if not self.active_connections[entity_uid]:
                    del self.active_connections[entity_uid]

manager = ConnectionManager()


@router.websocket("/messages/{entity_uid}")
async def ws_messages_endpoint(
    websocket: WebSocket,
    entity_uid: str,
):
    """WebSocket endpoint for real-time message updates.

    Protocol:
    - Client connects with entity_uid
    - Server sends new messages as they arrive: {"type": "new_message", "data": {...}}
    - Client sends ping: {"type": "ping"}, server responds with pong: {"type": "pong"}
    """
    logger.info(f"[WS] 收到连接请求 from entity_uid={entity_uid}")

    try:
        await websocket.accept()
        logger.info(f"[WS] WebSocket 已接受连接 for entity_uid={entity_uid}")
    except Exception as e:
        logger.error(f"[WS] 接受连接失败: {e}")
        return

    current_host = getattr(websocket.app.state, "host_runtime", None)
    if current_host is None:
        logger.error(f"[WS] Host runtime not available")
        await websocket.close(code=1011, reason="Host runtime not available")
        return

    entity = current_host.get_entity(entity_uid)
    if entity is None:
        logger.error(f"[WS] Entity not found: {entity_uid}")
        await websocket.send_json({
            "type": "entity_not_found",
            "data": {"entity_uid": entity_uid}
        })
        await websocket.close(code=1008, reason=f"Entity not found: {entity_uid}")
        return

    entity_kind = entity.kind.value if hasattr(entity.kind, 'value') else str(entity.kind)
    logger.info(f"[WS] 准备注册连接: entity_uid={entity_uid}, kind={entity_kind}")
    await manager.connect(entity_uid, websocket, entity_kind, current_host)

    try:
        logger.info(f"[WS] 开始消息循环 for {entity_uid}")
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                logger.debug(f"[WS] Ping-Pong with {entity_uid}")
            else:
                logger.warning(f"[WS] Unknown message type from {entity_uid}: {msg_type}")

    except WebSocketDisconnect:
        logger.info(f"[WS] Entity {entity_uid} disconnected normally")
    except Exception as e:
        logger.error(f"[WS] Error for entity {entity_uid}: {e}")
        import traceback
        logger.error(f"[WS] Traceback: {traceback.format_exc()}")
    finally:
        logger.info(f"[WS] 清理连接 for {entity_uid}")
        await manager.disconnect(entity_uid, websocket, entity_kind, current_host)


async def notify_new_message(entity_uid: str, message_data: dict):
    """Notify entity about new message via WebSocket."""
    await manager.send_message(
        entity_uid,
        {"type": "new_message", "data": message_data}
    )


async def notify_status_update(entity_uid: str, status_data: dict):
    """Notify entity about mail status update via WebSocket.

    Args:
        entity_uid: The entity UID to notify
        status_data: Status update data including message_id, status, timestamp
    """
    await manager.send_message(
        entity_uid,
        {"type": "status_update", "data": status_data}
    )


async def notify_delivery_status(
    sender_entity_uid: str,
    message_id: str,
    recipient_address: str,
    status: str,
    reason: str | None = None,
):
    """Notify sender about message delivery status via WebSocket.

    Args:
        sender_entity_uid: The entity UID of the sender
        message_id: Original message ID
        recipient_address: Full recipient address (host_uid:entity_uid)
        status: "delivered" | "queued" | "failed"
        reason: Optional reason for non-delivered status
    """
    from datetime import datetime

    status_data = {
        "message_id": message_id,
        "recipient": recipient_address,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if reason:
        status_data["reason"] = reason

    await manager.send_message(
        sender_entity_uid,
        {"type": "delivery_status", "data": status_data}
    )
