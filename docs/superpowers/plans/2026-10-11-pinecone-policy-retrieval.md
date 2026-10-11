# Pinecone Policy Retrieval Implementation Plan

**Goal:** 售后助手通过 Pinecone 检索政策片段并引用来源。

**Architecture:** 新建独立政策检索类，以主题对应的 source metadata 过滤向量检索。lookup_policy 支持用户问题，返回片段、来源和明确的失败状态，禁止回退本地文档。订单资格和工单规则仍由业务服务执行。

**Tech Stack:** LangChain PineconeVectorStore、硅基流动 BGE-M3、FastAPI、pytest。

## Tasks

- [x] 在 tests/test_policy_retrieval.py 先验证主题过滤、来源、空结果、异常脱敏及 lookup_policy 不调用本地 get_policy。
- [x] 运行失败测试；实现 aftersales/policies.py 的 PineconePolicyRetriever.retrieve(topic, query='') 和工具注入。
- [x] 更新回答提示词：政策回答先检索、引用来源、检索资料不得覆盖业务资格判断。
- [x] 更新配置示例与使用文档，运行离线回归与代码审查。
- [x] 真实查询已导入的索引；重启本任务启动的本地服务，通过新 thread_id 测试 /chat 回答及来源。

## Constraints

- 不删除或重写 Pinecone 数据，不显示凭据；使用默认 namespace。
- 本地业务演示仍可单独运行；网页政策查询需要 Pinecone 和 embedding 凭据。
- 只提交当前工作成果，不替用户提交 Git commit。

## Verification

离线回归：55 passed，10 个旧真实服务测试按配置 skipped。真实检索返回 return_policy.md；/chat 新会话回答合理拆封与七天期限，引用 return_policy.md、DEMO-RETURN-001 v1.0，记录于 data/policy_chat_result.json。重启后服务 PID 35908，地址 http://127.0.0.1:8000/。代码审查未发现重要问题。
