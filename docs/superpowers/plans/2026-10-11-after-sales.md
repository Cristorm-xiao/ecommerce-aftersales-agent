# 电商售后助手 Implementation Plan

> **For agentic workers:** Execute this plan task-by-task in the current session. User explicitly authorized implementation after announcing the changes.

**Goal:** 将通用聊天助手改为星云数码演示店售后助手，支持物流、资格判断与模拟工单。

**Architecture:** 保留 LangGraph 的路由、工具循环、答复节点。业务事实和资格判断由独立 Python 服务处理，政策按明确主题从本地 Markdown 加载；不依赖向量数据库即可演示。SQLite 保存工单，模型不能直接执行退款。

**Tech Stack:** Python、LangGraph、LangChain tools、FastAPI、SQLite、pytest。

## Global Constraints

- 保留用户现有未提交修改、模型配置和图片支持；不提交或发布。
- 所有店铺规则与订单标注为演示数据；日期固定 2026-10-11 以复现边界。
- 未知商品状态先追问；质量问题和超期争议转人工审核，不等同于拒绝所有售后。
- 默认仅暴露售后工具，通用模式仍可显式选择。
- 工单必须经程序重新校验；重复订单和申请类型返回已有工单。

### Task 1: 售后业务服务与资料

**Files:** Create `aftersales/service.py`, `aftersales/__init__.py`, `sample_data/orders.json`, `sample_docs/aftersales/*.md`, `tests/test_aftersales.py`.

**Interfaces:** `AfterSalesService.get_order(order_id)`, `get_policy(topic)`, `evaluate(order_id, request_type, item_condition='unknown')`, `create_ticket(order_id, request_type, reason, item_condition='unknown')` return JSON-serializable dicts. Constructor accepts `orders_path`, `db_path`, `today` for isolated tests.

- [ ] 写测试：签收次日起第七天仍可申请、第八天转人工；未签收不能走退货；状态未知需补问；质量问题转人工；订单不存在；重复与并发工单幂等、重启可查询；政策仅支持已知主题。
- [ ] Run `D:/python/python.exe -m pytest tests/test_aftersales.py -q`，确认缺失业务服务导致失败。
- [ ] 实现五份政策和相匹配的规则，SQLite 使用参数绑定与唯一约束。
- [ ] 运行测试确认边界与持久化通过。

### Task 2: 工具与对话循环

**Files:** Create `tools/aftersales.py`; Modify `tools/__init__.py`, `nodes/llm_tool.py`, `nodes/router.py`, `nodes/conditions.py`, `nodes/answer.py`, `config.py`, `llms.py`; Create `tests/test_aftersales_graph.py`.

**Interfaces:** `get_tools()` returns five售后工具 in aftersales mode; `llm_tool_node` first requires tools, then uses automatic tool choice to decide next step or completion. Existing State and `/chat` contract retained.

- [ ] 写离线测试：工具结果触发下一次模型调用；最后一轮调用仍执行且完整配对；历史问候和订单号追问使用对话上下文；默认工具不连接 MCP/Tavily/Pinecone。
- [ ] 运行对应测试验证旧流程失败。
- [ ] 实现售后提示词、完整工具消息历史、迭代边界和本地工具；不凭模型声明认定退款成功。
- [ ] 运行业务、图流程和现有 DeepSeek 协议回归。

### Task 3: 启动、演示与说明

**Files:** Modify `main.py`, `README.md`, `docs/architecture.md`, `docs/api_reference.md`, `.gitignore`; Create `.env.aftersales.example`, `demo_aftersales.py`, `tests/test_aftersales_api.py`.

- [ ] API 测试覆盖 memory 模式多轮记忆与原请求格式兼容。
- [ ] 实现无 PostgreSQL 时进程内记忆，有配置时仍使用 PostgreSQL；健康信息标注演示模式。
- [ ] 更新文档，给出模型凭据、启动命令、固定演示日期、订单号、政策出处和生产限制。
- [ ] Run `D:/python/python.exe -m pytest tests/test_aftersales.py tests/test_aftersales_graph.py tests/test_aftersales_api.py tests/test_deepseek_protocol.py -q`。
- [ ] Run `D:/python/python.exe demo_aftersales.py`；审查差异和业务规则，修复重要问题。

## 执行结果（2026-10-11）

- [x] Task 1：五份政策、六条订单、程序资格判断、SQLite 幂等工单已实现。
- [x] Task 2：五个业务工具、连续工具决策、中文售后答复、完整工具消息配对和图片过滤已实现。
- [x] Task 3：API 合约保留，进程内/数据库记忆可选，演示脚本、配置示例和运行指南已更新。
- [x] 独立只读代码审查完成；补齐超期/定制缺信息与省略商品状态的重复申请回归，修复两项重要问题。
- [x] 全套离线测试结果：36 passed，10 skipped（原通用模式真实服务集成测试）；语法检查及 git diff --check 通过。
- [x] 无模型演示运行两次，第二次返回同一持久化工单。

验证使用 D:/python/python.exe 和项目 .deps 依赖目录，测试临时文件位于项目内。Windows 沙箱阻塞 asyncio 本地 socketpair，图与 API 离线测试在批准后的沙箱外运行；模型和数据库均用模拟器，不调用真实服务。真实模型、PostgreSQL 和线上部署未验证，也未提交代码。
