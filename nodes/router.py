"""Router node — decides whether the query needs a tool or a direct answer."""
import logging
from langchain_core.messages import SystemMessage, trim_messages
from state import State, RouterDecision
from llms import router_LLM
from nodes.answer import _strip_images
import config

logger = logging.getLogger(__name__)

_PROMPT = """Decide if this query needs a tool, or can be answered directly.

- tools  : needs code execution, document/file lookup, or real-time web info
           (e.g. "run this code", "check my uploaded file", "latest news", "current price")
- answer : greetings, general knowledge, simple questions — no tool needed

When in doubt → tools."""


async def router_node(state: State):
    try:
        history = _strip_images(trim_messages(state["messages"], max_tokens=40, token_counter=len,
                                              strategy="last", start_on="human"))
        r = await router_LLM.with_structured_output(
            RouterDecision, method="function_calling"
        ).ainvoke([
            SystemMessage(content=(
                "你在星云数码演示店识别售后请求。订单、物流、政策、退款、退货、质量故障和工单查询路由 tools。"
                "结合上下文识别用户补充的订单号、商品状态和申请确认；需要查询业务事实的追问也走 tools。"
                "问候或缺少订单号等信息需要追问时可走 answer。无法判断时选择 tools。"
            ) if config.AGENT_MODE == "aftersales" else _PROMPT),
        ] + history)
        return {"router_decision": r.decision, "reasoning": r.reasoning}
    except Exception as e:
        logger.warning("Router failed; using fallback (%s)", type(e).__name__)
        # Business facts must never become an ungrounded direct answer on router failure.
        return {"router_decision": "tools" if config.AGENT_MODE == "aftersales" else "answer",
                "reasoning": "Router unavailable; conservative fallback"}


def route_condition(state: State) -> str:
    return state["router_decision"]
