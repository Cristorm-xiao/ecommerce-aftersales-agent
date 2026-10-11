# 星云数码店售后演示指南

这是学习项目，订单、物流、店铺服务承诺和工单均为模拟数据。默认售后业务日期固定为 2026-10-11，不使用用户给出的“今天”覆盖服务器日期。

## 已实现业务

| 业务 | 工具 | 结果 |
|---|---|---|
| 订单与物流查询 | lookup_order | 商品、签收时间、物流与演示日期 |
| 政策查询 | lookup_policy | Pinecone 政策片段、来源文件、片段编号 |
| 售后资格判断 | check_eligibility | eligible / needs_information / manual_review |
| 创建工单 | create_after_sales_ticket | pending_return / pending_review；重复申请返回已有工单 |
| 工单查询 | lookup_ticket | 本地持久化工单，refund_executed=false |

无理由退货截止日期=签收日期+7天，截止当日包含在内。签收与截止日期均按中国大陆本地日期表达。未知商品状态先追问；质量问题、超期、定制商品和损坏/缺配件进入人工审核。未签收订单先查物流；当前取消、换货、维修、错发漏发由人工处理。

用户只问“能退吗”时只查资格；明确申请才创建工单。工具内部重新计算资格，不接收模型传入“已审核通过”的结论。所有工单都不执行真实退款；质量责任及运费不能由图片或模型直接认定。

## 文档和数据

- `sample_docs/aftersales/`：五份店铺政策，分别处理退货、质量问题、运费、退款流程、转人工。
- `sample_data/orders.json`：六条演示订单，无真实客户信息。
- `aftersales/service.py`：独立于模型的日期规则、条件检查与 SQLite 工单存储。
- `tools/aftersales.py`：把业务服务暴露为模型可用的结构化工具。

`lookup_policy(topic, query)` 使用硅基流动 embedding 从 Pinecone 检索，以 `source` 元数据按政策主题过滤，避免其他主题混入。成功返回政策片段、来源文件、片段编号和相似度；空结果或服务失败返回明确状态，不回退读取本地政策。助手依据片段回答并引用来源，有政策编号和版本时也注明。订单资格和工单状态仍由本地业务规则计算；检索文本不能覆盖这些规则，冲突需人工核实。

目标索引由 `AFTERSALES_PINECONE_INDEX` 指定，未设置时使用 `PINECONE_INDEX`。`AFTERSALES_PINECONE_NAMESPACE` 默认空字符串，与已导入政策一致。政策查询需要 Pinecone 和硅基流动凭据；缺少时页面仍可查询演示订单，但会说明政策无法核实。

政策参考：[市场监管总局七日无理由退货暂行办法](https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/fgs/art/2023/art_26ca8fe29e184edd899fa0a7a060d935.html)。文件是虚拟店铺的简化演示规则，正式经营需核对适用法律、平台、品类和品牌政策。

## 配置

| 配置 | 含义 |
|---|---|
| AGENT_MODE | 默认 aftersales；general 保留原通用工具 |
| DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_MODEL | 文本模型独立配置；默认 https://api.deepseek.com、deepseek-flash |
| VISION_API_KEY / VISION_BASE_URL / VISION_MODEL | 视觉模型独立配置；默认百炼北京兼容接口、qwen3-vl-plus |
| MEMORY_BACKEND | memory 或 postgres；有 DATABASE_URL 默认 postgres，否则 memory |
| DATABASE_URL | postgres 模式必填 |
| AFTERSALES_DEMO_DATE | 默认 2026-10-11，服务器端演示日期 |
| AFTERSALES_DB_PATH | 默认项目下 data/aftersales.sqlite3 |
| MAX_ITERATIONS | 默认 5，单轮最多模型工具决策次数，必须大于等于 1 |

memory 只适合单进程演示，重启丢失聊天历史；工单不丢失。跨请求保持同一 thread_id，其他会话使用不同 thread_id；thread_id 不是认证凭据。

文本模型负责回答、路由与工具决策，视觉模型只负责图片理解，两者不共享密钥、接口地址或模型名。Embedding 继续使用独立的 SILICONFLOW 配置。视觉密钥可使用 VISION_API_KEY，也可使用 DASHSCOPE_API_KEY，前者非空时优先；未配置视觉密钥不影响文本启动，图片请求返回明确的 503 配置提示。

视觉模型预设为阿里云百炼 `qwen3-vl-plus`，配置北京地域的 API Key。默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`；也可按控制台替换为业务空间域名 `https://你的业务空间ID.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`。模型能力和接口见[官方视觉理解文档](https://help.aliyun.com/zh/model-studio/vision)及[OpenAI 兼容接口文档](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)。DeepSeek 默认名称依据[官方模型列表](https://api-docs.deepseek.com/quick_start/pricing/)。

## 启动与请求

### 本地聊天网页

```powershell
powershell -ExecutionPolicy Bypass -File .\start_local.ps1
```

打开 http://127.0.0.1:8000/ 即可文字聊天、上传商品图片和新建会话；可用 `-Port 8001` 更换端口。页面与 API 同源，无需额外前端安装或构建，不要直接双击 HTML 文件。

