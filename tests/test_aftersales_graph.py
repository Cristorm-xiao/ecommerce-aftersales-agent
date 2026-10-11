"""Offline graph regressions with scripted model responses."""
import asyncio
import json
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

import config

with patch.multiple(config, DEEPSEEK_API_KEY="offline-test", TAVILY_API_KEY="offline-test",
                    SILICONFLOW_API_KEY="offline-test"):
    from nodes import llm_tool as tool_module
    from nodes import router as router_module
    from nodes import answer as answer_module
    from nodes import conditions
    from graph import build_graph
    import graph as graph_module


def test_result_is_used_for_next_decision():
    model = AsyncMock()
    model.bind_tools = lambda *a, **kw: model
    model.ainvoke.return_value = AIMessage(content="已查询，可以继续判断")
    state = {"messages": [HumanMessage(content="订单 DEMO1001 能退吗？"),
                          AIMessage(content="", tool_calls=[{"name": "lookup_order", "args": {"order_id": "DEMO1001"}, "id": "o1"}]),
                          ToolMessage(content='{"status":"ok"}', tool_call_id="o1")], "iteration_count": 1}
    with patch.object(tool_module, "answer_LLM", model), patch.object(tool_module, "get_tools", AsyncMock(return_value=[])):
        result = asyncio.run(tool_module.llm_tool_node(state))
    assert model.ainvoke.await_count == 1
    assert result["messages"][0].content


def test_last_allowed_call_is_executed():
    state = {"messages": [AIMessage(content="", tool_calls=[{"name": "lookup_order", "args": {}, "id": "x"}])],
             "iteration_count": config.MAX_ITERATIONS}
    assert conditions.tool_or_answer(state) == "tools"
    assert conditions.after_tools(state) == "answer"


def test_default_tools_are_business_tools():
    names = {t.name for t in asyncio.run(tool_module.get_tools())}
    assert names == {"lookup_order", "lookup_policy", "check_eligibility", "create_after_sales_ticket", "lookup_ticket"}


def test_router_sees_prior_order_context():
    model = AsyncMock()
    model.with_structured_output = lambda *a, **kw: model
    from state import RouterDecision
    model.ainvoke.return_value = RouterDecision(decision="tools", reasoning="用户补充了退货商品状态")
    messages = [HumanMessage(content="DEMO1001 我想退货"), AIMessage(content="请问商品状态？"), HumanMessage(content="完好，配件齐全")]
    with patch.object(router_module, "router_LLM", model):
        asyncio.run(router_module.router_node({"messages": messages}))
    assert "DEMO1001" in str(model.ainvoke.call_args.args[0])


def test_end_to_end_graph_creates_persistent_ticket(tmp_path):
    from aftersales.service import AfterSalesService
    from tools.aftersales import build_aftersales_tools
    service = AfterSalesService(db_path=tmp_path / "tickets.db")
    tools = build_aftersales_tools(service)

    class ScriptedModel:
        def bind_tools(self, *args, **kwargs):
            return self

        async def ainvoke(self, messages):
            results = [m for m in messages if isinstance(m, ToolMessage)]
            steps = [
                ("lookup_order", {"order_id": "DEMO1001"}),
                ("check_eligibility", {"order_id": "DEMO1001", "request_type": "no_reason_return", "item_condition": "intact"}),
                ("create_after_sales_ticket", {"order_id": "DEMO1001", "request_type": "no_reason_return", "reason": "不喜欢", "item_condition": "intact"}),
            ]
            if len(results) < len(steps):
                name, args = steps[len(results)]
                return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"step{len(results)}"}])
            ticket = json.loads(results[-1].content)["ticket"]
            return AIMessage(content=f"演示工单 {ticket['ticket_id']} 待寄回，尚未退款。")

    async def run():
        with patch.object(tool_module, "get_tools", AsyncMock(return_value=tools)), \
             patch.object(graph_module, "get_tools", AsyncMock(return_value=tools)), \
             patch.object(tool_module, "answer_LLM", ScriptedModel()), \
             patch.object(answer_module, "answer_LLM", ScriptedModel()), \
             patch.object(router_module, "router_LLM") as router_model:
            router_model.with_structured_output.return_value.ainvoke = AsyncMock(return_value=__import__("state").RouterDecision(decision="tools", reasoning="需要查询订单和创建工单"))
            graph = await build_graph()
            return await graph.compile().ainvoke({"messages": [HumanMessage(content="DEMO1001 商品完好配件齐全，不喜欢，请帮我申请退货")], "iteration_count": 0})
    result = asyncio.run(run())
    responses = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(responses) == 3
    ticket = json.loads(responses[-1].content)["ticket"]
    assert service.get_ticket(ticket["ticket_id"])["status"] == "ok"
    assert ticket["refund_executed"] is False
    assert "尚未退款" in result["messages"][-1].content


def test_tool_loop_does_not_send_image_bytes():
    model = AsyncMock()
    model.bind_tools = lambda *a, **kw: model
    model.ainvoke.return_value = AIMessage(content="请提供订单号")
    state = {"messages": [HumanMessage(content=[{"type": "text", "text": "键盘损坏"},
                                               {"type": "image_url", "image_url": {"url": "data:image/png;base64,YQ=="}}]),
                          AIMessage(content="图片里有键盘"), HumanMessage(content="DEMO1001 帮我登记")], "iteration_count": 0}
    with patch.object(tool_module, "answer_LLM", model), patch.object(tool_module, "get_tools", AsyncMock(return_value=[])):
        asyncio.run(tool_module.llm_tool_node(state))
    assert "base64" not in str(model.ainvoke.call_args.args[0])


def test_router_keeps_tool_messages_paired_across_long_history():
    model = AsyncMock()
    model.with_structured_output = lambda *a, **kw: model
    model.ainvoke.return_value = __import__("state").RouterDecision(decision="tools", reasoning="继续同一订单售后申请")
    messages = [HumanMessage(content="DEMO1001 帮我查政策")]
    for i in range(5):
        messages.extend([AIMessage(content="", tool_calls=[{"name": "lookup_policy", "args": {"topic": "return"}, "id": str(i)}]),
                         ToolMessage(content="演示政策", tool_call_id=str(i))])
    messages.append(HumanMessage(content="继续"))
    with patch.object(router_module, "router_LLM", model):
        asyncio.run(router_module.router_node({"messages": messages}))
    sent = model.ainvoke.call_args.args[0]
    calls = {c["id"] for m in sent if isinstance(m, AIMessage) for c in m.tool_calls}
    results = {m.tool_call_id for m in sent if isinstance(m, ToolMessage)}
    assert calls == results
