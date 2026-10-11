"""Demo store rules and persistent, idempotent tickets. No real refunds."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
POLICIES = {
    "return": ("DEMO-RETURN-001", "return_policy.md"),
    "quality": ("DEMO-QUALITY-001", "quality_issue_policy.md"),
    "shipping": ("DEMO-SHIPPING-001", "shipping_policy.md"),
    "refund": ("DEMO-REFUND-001", "refund_process.md"),
    "escalation": ("DEMO-ESCALATION-001", "escalation_policy.md"),
}


class AfterSalesService:
    def __init__(self, orders_path=None, db_path=None, today=None):
        self.orders_path = Path(orders_path or ROOT / "sample_data" / "orders.json")
        self.db_path = Path(db_path or ROOT / "data" / "aftersales.sqlite3")
        # Fixed demo clock; production must use a trusted server clock.
        self.today = today or date(2026, 10, 11)
        self.orders = {o["order_id"]: o for o in json.loads(self.orders_path.read_text(encoding="utf-8"))}
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                request_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                UNIQUE(order_id, request_type)
            )""")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def get_order(self, order_id: str) -> dict:
        order = self.orders.get(order_id.strip())
        if order is None:
            return {"status": "not_found", "message": "未找到演示订单，请核对订单号。"}
        return {"status": "ok", "demo": True, "as_of": self.today.isoformat(), "order": dict(order)}

    def get_policy(self, topic: str) -> dict:
        if topic not in POLICIES:
            return {"status": "invalid_request", "message": "政策主题必须为 return/quality/shipping/refund/escalation。"}
        policy_id, filename = POLICIES[topic]
        path = ROOT / "sample_docs" / "aftersales" / filename
        return {"status": "ok", "demo": True, "policy_id": policy_id, "version": "1.0",
                "source": f"sample_docs/aftersales/{filename}", "content": path.read_text(encoding="utf-8")}

    def evaluate(self, order_id: str, request_type: str, item_condition: str = "unknown") -> dict:
        if request_type not in {"no_reason_return", "quality_issue"} or item_condition not in {
            "unknown", "intact", "damaged", "incomplete"
        }:
            return {"status": "invalid_request", "message": "申请类型或商品状态无效。"}
        lookup = self.get_order(order_id)
        if lookup["status"] != "ok":
            return lookup
        order = lookup["order"]
        result = {"demo": True, "order_id": order["order_id"], "request_type": request_type,
                  "as_of": self.today.isoformat(), "policy_version": "1.0",
                  "policy_id": POLICIES["quality" if request_type == "quality_issue" else "return"][0]}
        if order["status"] != "delivered" or not order.get("delivered_at"):
            return result | {"status": "needs_information", "message": "订单尚未签收，请查询物流；未收货问题请联系人工处理。"}
        if request_type == "quality_issue":
            return result | {"status": "manual_review", "shipping_payer": "pending_review",
                             "message": "质量问题需人工核实故障和凭证，可创建待审核工单；不能仅因超过七天而拒绝售后。"}
        delivered = date.fromisoformat(order["delivered_at"])
        result["deadline"] = (delivered + timedelta(days=7)).isoformat()
        if delivered > self.today:
            return result | {"status": "manual_review", "message": "签收日期异常，需要人工核实。"}
        if item_condition == "unknown":
            return result | {"status": "needs_information", "message": "请确认商品功能、外观是否完好，配件是否齐全；合理拆包检查不直接视为损坏。"}
        if not order.get("supports_no_reason"):
            return result | {"status": "manual_review", "message": "该商品不在演示店普通无理由退货范围，需核实商品属性与购买时确认情况。"}
        if self.today > delivered + timedelta(days=7):
            return result | {"status": "manual_review", "message": "已超过演示店七天无理由退货期限，转人工评估其他售后途径。"}
        if item_condition != "intact":
            return result | {"status": "manual_review", "message": "商品损坏或配件缺失，需人工核实原因与完好情况。"}
        return result | {"status": "eligible", "shipping_payer": "customer",
                         "message": "符合演示店无理由退货申请条件，个人原因退货运费由买家承担；寄回后仍需验收。"}

    def create_ticket(self, order_id: str, request_type: str, reason: str,
                      item_condition: str = "unknown") -> dict:
        if not reason.strip() or len(reason) > 1000:
            return {"status": "invalid_request", "message": "请提供 1 至 1000 字的申请原因。"}
        decision = self.evaluate(order_id, request_type, item_condition)
        if decision["status"] in {"invalid_request", "not_found"}:
            return decision
        # A retry returns the original application, even if this turn omits
        # item details. Only a new application needs complete information.
        with self._connect() as db:
            existing = db.execute("SELECT payload FROM tickets WHERE order_id=? AND request_type=?",
                                  (decision["order_id"], request_type)).fetchone()
        if existing:
            return {"status": "existing", "ticket": json.loads(existing[0])}
        if decision["status"] not in {"eligible", "manual_review"}:
            return decision
        ticket = {"ticket_id": f"AS-{uuid4().hex[:12].upper()}", "order_id": decision["order_id"],
                  "request_type": request_type, "reason": reason.strip(), "item_condition": item_condition,
                  "status": "pending_return" if decision["status"] == "eligible" else "pending_review",
                  "decision": decision, "demo": True, "refund_executed": False,
                  "created_at": datetime.now(timezone.utc).isoformat()}
        with self._connect() as db:
            cursor = db.execute("INSERT OR IGNORE INTO tickets VALUES (?, ?, ?, ?)",
                                (ticket["ticket_id"], ticket["order_id"], request_type,
                                 json.dumps(ticket, ensure_ascii=False)))
            created = cursor.rowcount == 1
            row = db.execute("SELECT payload FROM tickets WHERE order_id=? AND request_type=?",
                             (ticket["order_id"], request_type)).fetchone()
        return {"status": "created" if created else "existing", "ticket": json.loads(row[0])}

    def get_ticket(self, ticket_id: str) -> dict:
        with self._connect() as db:
            row = db.execute("SELECT payload FROM tickets WHERE ticket_id=?", (ticket_id.strip(),)).fetchone()
        if row is None:
            return {"status": "not_found", "message": "未找到演示售后工单。"}
        return {"status": "ok", "ticket": json.loads(row[0])}
