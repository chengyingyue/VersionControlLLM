# VC-LLM 开发规划

- **阶段一：核心存储与生成通路 (当前)**
  - [x] 重构 `storage_manager.py`：实现一文件一对话、Frontmatter 解析、消息分段读写。
  - [x] 完善 `main.py`：实现 `/api/chat` (SSE)、`/api/fork` (文件级)、`/api/rewrite` (截断生成)。
  - [x] 增加辅助端点：对话改名、导出、修改 System Prompt。
  - [x] 实现中止逻辑：支持 `/api/chat/stop` 中止 LLM 推理任务。

- **阶段一验证方法 (Manual API Test)**
  - [ ] **创建对话**：调用 `POST /api/conversations`，验证 `data/conversations/debug_user/` 下是否生成了带 Frontmatter 的 .md 文件。
  - [ ] **流式对话**：调用 `POST /api/chat`，观察是否返回 SSE 数据流（delta），且结束后 .md 文件追加了 `# Message 1` 和 `# Message 2`。
  - [ ] **对话 Fork**：调用 `POST /api/fork`，验证是否生成了内容一致但 ID/Name 不同的新 .md 文件。
  - [ ] **历史重写**：调用 `POST /api/rewrite` (指向 index 1)，验证文件是否被截断并重新生成了后续消息。
  - [ ] **中止生成**：在 `chat` 过程中调用 `/api/chat/stop`，验证流是否停止且文件保存了 `[Stopped]` 标记。
  - [ ] **改名与导出**：验证 `/api/conversations/rename` 后文件元数据是否更新，`/api/conversations/{id}/export` 是否返回完整源码。

- **阶段二：前端展示与渲染 (Next)**
  - [ ] 搭建前端基础骨架：使用 Vue 3 + Tailwind CSS（CDN 引入，无需构建）。
  - [ ] 对话列表组件：实现侧边栏，支持加载、搜索、切换对话。
  - [ ] 消息流渲染：集成 `markdown-it` 实现流式文本解析，集成 `mermaid.js`。
  - [ ] 实时生成交互：处理 SSE 事件（delta, complete, stopped, error）。
  - [ ] 版本操作 UI：实现 Fork、Rename、Export、Modify System Prompt 的交互弹窗。
  - [ ] 历史操控：在消息块上实现“从此处重写”按钮逻辑。

- **阶段三：用户系统与隔离**
  - [ ] 实现登录端点：支持工号/姓名登录，并在 Session 中记录 `user_id`。
  - [ ] 目录隔离：确保 `storage_manager` 根据当前 Session 的 `user_id` 访问对应目录。
  - [ ] 权限校验：为所有敏感端点增加 `get_current_user` 依赖项。

- **调试与优化**
  - [ ] 复用 `llm_client` 的 Mock 机制进行稳定测试。
  - [ ] 优化正则解析：增强对特殊 Markdown 字符的兼容性。
  - [ ] 添加单元测试：覆盖文件截断、Fork 逻辑。
