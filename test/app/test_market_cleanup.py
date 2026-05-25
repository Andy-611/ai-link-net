"""Tests for market order cleanup when a child host is removed."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from aln.app.api.v1.children import delete_child
from aln.app.schemas.market import (
    MarketStore,
    OrderType,
    PublishOrderRequest,
)
from fp import Host
from fp.core.base import EntityKind


def _make_publish_request(publisher: str, title: str) -> PublishOrderRequest:
    return PublishOrderRequest(
        order_type=OrderType.DEMAND,
        publisher=publisher,
        title=title,
    )


def _setup_parent_with_child() -> tuple[Host, Host, str, str]:
    """Create a parent host with one registered child, return (parent, child, child_uid, entity_uid)."""
    parent = Host(name="ParentHost")
    child = Host(name="ChildHost")
    parent._set_child_host(child)

    entity = child.register_entity(name="Alice", kind=EntityKind.HUMAN)
    return parent, child, child.uid, entity.uid


class TestMarketStoreRemoveByHost:
    """Unit tests for MarketStore.remove_orders_by_host_uid."""

    def test_removes_matching_orders(self):
        store = MarketStore()
        host_a = "host_aaa"
        store.publish(_make_publish_request("e1", "Order 1"), publisher_address=f"{host_a}:e1")
        store.publish(_make_publish_request("e2", "Order 2"), publisher_address=f"{host_a}:e2")

        removed = store.remove_orders_by_host_uid(host_a)

        assert removed == 2
        assert store.list_orders() == []

    def test_preserves_other_hosts_orders(self):
        store = MarketStore()
        host_a = "host_aaa"
        host_b = "host_bbb"
        store.publish(_make_publish_request("e1", "A's order"), publisher_address=f"{host_a}:e1")
        store.publish(_make_publish_request("e2", "B's order"), publisher_address=f"{host_b}:e2")

        removed = store.remove_orders_by_host_uid(host_a)

        assert removed == 1
        remaining = store.list_orders()
        assert len(remaining) == 1
        assert remaining[0].title == "B's order"

    def test_returns_zero_when_no_match(self):
        store = MarketStore()
        store.publish(_make_publish_request("e1", "Order"), publisher_address="host_x:e1")

        removed = store.remove_orders_by_host_uid("host_nonexistent")

        assert removed == 0
        assert len(store.list_orders()) == 1

    def test_empty_store(self):
        store = MarketStore()
        assert store.remove_orders_by_host_uid("any_host") == 0

    def test_no_false_positive_on_prefix_overlap(self):
        """host_a should not match host_aaa."""
        store = MarketStore()
        store.publish(_make_publish_request("e1", "Order"), publisher_address="host_aaa:e1")

        removed = store.remove_orders_by_host_uid("host_a")

        assert removed == 0
        assert len(store.list_orders()) == 1


class TestDeleteChildCleansMarketOrders:
    """Integration test: DELETE /children/{uid} cleans up market orders."""

    def test_delete_child_removes_orders(self):
        parent, _, child_uid, entity_uid = _setup_parent_with_child()

        store = MarketStore()
        store.publish(
            _make_publish_request(entity_uid, "Child order"),
            publisher_address=f"{child_uid}:{entity_uid}",
        )
        store.publish(
            _make_publish_request("local_e", "Parent order"),
            publisher_address=f"{parent.uid}:local_e",
        )
        assert len(store.list_orders()) == 2

        response = delete_child(child_uid, current_host=parent, market_store=store)

        assert response.success is True
        remaining = store.list_orders()
        assert len(remaining) == 1
        assert remaining[0].title == "Parent order"

    def test_delete_child_404_for_unknown_uid(self):
        parent, _, _, _ = _setup_parent_with_child()
        store = MarketStore()

        with pytest.raises(HTTPException) as exc_info:
            delete_child("nonexistent_uid", current_host=parent, market_store=store)
        assert exc_info.value.status_code == 404

    def test_delete_child_no_orders_still_succeeds(self):
        parent, _, child_uid, _ = _setup_parent_with_child()
        store = MarketStore()

        response = delete_child(child_uid, current_host=parent, market_store=store)

        assert response.success is True
        assert child_uid not in parent.child_hosts
