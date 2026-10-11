"""API contract and process-local conversation memory without network."""
import asyncio
from unittest.mock import patch

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from state import State
import config

with patch.multiple(config, DEEPSEEK_API_KEY="offline-test", TAVILY_API_KEY="offline-test",
                    SILICONFLOW_API_KEY="offline-test", DATABASE_URL="offline-test"):
    import main


def test_health_identifies_demo_mode():
    with TestClient(main.app) as client:
        result = client.get("/health")
    assert result.json()["agent_mode"] == "aftersales"
    assert result.json()["demo"] is True


def test_api_keeps_existing_contract_and_validation():
    from unittest.mock import AsyncMock
    with patch.object(main, "_invoke", AsyncMock(return_value="订单运输中")) as invoke:
        with TestClient(main.app) as client:
            assert client.post("/chat", json={"query": "查询 DEMO1003", "thread_id": "shop-test"}).json() == {"response": "订单运输中"}
            assert client.post("/chat", json={"query": " "}).status_code == 422
            assert client.post("/chat", json={"query": "你好", "thread_id": " "}).status_code == 422
            assert client.post("/chat", json={"query": "看图片", "image_base64": "invalid"}).status_code == 422
    invoke.assert_awaited_once_with("查询 DEMO1003", "shop-test")


def test_memory_backend_keeps_threads_separate():
    async def run():
        async def build():
            async def answer(state):
                queries = [m.content for m in state["messages"] if isinstance(m, HumanMessage)]
                return {"messages": [AIMessage(content=" / ".join(queries))]}
            graph = StateGraph(State)
            graph.add_node("answer", answer)
            graph.add_edge(START, "answer")
            graph.add_edge("answer", END)
            return graph
        with patch.object(config, "MEMORY_BACKEND", "memory"), patch.object(main, "build_graph", build):
            await main._invoke("DEMO1001", "isolated-a")
            second = await main._invoke("商品完好", "isolated-a")
            other = await main._invoke("你好", "isolated-b")
        assert second == "DEMO1001 / 商品完好"
        assert other == "你好"
    asyncio.run(run())


def test_aftersales_needs_only_model_credentials():
    with patch.multiple(config, DEEPSEEK_API_KEY="offline-test", DATABASE_URL=None,
                        PINECONE_API_KEY=None, TAVILY_API_KEY=None, SILICONFLOW_API_KEY=None,
                        MEMORY_BACKEND="memory"):
        config.validate()


def test_image_summary_cannot_approve_refund():
    from unittest.mock import AsyncMock
    async def run():
        model = AsyncMock()
        model.ainvoke.return_value = AIMessage(content="图片显示键盘")
        with patch.object(config, "MEMORY_BACKEND", "memory"), patch.object(main, "vision_LLM", model):
            result = await main._invoke_vision("是否有损坏", "data:image/png;base64,YQ==", "image-test")
        assert result == "图片显示键盘"
        assert "不能" in model.ainvoke.call_args.args[0][0].content
    asyncio.run(run())


def test_missing_vision_configuration_is_clear_and_does_not_touch_memory():
    from unittest.mock import Mock
    with patch.object(main, "vision_LLM", None), patch.object(main, "_checkpointer", Mock()) as memory:
        with TestClient(main.app) as client:
            result = client.post("/chat", json={"query": "看看图片", "image_base64": "data:image/png;base64,YQ=="})
    assert result.status_code == 503
    assert "VISION_API_KEY" in result.json()["detail"]
    memory.assert_not_called()
