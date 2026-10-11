# 📚 API Reference

## 售后 API（当前默认）

`GET /health` 返回 `status`、`agent_mode`、`demo` 和 `memory_backend`；它仅检查应用存活，不代表模型或数据库可用。

`GET /` 提供本地聊天网页，`/assets` 提供静态资源；网页每个新会话生成独立 UUID，不复用旧测试历史。

`POST /chat` 输入 `query: str`、可选 `thread_id: str`、可选 `image_base64: str`；输出 `{"response": "..."}`。未传 thread_id 每次自动生成新的 api-UUID；连续对话必须显式传入同一个 ID。query 和 thread_id 不允许为空白，图片维持原格式校验。

| 工具 | 参数 |
|---|---|
| lookup_order | order_id |
| lookup_policy | topic: return / quality / shipping / refund / escalation；query: 用户问题（可选） |
| check_eligibility | order_id, request_type: no_reason_return / quality_issue, item_condition: unknown / intact / damaged / incomplete |
| create_after_sales_ticket | order_id, request_type, reason, item_condition（默认 unknown） |
| lookup_ticket | ticket_id |

工具返回 JSON 字符串。资格状态为 eligible / needs_information / manual_review / invalid_request / not_found；工单创建状态为 created / existing。工单内部状态为 pending_return / pending_review，refund_executed 始终 false。

政策从 Pinecone 检索，按主题对应的 source 元数据过滤；返回 passages（text、source、chunk_id、score），空结果为 not_found，服务故障为 unavailable，不回退本地文件。原通用工具只在 AGENT_MODE=general 时启用。详见 [售后指南](aftersales.md)。

以下保留原项目历史 API 说明，其中旧四分类路由和 load_document 示例不代表当前已实现接口。

## Main Function

### `build_and_run(query, thread_id)`

```python
async def build_and_run(query: str, thread_id: str = "1") -> str:
    """
    Main entry point for the chatbot.

    Args:
        query (str): User's input query
        thread_id (str): Conversation ID for memory (default: "1")

    Returns:
        str: AI assistant's response

    Example:
        result = await build_and_run("python version check karo", "user_123")
    """
```

## Tools

### `RAG(query)`
Retrieves information from uploaded documents.
```python
@tool
def RAG(query: str) -> str:
    """Use for document-based questions."""
```

### `web_search(query)`
Searches Google for real-time information.
```python
@tool
def web_search(query: str) -> str:
    """Use for current news, prices, latest info."""
```

### `run_python(code)` (via MCP)
Executes Python code remotely.
```python
# Automatically called by LLM for python_tool queries
# Code must use print() to show output
```

## Document Loading

### `load_document(file_path)`
```python
def load_document(file_path: str) -> str:
    """
    Loads and indexes a document into Pinecone.

    Supported formats: .pdf, .csv, .txt, .docx

    Args:
        file_path: Path to document

    Returns:
        Success/error message
    """
```

## Router Categories

| Decision | Triggered By |
|----------|-------------|
| `python_tool` | code, python, install, pip, version, "karo" |
| `web_search` | latest, news, today, current, price |
| `rag` | file uploaded + document question |
| `direct` | general knowledge, greetings |
