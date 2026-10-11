"""Offline business contract tests; no model or external services."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest


@pytest.fixture
def service(tmp_path):
    from aftersales.service import AfterSalesService
    orders = [
        {"order_id": "recent", "product": "键盘", "status": "delivered", "delivered_at": "2026-10-04", "supports_no_reason": True, "logistics": "已签收"},
        {"order_id": "old", "product": "鼠标", "status": "delivered", "delivered_at": "2026-10-03", "supports_no_reason": True, "logistics": "已签收"},
        {"order_id": "shipping", "product": "充电器", "status": "shipped", "delivered_at": None, "supports_no_reason": True, "logistics": "运输中"},
        {"order_id": "custom", "product": "定制键帽", "status": "delivered", "delivered_at": "2026-10-10", "supports_no_reason": False, "logistics": "已签收"},
    ]
    path = tmp_path / "orders.json"
    path.write_text(json.dumps(orders), encoding="utf-8")
    return AfterSalesService(orders_path=path, db_path=tmp_path / "tickets.sqlite3", today=date(2026, 10, 11))


def test_order_lookup_and_missing(service):
    assert service.get_order("shipping")["order"]["logistics"] == "运输中"
    assert service.get_order("missing")["status"] == "not_found"


def test_seventh_day_inclusive(service):
    result = service.evaluate("recent", "no_reason_return", "intact")
    assert result["status"] == "eligible"
    assert result["deadline"] == "2026-10-11"
    assert result["shipping_payer"] == "customer"


def test_eighth_day_is_review_not_blanket_rejection(service):
    assert service.evaluate("old", "no_reason_return", "intact")["status"] == "manual_review"


def test_missing_condition_requests_information(service):
    assert service.evaluate("recent", "no_reason_return")["status"] == "needs_information"


@pytest.mark.parametrize("condition", ["damaged", "incomplete"])
def test_non_intact_item_requires_review(service, condition):
    assert service.evaluate("recent", "no_reason_return", condition)["status"] == "manual_review"


def test_quality_request_always_needs_human_assessment(service):
    result = service.evaluate("old", "quality_issue", "damaged")
    assert result["status"] == "manual_review"
    assert result["shipping_payer"] == "pending_review"


def test_undelivered_and_custom_orders(service):
    assert service.evaluate("shipping", "no_reason_return", "intact")["status"] == "needs_information"
    assert service.evaluate("custom", "no_reason_return", "intact")["status"] == "manual_review"


def test_unsupported_values_and_missing_orders(service):
    assert service.evaluate("recent", "refund_everything")["status"] == "invalid_request"
    assert service.evaluate("recent", "no_reason_return", "anything")["status"] == "invalid_request"
    assert service.evaluate("missing", "no_reason_return", "intact")["status"] == "not_found"


def test_ticket_does_not_bypass_missing_information(service):
    assert service.create_ticket("recent", "no_reason_return", "不喜欢")["status"] == "needs_information"
    assert service.create_ticket("recent", "no_reason_return", " ", "intact")["status"] == "invalid_request"


@pytest.mark.parametrize("order_id", ["old", "custom"])
def test_manual_return_still_asks_for_item_condition(service, order_id):
    assert service.create_ticket(order_id, "no_reason_return", "不喜欢")["status"] == "needs_information"


def test_repeated_application_returns_existing_without_reasking(service):
    first = service.create_ticket("recent", "no_reason_return", "不喜欢", "intact")
    again = service.create_ticket("recent", "no_reason_return", "请查询重复申请")
    assert again["status"] == "existing"
    assert again["ticket"] == first["ticket"]


def test_ticket_idempotency_and_persistence(service):
    from aftersales.service import AfterSalesService
    first = service.create_ticket("recent", "no_reason_return", "不喜欢", "intact")
    again = service.create_ticket("recent", "no_reason_return", "重复申请", "intact")
    assert first["ticket"]["ticket_id"] == again["ticket"]["ticket_id"]
    assert first["ticket"]["status"] == "pending_return"
    assert first["ticket"]["refund_executed"] is False
    restarted = AfterSalesService(orders_path=service.orders_path, db_path=service.db_path, today=service.today)
    assert restarted.get_ticket(first["ticket"]["ticket_id"])["ticket"] == first["ticket"]


def test_concurrent_tickets_are_unique(service):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: service.create_ticket("old", "quality_issue", "无法开机"), range(8)))
    assert len({r["ticket"]["ticket_id"] for r in results}) == 1
    assert results[0]["ticket"]["status"] == "pending_review"


@pytest.mark.parametrize("topic", ["return", "quality", "shipping", "refund", "escalation"])
def test_policy_has_version_and_source(service, topic):
    result = service.get_policy(topic)
    assert result["status"] == "ok"
    assert "演示" in result["content"]
    assert result["policy_id"]
    assert result["version"] == "1.0"


def test_policy_rejects_path_traversal(service):
    assert service.get_policy("../../.env")["status"] == "invalid_request"