网页首次打开生成全新的 `web-aftersales-v1-UUID`，不会使用历史测试 ID `1`。当前标签页的 ID 和可见消息保存在 sessionStorage，刷新保持当前对话；点击“新建会话”生成新 ID 并清空可见消息，不删除数据库历史和售后工单。图片数据不写入浏览器持久存储。

同一网页会话每次请求携带同一个 ID。若直接调用 API 未传 thread_id，后端为每次请求生成新的 api-UUID；要连续对话，调用者需要显式传入同一个 thread_id。

启动脚本将本地演示设为 MEMORY_BACKEND=memory。服务重启后内存上下文丢失，但页面可能仍保留可见消息，此时点击“新建会话”开始新对话。若需要跨服务重启保持上下文，按原启动方式使用 PostgreSQL。

支持 PNG/JPEG/WebP/GIF，单图最大 3.5 MB，发送前预览、可移除；Enter 发送、Shift+Enter 换行，中文输入法选词不会误发。请求失败时保留输入和附件供重试。

等待回复时刷新会显示未收到结果的提示并恢复文字输入，附件需重新选择。单进程服务按 thread_id 顺序执行文本和图片请求，避免刷新后的重试与上一请求同时修改对话记忆；多进程部署需另行采用跨进程锁或任务队列。

将 `.env.aftersales.example` 合并进现有 `.env`，然后：

```powershell
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Windows 下 PostgreSQL 异步模式要求 SelectorEventLoop，`--loop asyncio` 本身不保证使用 Selector。直接 CLI 的 Windows 切换逻辑保留；API 演示建议使用 memory 模式，生产 PostgreSQL 部署建议使用 Linux。

POST `/chat` 保留原输入输出格式：

```json
{"query":"DEMO1001 商品完好配件齐全，不喜欢，请帮我申请退货", "thread_id":"demo-customer-a"}
```

```json
{"response":"包含演示工单号、当前状态及后续说明的答复"}
```

## 可复现案例

| 订单 | 事实 | 预期 |
|---|---|---|
| DEMO1001 | 10 月 6 日签收 | 完好且配件齐全可申请无理由退货 |
| DEMO1002 | 9 月 25 日签收 | 无理由超期转人工；质量问题仍登记审核 |
| DEMO1003 | 运输中 | 查物流，不直接创建退货工单 |
| DEMO1004 | 个性定制 | 转人工核实适用例外及确认情况 |
| DEMO1005 | 10 月 4 日签收 | 第七天，当日仍可申请 |
| DEMO1006 | 10 月 3 日签收 | 第八天，转人工 |

无凭据业务演示：`python demo_aftersales.py`。它会写入一张 DEMO1001 工单，多次运行返回同一工单。

离线验证（需要 pytest 和项目依赖）：

```powershell
python -m pytest tests/test_aftersales.py tests/test_aftersales_graph.py tests/test_aftersales_api.py tests/test_deepseek_protocol.py -q --basetemp .test-tmp
```

`tests/test_agent.py` 为原项目访问真实服务的集成测试，仅在 `AGENT_MODE=general` 且显式启用 `RUN_LIVE_TESTS=1` 时运行。

本次开发验证环境使用 `D:/python/python.exe`，依赖安装在项目 `.deps` 内，未改动系统 Python。若在当前电脑复用该环境，可在 PowerShell 中运行：

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) '.deps')
$env:MEMORY_BACKEND = 'memory'
& D:/python/python.exe -m uvicorn main:app --reload
```

`.deps` 不纳入版本控制；其他电脑按前面的 requirements 安装步骤建立自己的环境。

## 售后政策向量导入

五份 `sample_docs/aftersales/*.md` 政策已导入 `ecommerce-aftersales` 索引的默认 namespace，共 6 个片段。使用硅基流动 `BAAI/bge-m3`（1024 维），已逐条读取核对内容，并用七天无理由退货问题验证检索。

复用导入命令（需要配置 Pinecone 和硅基流动凭据，并提前创建维度匹配的索引）：

```powershell
python ingest_docs.py --aftersales
```

目标由 `PINECONE_INDEX` 配置决定。相同内容重复导入会覆盖相同 ID；修改或删除政策文件后，旧片段不会自动清理。未加 `--aftersales` 时仍导入原 `sample_docs/*.txt`。

售后助手的 `lookup_policy` 已切换为 Pinecone 检索。原始 Markdown 留在本地供编辑和重新导入；修改本地文件不会自动更新向量。实际写入与检索验证记录保存在本机 `data/policy_import_result.json`。

## 生产扩展边界

目前是工具协作工作流，不是多个独立角色 Agent。真实订单系统接入前需添加客户认证与订单归属校验、服务端确认记录和审批流程。提示词中的“明确申请才创建”是演示约束，不能代替生产授权校验。真实退款、寄回、验收和人工工单系统尚未接入。

SQLite 唯一约束按订单+申请类型去重，演示不支持同一订单多商品、多次售后或工单关闭后重新申请。真实业务需改为订单明细级工单和完整状态机。
