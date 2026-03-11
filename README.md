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

## 6. 前端交互补充（复制与代码块）

- **消息复制**：每条对话气泡底部提供复制图标按钮，用于复制该条消息的原始 Markdown 内容。
- **代码块复制**：每个代码块右上角提供复制图标按钮，用于复制该代码块内容。
- **无弹窗反馈**：复制成功/失败不弹窗，按钮会短暂变色并通过悬浮提示反馈状态。
- **导出完整对话**：顶部工具栏 `Export` 可导出当前对话的完整 Markdown 源码文件。

## 6. 内网部署指南

以下步骤可将服务部署到公司内网，便于同事通过浏览器访问：

1. **选择部署主机**
   - 选择一台与同事处于同一局域网（或办公网段）的 Windows 机器。
   - 记录该主机的局域网 IP，例如 `192.168.1.23`。

2. **准备运行环境**
   - 安装 Python 3.10+ 与项目依赖（见上文“环境准备”）。
   - 确保配置文件 `LLM_config.json` 放置在项目根目录的上一级路径，并正确填写 API Key。
   - 配置白名单 `white_list.json`（项目根目录），示例：
     ```json
     ["debug_user","user_a","user_b"]
     ```
     仅白名单用户可登录系统。

3. **启动服务并对外监听**
   - 项目内置运行命令已监听 `0.0.0.0:8002`，可被局域网访问：
     ```bash
     python -m app.main
     ```
   - 同事访问地址：`http://<你的主机IP>:8002`（例如 `http://192.168.1.23:8002`）。

4. **开放 Windows 防火墙端口**
   - 打开“Windows 安全中心 → 防火墙和网络保护 → 高级设置 → 入站规则”，添加一条规则：
     - 允许 TCP 端口 `8002` 入站
     - 程序或端口方式均可，范围选“域/专用”网络
   - 或使用 PowerShell（管理员）：
     ```powershell
     New-NetFirewallRule -DisplayName "VC-LLM 8002" -Direction Inbound -Protocol TCP -LocalPort 8002 -Action Allow
     ```

5. **可选：反向代理（Nginx）**
   - 如需统一域名或端口映射，可在内网网关或一台服务器上部署 Nginx 反向代理：
     ```nginx
     server {
       listen 80;
       server_name vc-llm.internal;  # 内网域名
       location / {
         proxy_pass http://<你的主机IP>:8002;
         proxy_set_header Host $host;
         proxy_set_header X-Real-IP $remote_addr;
         proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       }
     }
     ```
   - 内网 DNS 或 hosts 解析 `vc-llm.internal` 到该 Nginx 主机。

6. **后台运行与守护**
   - 简单场景：使用 PowerShell 启动并保持窗口打开即可。
   - 生产场景建议使用 Windows 服务管理工具（如 NSSM）将 `python -m app.main` 注册为服务，自动随系统启动与重启。

7. **安全建议**
   - 白名单是第一道访问控制，请及时维护 `white_list.json`。
   - 如需进一步限制来源网段，可在防火墙规则中限定源地址范围。
   - 如果需要 HTTPS，可在反向代理处配置证书（内网自签或企业 CA）。

8. **故障排查**
   - 浏览器无法访问：检查服务是否运行、主机 IP 是否可达、防火墙端口是否放行。
   - 登录失败：检查 `white_list.json` 是否包含该用户，后端日志会显示非白名单拒绝（403）。
   - 静态页面问题：确认 [index.html](file:///c:/Users/wsadb/Documents/workspace/VersionControlLLM/static/index.html) 存在并可读取。
