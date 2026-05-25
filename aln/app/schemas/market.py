"""Market schemas — order model and store for the marketplace."""

from __future__ import annotations

import time
from enum import Enum
from uuid import uuid4

from loguru import logger
from pydantic import BaseModel, Field


class OrderType(str, Enum):
    """Market order type."""

    DEMAND = "demand"
    SUPPLY = "supply"


class OrderStatus(str, Enum):
    """Market order lifecycle status."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class OrderCategory(str, Enum):
    """Market order scene category."""

    TASK = "task"
    MATCHMAKING = "matchmaking"
    JOB = "job"
    SECONDHAND = "secondhand"
    SERVICE = "service"


class TradeMode(str, Enum):
    """How the order is fulfilled."""

    FACILITATION = "facilitation"
    AUTONOMOUS = "autonomous"


def infer_trade_mode(category: OrderCategory | None) -> TradeMode:
    """Derive trade mode from category: task → autonomous, others → facilitation."""
    if category == OrderCategory.TASK:
        return TradeMode.AUTONOMOUS
    return TradeMode.FACILITATION


class MarketOrder(BaseModel):
    """A marketplace listing hosted by the app layer."""

    order_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    order_type: OrderType
    publisher: str = Field(description="Publisher entity_uid")
    publisher_address: str = Field(default="", description="Publisher FPAddress string")
    title: str
    description: str = ""
    budget: float | None = None
    tags: list[str] = Field(default_factory=list)
    category: OrderCategory | None = None
    trade_mode: TradeMode = TradeMode.FACILITATION
    status: OrderStatus = OrderStatus.ACTIVE
    created_at: float = Field(default_factory=time.time)
    archived_at: float | None = None


class PublishOrderRequest(BaseModel):
    """Request to publish a new market order."""

    order_type: OrderType
    publisher: str = Field(description="Publisher entity_uid")
    publisher_address: str = Field(default="", description="Publisher FPAddress string (host_uid:entity_uid)")
    title: str
    description: str = ""
    budget: float | None = None
    tags: list[str] = Field(default_factory=list)
    category: OrderCategory | None = None
    trade_mode: TradeMode = TradeMode.FACILITATION


class MarketStoreSnapshot(BaseModel):
    """Serializable snapshot of MarketStore."""

    orders: list[MarketOrder] = Field(default_factory=list)


class MarketStore:
    """In-memory market order store, lives in app layer."""

    def __init__(self) -> None:
        self._orders: dict[str, MarketOrder] = {}

    def save(self, host_uid: str) -> None:
        """Persist all orders to disk."""
        from fp.utils.storage import get_storage_manager
        snapshot = MarketStoreSnapshot(orders=list(self._orders.values()))
        get_storage_manager().save_market_state(host_uid, snapshot)
        logger.info(f"[MarketStore] Saved {len(self._orders)} orders")

    def load(self, host_uid: str) -> None:
        """Restore orders from disk."""
        from fp.utils.storage import get_storage_manager
        raw = get_storage_manager().load_market_state_raw(host_uid)
        if raw is None:
            return
        snapshot = MarketStoreSnapshot.model_validate_json(raw)
        self._orders = {o.order_id: o for o in snapshot.orders}
        logger.info(f"[MarketStore] Loaded {len(self._orders)} orders")

    def publish(self, request: PublishOrderRequest, publisher_address: str = "") -> MarketOrder:
        """Create and store a new market order."""
        order = MarketOrder(
            order_type=request.order_type,
            publisher=request.publisher,
            publisher_address=publisher_address,
            title=request.title,
            description=request.description,
            budget=request.budget,
            tags=request.tags,
            category=request.category,
            trade_mode=request.trade_mode,
        )
        self._orders[order.order_id] = order
        return order

    def get(self, order_id: str) -> MarketOrder | None:
        return self._orders.get(order_id)

    def list_orders(
        self,
        order_type: OrderType | None = None,
        status: OrderStatus | None = None,
        publisher: str | None = None,
        category: OrderCategory | None = None,
        trade_mode: TradeMode | None = None,
    ) -> list[MarketOrder]:
        """List orders with optional filters."""
        result = list(self._orders.values())
        if order_type is not None:
            result = [o for o in result if o.order_type == order_type]
        if status is not None:
            result = [o for o in result if o.status == status]
        if publisher is not None:
            result = [o for o in result if o.publisher == publisher]
        if category is not None:
            result = [o for o in result if o.category == category]
        if trade_mode is not None:
            result = [o for o in result if o.trade_mode == trade_mode]
        return sorted(result, key=lambda o: o.created_at, reverse=True)

    def archive(self, order_id: str, requester_uid: str) -> MarketOrder | None:
        """Archive an order. Only the publisher can archive."""
        order = self._orders.get(order_id)
        if order is None or order.publisher != requester_uid:
            return None
        order.status = OrderStatus.ARCHIVED
        order.archived_at = time.time()
        return order

    def delete(self, order_id: str, requester_uid: str) -> bool:
        """Delete an order. Only the publisher can delete."""
        order = self._orders.get(order_id)
        if order is None or order.publisher != requester_uid:
            return False
        del self._orders[order_id]
        return True

    def remove_orders_by_host_uid(self, host_uid: str) -> int:
        """Remove all orders published from a specific host."""
        prefix = f"{host_uid}:"
        to_remove = [
            oid for oid, o in self._orders.items()
            if o.publisher_address.startswith(prefix)
        ]
        for oid in to_remove:
            del self._orders[oid]
        return len(to_remove)
