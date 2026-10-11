"""Offline regressions for routing and tool-result message compatibility.

Run: python -m unittest discover -s tests -p test_deepseek_protocol.py -v
"""
import json
import runpy
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from openai import AsyncOpenAI
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

import config

# Import tool wrappers with dummy credentials, even when .env is absent.
with patch.multiple(config, DEEPSEEK_API_KEY="offline-test", TAVILY_API_KEY="offline-test"):
    from nodes import router as router_module
    from nodes import answer as answer_module
    from nodes import llm_tool as tool_module


def completion(message):
    return httpx.Response(200, json={
        "id": "offline-completion", "object": "chat.completion",
        "created": 0, "model": "deepseek-flash",
        "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
    })


class DeepSeekProtocolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Exercise the actual model configuration without depending on .env.
        with patch.multiple(config, DEEPSEEK_API_KEY="offline-test",
                            DEEPSEEK_BASE_URL="https://api.deepseek.com",
                            DEEPSEEK_MODEL="deepseek-flash"):
            self.models = runpy.run_path(str(Path(__file__).resolve().parents[1] / "llms.py"))

    async def test_tool_route_requires_call_despite_previous_denial(self):
        @tool
        def tavily_search(query: str) -> str:
            """Search the web for current information."""
            return "offline weather result"

        def respond(request):
            body = json.loads(request.content)
            if body.get("tool_choice") != "required":
                return completion({"role": "assistant", "content": "I have no web search tool."})
            return completion({"role": "assistant", "content": "", "tool_calls": [{
                "id": "search-1", "type": "function", "function": {
                    "name": "tavily_search", "arguments": '{"query":"Hefei weather today"}'}}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            client = AsyncOpenAI(api_key="offline-test", http_client=http)
            model = self.models["answer_LLM"].model_copy(update={
                "async_client": client.chat.completions, "root_async_client": client})
            with patch.object(tool_module, "answer_LLM", model), patch.object(
                tool_module, "get_tools", AsyncMock(return_value=[tavily_search])
            ):
                result = await tool_module.llm_tool_node({"messages": [
                    HumanMessage(content="Find today's weather in Hefei"),
                    AIMessage(content="I have no web search tool."),
                    HumanMessage(content="Please look it up online."),
                ], "iteration_count": 0})
        self.assertEqual([call["name"] for call in result["messages"][0].tool_calls],
                         ["tavily_search"])

    async def test_weather_routes_to_tools_with_supported_request(self):
        requests = []

        def respond(request):
            body = json.loads(request.content)
            requests.append(body)
            if body.get("response_format", {}).get("type") == "json_schema":
                return httpx.Response(400, json={"error": {
                    "message": "This response_format type is unavailable now"}})
            if body.get("thinking", {}).get("type") != "disabled":
                return httpx.Response(400, json={"error": {
                    "message": "Thinking mode does not support this tool_choice"}})
            return completion({"role": "assistant", "content": "", "tool_calls": [{
                "id": "route-1", "type": "function", "function": {
                    "name": "RouterDecision", "arguments": json.dumps({
                        "decision": "tools", "reasoning": "Current weather requires search"})}}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            client = AsyncOpenAI(api_key="offline-test", http_client=http)
            model = self.models["router_LLM"].model_copy(update={
                "async_client": client.chat.completions, "root_async_client": client})
            with patch.object(router_module, "router_LLM", model):
                result = await router_module.router_node({
                    "messages": [HumanMessage(content="Find today's weather in Hefei")]})
        self.assertEqual(result["router_decision"], "tools", result["reasoning"])
        self.assertTrue(requests[0].get("tools"))

    async def test_answer_preserves_results_for_every_tool_call(self):
        requests = []

        def respond(request):
            body = json.loads(request.content)
            requests.append(body)
            pending = set()
            for message in body["messages"]:
                if pending and message["role"] != "tool":
                    return httpx.Response(400, json={"error": {
                        "message": "Assistant tool_calls require corresponding tool messages"}})
                pending.update(call["id"] for call in message.get("tool_calls", []))
                if message["role"] == "tool":
                    pending.discard(message["tool_call_id"])
            if pending:
                return httpx.Response(400, json={"error": {"message": "Missing tool results"}})
            return completion({"role": "assistant", "content": "Hefei weather: sunny."})

        state = {"messages": [
            HumanMessage(content="Find today's weather in Hefei"),
            AIMessage(content="", tool_calls=[{
                "name": "tavily_search", "args": {"query": "Hefei weather"},
                "id": "search-1", "type": "tool_call"}]),
            ToolMessage(content="Hefei: sunny", tool_call_id="search-1"),
        ]}
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            client = AsyncOpenAI(api_key="offline-test", http_client=http)
            model = self.models["answer_LLM"].model_copy(update={
                "async_client": client.chat.completions, "root_async_client": client})
            with patch.object(answer_module, "answer_LLM", model):
                result = await answer_module.answer_node(state)
        self.assertIn("sunny", result["messages"][0].content)
        self.assertEqual([m["role"] for m in requests[0]["messages"]],
                         ["system", "user", "assistant", "tool"])
