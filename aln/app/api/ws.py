"""WebSocket endpoint for host-to-host communication."""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from fp import HostWellKnown, Mail

router = APIRouter()

# 记录每个 child 的最后心跳时间
child_heartbeats: dict[str, float] = {}


async def _check_child_heartbeat(child_uid: str, websocket: WebSocket, host_runtime) -> None:
    """检测 child 心跳，超时则主动关闭连接."""
    timeout = 90  # 90秒超时（允许 3 次心跳丢失）

    while True:
        try:
            await asyncio.sleep(30)

            last_heartbeat = child_heartbeats.get(child_uid, 0)
            elapsed = time.time() - last_heartbeat

            if elapsed > timeout:
                logger.warning(f"Child {child_uid} heartbeat timeout ({elapsed:.1f}s), closing connection")
                await websocket.close(code=1000, reason="Heartbeat timeout")
                break

            # 主动发送 ping 检测
            try:
                await websocket.send_json({"type": "ping"})
                logger.debug(f"Sent ping to child {child_uid}")
            except Exception as e:
                logger.warning(f"Failed to send ping to child {child_uid}: {e}")
                break

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Heartbeat check error for child {child_uid}: {e}")
            break


@router.websocket("/ws")
async def ws_host_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for child hosts to connect.

    Protocol:
    1. Child connects and sends handshake: {"type": "handshake", "wellknown": {...}}
    2. Parent accepts and registers child connection
    3. Both sides can send mail: {"type": "mail", "data": {...}}
    """
    await websocket.accept()

    host_runtime = getattr(websocket.app.state, "host_runtime", None)
    if host_runtime is None:
        await websocket.close(code=1011, reason="Host runtime not available")
        return

    # 1. Receive handshake
    child_uid = None
    try:
        msg = await websocket.receive_json()
        if msg.get("type") != "handshake" or "wellknown" not in msg:
            await websocket.close(code=1008, reason="Expected handshake")
            return
        child_uid = msg["wellknown"]["uid"]
        host_runtime.register_child(HostWellKnown(**msg["wellknown"]))
        logger.info(f"WebSocket handshake from child: {child_uid}")
    except Exception as e:
        logger.error(f"WebSocket handshake failed: {e}")
        await websocket.close(code=1008, reason="Handshake failed")
        return

    # 2. Register child connection
    await host_runtime.accept_child_connection(child_uid, websocket)
    child_heartbeats[child_uid] = time.time()

    # 启动心跳检测
    heartbeat_task = asyncio.create_task(_check_child_heartbeat(child_uid, websocket, host_runtime))

    # 3. Listen for messages
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            if msg_type == "mail":
                mail = Mail.from_dict(data["data"])
                await host_runtime.route_mail(mail)
            elif msg_type == "ping":
                child_heartbeats[child_uid] = time.time()
                await websocket.send_json({"type": "pong"})
                logger.debug(f"Received ping from child {child_uid}")
            elif msg_type == "pong":
                child_heartbeats[child_uid] = time.time()
                logger.debug(f"Received pong from child {child_uid}")
            else:
                logger.warning(f"Unknown WS message type: {msg_type}")
    except WebSocketDisconnect:
        logger.info(f"Child host {child_uid} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error from child {child_uid}: {e}")
    finally:
        heartbeat_task.cancel()
        if child_uid:
            await host_runtime.remove_child_connection(child_uid)
            child_heartbeats.pop(child_uid, None)
