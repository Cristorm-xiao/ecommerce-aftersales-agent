# Local Chat Implementation Plan

**Goal:** 在现有 FastAPI 服务内提供本地中文售后聊天网页，使用全新的独立会话。

**Architecture:** 无构建 HTML/CSS/ES modules，同源调用 /chat。sessionStorage 保存当前标签页的 UUID 和可见消息；初次访问生成 web-aftersales-v1-UUID，新建会话轮换 UUID。后端未传 thread_id 的请求也生成独立 ID，避免默认 1 的历史污染。

**Tech Stack:** FastAPI StaticFiles/FileResponse、原生 JavaScript、Python pytest、Node 内置测试。

## Tasks

- [ ] 先写 API 网页与缺省会话 ID 测试，Node 测试首次会话、刷新恢复、新会话、存储不可用和旧格式拒绝；验证失败。
- [ ] 创建 web/index.html、styles.css、session.mjs、app.mjs，暖白与墨绿的客服工作台，左侧服务导航、右侧聊天与输入框；移动端适配。
- [ ] 同源挂载 /assets 与根路由；查询请求 ID 用 UUID factory，显式 thread_id 保持多轮兼容。
- [ ] 图片本地预览、类型与大小校验、上传中/发送中状态、错误恢复、Enter 发送与 Shift+Enter 换行、IME 防误发；消息使用 textContent 防止 HTML 注入。
- [ ] 添加本地启动脚本，更新 README 与售后指南，运行 API、业务、协议及 Node 测试。
- [ ] 本地浏览器验证新会话、连续聊天、刷新、图片预览、手机布局；独立代码审查并修复重要问题。

## Constraints

- 不部署网站，不暴露密钥，不删除旧数据库会话或用户修改。
- 不在浏览器存储图片 base64，附件只在当前页面预览；聊天正文使用 sessionStorage。
- 单标签页的连续消息共享 ID；新会话生成新 ID；发送中禁止切换会话。

## Execution Results

- [x] 本地根路由、聊天页面、图片预览和新会话已实现，既有 API 返回格式保留。
- [x] 默认会话 UUID 与独立网页命名空间避免旧 ID 1 历史；刷新恢复及请求中断状态已有回归测试。
- [x] 独立审查发现刷新后的同线程并发风险，已添加单进程按会话串行执行，并通过延迟请求测试。
- [x] Windows ES modules MIME 问题已复现并修复；浏览器真实按钮与聊天操作正常。
- [x] 48 Python tests passed、10 legacy live tests skipped；5 Node session tests passed。
- [x] 浏览器真实验证：物流查询与连续追问正确、刷新保留、新建会话清空记录、图片预览及 Qwen 图片识别正常，桌面/窄屏布局检查完成。
- [x] 新增启动脚本及运行说明；网页最终保持全新空白会话，未删除任何旧数据库历史。
