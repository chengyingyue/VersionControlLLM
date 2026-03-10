# 对话版本控制系统 (VC-LLM)

基于 Markdown 存储的 Git 式大模型交互工具。支持对对话进行重写（Rewrite）、分叉（Fork）和回滚（Rollback）。

## 1. 环境准备

建议使用 Python 3.10+。

```bash
# 进入项目目录
cd versionControlLLM

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境 (Windows)
.\.venv\Scripts\activate

# 安装依赖
pip install fastapi uvicorn httpx requests python-multipart
```

## 2. 核心配置

项目复用了原项目的 LLM 客户端逻辑，配置文件的位置与原项目保持一致：

- **配置文件路径**：项目根目录向上一级（即 `c:\Users\wsadb\Documents\workspace\LLM_config.json`）。
- **配置内容示例**：
  ```json
  {
    "deepseek_api_key": "你的 API KEY",
    "deepseek_base_url": "https://api.deepseek.com",
    "model_name": "deepseek-chat",
    "debug_mode": false,
    "mock_chunk_count": 10
  }
  ```

## 3. 启动后端服务

```bash
# 在 versionControlLLM 目录下运行
python -m app.main
```
服务默认启动在 `http://localhost:8002`。

## 4. 阶段一功能验证 (API 测试建议)

由于目前处于阶段一（后端核心已完成，前端开发中），你可以使用 API 测试工具（如 Postman 或 cURL）进行功能验证：

### 4.1 创建对话
- **URL**: `POST /api/conversations`
- **Body**: `{"name": "测试对话", "system_prompt": "你是一个助手"}`
- **验证**: 检查 `data/conversations/debug_user/` 下是否生成了对应的 `.md` 文件。

### 4.2 发起流式聊天
- **URL**: `POST /api/chat`
- **Body**: `{"conversation_id": "{ID}", "message": "你好"}`
- **验证**: 观察 SSE (Server-Sent Events) 输出，并检查 `.md` 文件是否追加了消息。

### 4.3 分叉对话 (Fork)
- **URL**: `POST /api/fork`
- **Body**: `{"conversation_id": "{ID}", "new_name": "我的分叉支线"}`
- **验证**: 检查是否生成了新的文件，内容与原文件一致但元数据已更新。

### 4.4 历史重写 (Rewrite)
- **URL**: `POST /api/rewrite`
- **Body**: `{"conversation_id": "{ID}", "index": 1, "new_content": "请重新回答..."}`
- **验证**: 文件应在索引 1 处被截断，并基于新内容重新生成。

## 5. 存储结构说明

- 对话文件：`data/conversations/{user_id}/{conversation_id}.md`
- 这种结构允许你直接使用 VS Code 等编辑器手动修改 `.md` 内容，后端在下次读取时会自动解析。
