"""Local webpage/API contract; independent from live model calls."""
from unittest.mock import AsyncMock, patch
import asyncio
from fastapi.testclient import TestClient
import config

with patch.multiple(config, DEEPSEEK_API_KEY="offline-test", MEMORY_BACKEND="memory"):
    import main


def test_root_serves_local_chat_and_assets():
    with TestClient(main.app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "text/html" in page.headers["content-type"]
        assert "星云" in page.text
        module = client.get("/assets/app.mjs")
        assert module.status_code == 200
        assert module.headers["content-type"].startswith("text/javascript")
        assert client.get("/assets/styles.css").status_code == 200


def test_default_thread_ids_are_fresh_not_legacy_one():
    first = main.QueryRequest(query="你好")
    second = main.QueryRequest(query="你好")
    assert first.thread_id != "1"
    assert first.thread_id != second.thread_id


def test_explicit_web_thread_id_is_preserved():
    with patch.object(main, "_invoke", AsyncMock(return_value="请提供订单号")) as invoke:
        with TestClient(main.app) as client:
            response = client.post("/chat", json={"query": "我想退货", "thread_id": "web-aftersales-v1-new"})
    assert response.json()["response"] == "请提供订单号"
    invoke.assert_awaited_once_with("我想退货", "web-aftersales-v1-new")


def test_same_thread_text_and_image_requests_are_serialized():
    async def run():
        active = 0
        maximum = 0
        async def answer(*args):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(0.02)
            active -= 1
            return "已处理"
        with patch.object(main, "_invoke", answer), patch.object(main, "_invoke_vision", answer):
            await asyncio.gather(
                main.chat(main.QueryRequest(query="查订单", thread_id="serialization-test")),
                main.chat(main.QueryRequest(query="看图片", thread_id="serialization-test", image_base64="data:image/png;base64,YQ==")),
            )
        assert maximum == 1
    asyncio.run(run())
