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

## 4. 阶段二：前端界面访问

目前已进入阶段二，你可以通过浏览器直接访问前端界面：

1. **启动后端服务**：
   ```bash
   python -m app.main
   ```
2. **访问地址**：`http://localhost:8002` (默认端口)

### 前端功能概览
- **侧边栏**：查看和搜索对话列表，支持新建/删除对话。
- **对话区**：流式 Markdown 渲染，支持 Mermaid 图表。
- **版本控制**：
  - **Fork**：复制当前对话为新分支。
  - **Rewrite**：修改历史消息并截断重生成。
  - **Rollback**：回滚到指定的历史版本。
  - **System Prompt**：实时修改对话的系统设定。

## 5. 存储结构说明

- 对话文件：`data/conversations/{user_id}/{conversation_id}.md`
- 这种结构允许你直接使用 VS Code 等编辑器手动修改 `.md` 内容，后端在下次读取时会自动解析。
