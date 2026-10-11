"""Typed business tools. All outputs are structured JSON with demo markers."""
import json
from functools import lru_cache
from typing import Literal

from langchain_core.tools import tool
from aftersales.service import AfterSalesService
from aftersales.policies import PineconePolicyRetriever
import config

RequestType = Literal["no_reason_return", "quality_issue"]
ItemCondition = Literal["unknown", "intact", "damaged", "incomplete"]
PolicyTopic = Literal["return", "quality", "shipping", "refund", "escalation"]


def build_aftersales_tools(service: AfterSalesService, policy_retriever=None) -> list:
    policy_retriever = policy_retriever if policy_retriever is not None else PineconePolicyRetriever()
    def encode(value):
        return json.dumps(value, ensure_ascii=False)

    @tool
    def lookup_order(order_id: str) -> str:
        """查询演示订单、物流、实际签收日期和服务器演示日期。订单号必须由用户提供。"""
        return encode(service.get_order(order_id))

    @tool
    def lookup_policy(topic: PolicyTopic, query: str = "") -> str:
        """从Pinecone检索政策片段和来源。query填写用户问题。
        topic: return退货、quality质量、shipping运费、refund退款、escalation转人工。
        无结果或服务不可用时不能编造政策。
        """
        return encode(policy_retriever.retrieve(topic, query))

    @tool
    def check_eligibility(order_id: str, request_type: RequestType,
                          item_condition: ItemCondition = "unknown") -> str:
        """程序判断资格。无理由退货用no_reason_return，故障用quality_issue。
        用户确认功能外观完好且配件齐全才用intact；缺信息用unknown，不自行猜测。
        """
        return encode(service.evaluate(order_id, request_type, item_condition))

    @tool
    def create_after_sales_ticket(order_id: str, request_type: RequestType, reason: str,
                                 item_condition: ItemCondition = "unknown") -> str:
        """仅在用户明确申请后创建模拟工单；内部再次核验资格，重复申请返回已有工单。
        需要用户提供真实申请原因；不会退款，pending_review代表待人工审核。
        """
        return encode(service.create_ticket(order_id, request_type, reason, item_condition))

    @tool
    def lookup_ticket(ticket_id: str) -> str:
        """根据工单号查询模拟售后状态；不代表真实退款已执行。"""
        return encode(service.get_ticket(ticket_id))

    return [lookup_order, lookup_policy, check_eligibility, create_after_sales_ticket, lookup_ticket]


@lru_cache(maxsize=1)
def get_aftersales_tools() -> list:
    return build_aftersales_tools(AfterSalesService(db_path=config.AFTERSALES_DB_PATH,
                                                  today=config.AFTERSALES_DEMO_DATE))
