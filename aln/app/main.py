"""FastAPI application entry point."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from loguru import logger

from aln.app.api import api_router
from aln.app.schemas.market import MarketStore
from aln.app.service import HostServer
from fp.utils.storage import get_storage_manager


class LifecycleLogBlock:
    """Render lifecycle logs as a highlighted star block."""

    _INNER_WIDTH = 72
    _BORDER = "*" * (_INNER_WIDTH + 4)

    @classmethod
    def _format_line(cls, content: str) -> str:
        trimmed = content[: cls._INNER_WIDTH]
        return f"* {trimmed:<{cls._INNER_WIDTH}} *"

    @classmethod
    def log(cls, title: str, details: list[str]) -> None:
        logger.info(cls._BORDER)
        logger.info(cls._format_line(title))
        for detail in details:
            logger.info(cls._format_line(detail))
        logger.info(cls._BORDER)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    host_name = os.getenv("FP_HOST_NAME")

    logger.info("Starting FP Backend...")
    logger.info("API docs: http://localhost:8000/docs")

    if host_name:
        storage = get_storage_manager()

        # Configure logging for this host
        # 需要先从config获取或创建host_uid
        from fp import FPAddress

        # 尝试从config.json获取host信息
        host_tuple = storage.get_host_by_name(host_name)
        if host_tuple:
            host_uid, host_entry = host_tuple
            address = FPAddress(address=f"{host_uid}:0")
            logger.info(f"Using existing address: {address.address}")
        else:
            # 新host，生成address
            address = FPAddress.create()
            host_uid = address.host_uid
            logger.info(f"Generated new address: {address.address}")

        # 设置日志
        log_path = storage._host_log_path(host_uid)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_format = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"
        # log_format = (
        #     "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
        #     "{name}:{function}:{line} - {message}"
        # )
        logger.add(
            str(log_path),
            rotation="10 MB",
            retention="7 days",
            compression="zip",
            format=log_format,
            level="INFO",
        )

        try:
            # 尝试从存储加载host（如果存在）
            try:
                host_runtime = HostServer.load(host_uid)
                logger.info(f"Loaded host from storage: {host_name} ({host_uid})")
            except (ValueError, FileNotFoundError):
                # Host不存在，创建新的
                logger.info(f"Creating new host: {host_name} ({host_uid})")

                # 从config获取配置
                if host_tuple:
                    bind_host = host_entry.bind_host
                    advertise_host = host_entry.advertise_host
                    port = host_entry.port
                    parent_uid = host_entry.parent_uid
                else:
                    bind_host = "0.0.0.0"
                    advertise_host = None
                    port = 7001
                    parent_uid = None

                host_runtime = HostServer(
                    name=host_name,
                    address=address,
                    bind_host=bind_host,
                    advertise_host=advertise_host,
                    port=port,
                )

                restored = host_runtime._load_entities_from_config(host_uid)
                if restored:
                    host_runtime._apply_load_policies()
                    logger.info(f"Restored {restored} entities from config")

                host_runtime.save()

            # 连接parent（如果配置了）
            # 优先使用 host_runtime 已加载的 parent_url
            if hasattr(host_runtime, 'parent_url') and host_runtime.parent_url:
                await host_runtime.connect_to_parent(host_runtime.parent_url)
            elif host_tuple and host_tuple[1].parent_uid:
                # 如果没有 parent_url，从 config.json 获取
                config = storage.load_config()
                parent_entry = config.hosts.get(host_tuple[1].parent_uid)
                if parent_entry:
                    # 使用 advertise_host（如果有）或 bind_host
                    host = parent_entry.advertise_host or parent_entry.bind_host
                    if host == "0.0.0.0":
                        host = "127.0.0.1"
                    parent_url = f"http://{host}:{parent_entry.port}"
                    host_runtime.parent_url = parent_url
                    await host_runtime.connect_to_parent(parent_url)

            app.state.host_runtime = host_runtime
            app.state.market_store = MarketStore()
            app.state.market_store.load(host_runtime.uid)

            # Detailed startup diagnostics
            owner_addr = getattr(host_runtime, "default_owner", None)
            owner_label = owner_addr.address if owner_addr else "None"
            entity_lines = []
            for ent in host_runtime.entities.values():
                ent_owner = ent.owner.address if ent.owner else "None"
                ent_kind = ent.kind.value if hasattr(ent.kind, "value") else str(ent.kind)
                entity_lines.append(
                    f"  {ent.name} ({ent.uid})  kind={ent_kind}  owner={ent_owner}"
                )

            LifecycleLogBlock.log(
                title="HOST STARTED",
                details=[
                    f"name={host_runtime.name}",
                    f"uid={host_runtime.uid}",
                    f"url={host_runtime.url}",
                    f"default_owner={owner_label}",
                    f"entities ({len(host_runtime.entities)}):",
                    *entity_lines,
                ],
            )
        except Exception as exc:
            logger.error(f"Failed to initialize host runtime for '{host_name}': {exc}")
    else:
        logger.warning("FP_HOST_NAME is not set; host runtime initialization skipped")

    yield

    host_runtime = getattr(app.state, "host_runtime", None)
    if isinstance(host_runtime, HostServer):
        LifecycleLogBlock.log(
            title="HOST STOPPING",
            details=[
                f"name={host_runtime.name}",
                f"uid={host_runtime.uid}",
                f"url={host_runtime.url}",
            ],
        )
        # Save state before shutdown
        try:
            market_store = getattr(app.state, "market_store", None)
            if isinstance(market_store, MarketStore):
                market_store.save(host_runtime.uid)
            host_runtime.save()
            logger.info(f"Host state saved: {host_runtime.name} ({host_runtime.uid})")
        except Exception as exc:
            logger.error(f"Failed to save host state: {exc}")

        await host_runtime.disconnect_from_parent()

    logger.info("Shutting down FP Backend...")


app = FastAPI(
    title="FP Backend API",
    description="Federated Protocol Backend Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/", include_in_schema=False)
def root():
    """Root endpoint - redirect to API docs."""
    return RedirectResponse(url="/docs", status_code=307)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "message": "FP Backend is running"}
