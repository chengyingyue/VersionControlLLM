# 对话版本控制系统 (VC-LLM) 设计文档

## 1. 核心定位
本工具旨在提供类似网页端大模型的交互体验，但赋予用户 **API 级别的对话操控权**。通过“一文件一对话”的 Markdown 结构，实现对话的重写（Rewrite）、分叉（Fork）和回滚（Rollback），让对话像代码一样可管理、可复用。

## 2. 核心需求
- **对话历史操控**：
  - **Rewrite**：修改历史中任意位置的 User 或 Assistant 消息，截断后续并重新生成。
  - **Fork**：将当前对话完整复制为新文件，支持多支线并行探索。在 GUI 上表现为两个并行的对话分支。
  - **Rollback**：将对话状态回退到指定历史点（截断文件）。
- **用户隔离与登录**：
  - **登录机制**：支持多用户登录（通过姓名/工号）。
  - **目录隔离**：数据按 `data/conversations/{user_id}/` 目录物理隔离。
- **Markdown 与 Mermaid 渲染**：
  - 前端流式渲染 Markdown 内容。
  - 支持 Mermaid 代码块实时转化为图表。
- **辅助功能**：
  - **停止生成**：生成过程中支持前端发送中止信号。
  - **导出/复制**：提供获取完整 Markdown 源码的端点。
  - **System Prompt 修改**：允许随时调整该对话的设定（Message 0）并影响后续生成。

## 3. 存储设计 (一文件一对话)
每个对话存储为一个独立的 `.md` 文件，包含 Frontmatter 元数据和分段消息体。

### 3.1 文件结构示例
```markdown
---
id: conv_a1b2c3d4
name: 逻辑分析分叉
created_at: 2026-03-10T10:00:00Z
updated_at: 2026-03-10T11:30:00Z
user_id: user_01
---
# Message 0 (System)
你是一个专业的 Python 专家，请用简洁的代码回答问题。

# Message 1 (User)
如何实现一个单例模式？

# Message 2 (Assistant)
可以使用装饰器或元类实现...
```

### 3.2 存储目录
- `data/conversations/{user_id}/{conv_id}.md`
- 这种结构天然支持文件系统级别的备份、同步和人工查阅。

## 4. 前端 UI/UX 设计
前端采用单页应用（SPA）架构，重点在于流式内容渲染与对话树的线性化展示。

### 4.1 布局规划
- **侧边栏 (Sidebar)**：
  - 对话列表：按更新时间排序，显示名称与摘要。
  - 操作按钮：新建对话、删除对话。
- **主对话区 (Chat Area)**：
  - 消息流：按索引渲染 `# Message X` 块。
  - **流式渲染**：使用 Markdown-it 实时解析 SSE 传回的片段。
  - **Mermaid 渲染**：检测到代码块类型为 `mermaid` 时，调用 Mermaid.js 进行 SVG 转换。
- **控制栏 (Header/Toolbar)**：
  - 当前对话名称（点击可重命名）。
  - **System Prompt 配置**：下拉/弹窗修改该对话的 Message 0。
  - **版本操作**：Fork（复制当前对话）、Export（复制 Markdown 源码）、Rollback（选择消息索引回退）。
  - **生成控制**：正在生成时显示“停止”按钮。

### 4.2 核心交互
1. **停止生成**：点击停止 -> 发送 `POST /api/chat/stop` -> 后端截断推理 -> 前端显示“已中止”。
2. **重写 (Rewrite)**：悬停在历史消息上显示“编辑” -> 修改内容 -> 发送 `POST /api/rewrite` -> 界面截断该消息后的内容并开始流式刷新。

## 5. 系统架构
- **前端**：原生 ES Modules + Vue 3（无构建），集成 Markdown-it、Mermaid.js、Highlight.js。
- **后端**：FastAPI + SSE (Server-Sent Events) 流式推送。
- **LLM 层**：复用 `llm_client.py`，支持 Mock 打桩和日志记录。

## 6. API 交互逻辑
### 6.1 身份校验
- 使用 `SessionMiddleware` 存储 `user_id`。
- 接口通过 `Depends(get_current_user)` 进行权限拦截，确保用户只能访问自己的目录。

### 6.2 核心端点
- `GET /api/conversations`：列表展示（带元数据）。
- `POST /api/chat`：追加消息并流式生成。
- `POST /api/rewrite`：截断到 index-1 -> 替换 index 内容 -> 重新生成。
- `POST /api/fork`：复制 .md 文件 -> 赋予新 ID。
- `POST /api/chat/stop`：中止当前对话的生成任务。
- `POST /api/conversations/rename`：修改 Frontmatter 中的名称。
- `POST /api/conversations/system_prompt`：针对当前对话修改 Message 0 的内容。

## 7. 演进路线
- **阶段一**：完成一文件一对话存储、SSE 生成通路、Fork/Rewrite 核心逻辑。
- **阶段二**：前端 UI 开发（Vue 3 + Tailwind），集成 Markdown/Mermaid 渲染。
- **阶段三**：引入用户登录界面与多用户隔离，完善 Session 管理。
