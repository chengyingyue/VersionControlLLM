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

## 4. 阶段三：用户系统与隔离

目前已进入阶段三，系统支持多用户登录与数据物理隔离。

1. **登录系统**：
   - 首次访问 `http://localhost:8002` 将重定向至登录页面（或弹出登录框）。
   - 输入 **工号** 或 **姓名** 即可登录。
   - 系统将根据 `user_id` 在 `data/conversations/{user_id}/` 下创建独立的存储空间。

2. **多用户隔离**：
   - 不同用户的对话记录互不可见。
   - Session 机制确保 API 请求的合法性。

## 5. 存储结构说明

- 对话文件：`data/conversations/{user_id}/{conversation_id}.md`
- 这种结构允许你直接使用 VS Code 等编辑器手动修改 `.md` 内容，后端在下次读取时会自动解析。
