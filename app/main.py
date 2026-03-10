import os
import json
import logging
import sys
import asyncio
from typing import AsyncGenerator, List, Dict, Any, Set

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.llm_client import llm_client
from app.logic.storage_manager import StorageManager
from app.models.schema import (
    ChatRequest, RewriteRequest, ForkRequest, 
    RollbackRequest, CreateConversationRequest,
    RenameRequest, UpdateSystemPromptRequest
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

app = FastAPI(title="Version Control LLM Interface (File-per-Conv)")

# 中间件配置
app.add_middleware(
    SessionMiddleware, 
    secret_key="vc-llm-secret-key-v3",
    same_site="lax",
    https_only=False
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def read_index():
    """返回前端主页面"""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return PlainTextResponse("Frontend index.html not found. Please create it in 'static/index.html'.")

DEFAULT_USER = "debug_user"

# 用于跟踪正在运行的任务，支持中止生成
# 格式: { "user_id_conv_id": asyncio.Event }
# 使用 Event 来标记是否需要停止
stop_events: Dict[str, asyncio.Event] = {}

def get_storage() -> StorageManager:
    return StorageManager(DEFAULT_USER)

@app.get("/api/conversations")
async def list_conversations(storage: StorageManager = Depends(get_storage)):
    """获取所有对话列表"""
    return storage.list_conversations()

@app.post("/api/conversations")
async def create_conversation(request: CreateConversationRequest, storage: StorageManager = Depends(get_storage)):
    """创建新对话"""
    conv_id = storage.create_conversation(request.name, request.system_prompt)
    return {"id": conv_id}

@app.get("/api/conversations/{conversation_id}")
async def get_history(conversation_id: str, storage: StorageManager = Depends(get_storage)):
    """获取指定对话的历史消息"""
    messages = storage.get_messages(conversation_id)
    if not messages:
        metadata = storage.get_metadata(conversation_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Conversation not found")
    return {"messages": messages}

@app.get("/api/conversations/{conversation_id}/export")
async def export_conversation(conversation_id: str, storage: StorageManager = Depends(get_storage)):
    """导出对话的原始 Markdown 内容"""
    content = storage.get_raw_markdown(conversation_id)
    if not content:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return PlainTextResponse(content)

@app.post("/api/conversations/rename")
async def rename_conversation(request: RenameRequest, storage: StorageManager = Depends(get_storage)):
    """重命名对话"""
    storage.rename_conversation(request.conversation_id, request.new_name)
    return {"message": "Success"}

@app.post("/api/conversations/system_prompt")
async def update_system_prompt(request: UpdateSystemPromptRequest, storage: StorageManager = Depends(get_storage)):
    """修改对话的 System Prompt"""
    storage.update_system_prompt(request.conversation_id, request.new_prompt)
    return {"message": "Success"}

@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, storage: StorageManager = Depends(get_storage)):
    """删除指定对话"""
    storage.delete_conversation(conversation_id)
    return {"message": "Success"}

@app.post("/api/chat/stop")
async def stop_chat(conversation_id: str):
    """停止正在进行的生成任务"""
    task_key = f"{DEFAULT_USER}_{conversation_id}"
    if task_key in stop_events:
        stop_events[task_key].set()
        return {"message": "Stop signal sent"}
    return {"message": "No active task found"}

@app.post("/api/chat")
async def chat(request: ChatRequest, storage: StorageManager = Depends(get_storage)):
    """向对话追加消息并流式生成回复"""
    messages = storage.get_messages(request.conversation_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    storage.append_message(request.conversation_id, "user", request.message)
    updated_messages = storage.get_messages(request.conversation_id)
    
    task_key = f"{DEFAULT_USER}_{request.conversation_id}"
    stop_events[task_key] = asyncio.Event()

    async def generate_stream():
        full_response = ""
        try:
            llm_stream = await llm_client.chat_completion(updated_messages, stream=True)
            async for chunk in llm_stream:
                # 检查是否收到停止信号
                if stop_events[task_key].is_set():
                    logging.info(f"Generation stopped by user for {task_key}")
                    yield f"data: {json.dumps({'type': 'stopped', 'content': full_response})}\n\n"
                    break
                
                if chunk:
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'delta', 'content': chunk})}\n\n"
            
            if not stop_events[task_key].is_set():
                storage.append_message(request.conversation_id, "assistant", full_response)
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            else:
                # 如果是停止的，也将部分结果存入，或者按需处理
                storage.append_message(request.conversation_id, "assistant", full_response + " [Stopped]")
            
        except Exception as e:
            logging.error(f"Chat error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            if task_key in stop_events:
                del stop_events[task_key]

    return StreamingResponse(generate_stream(), media_type="text/event-stream")

@app.post("/api/fork")
async def fork(request: ForkRequest, storage: StorageManager = Depends(get_storage)):
    """复制对话文件"""
    try:
        new_id = storage.fork_conversation(request.conversation_id, request.new_name)
        return {"id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/rollback")
async def rollback(request: RollbackRequest, storage: StorageManager = Depends(get_storage)):
    """回退到指定消息索引"""
    try:
        storage.rollback_to(request.conversation_id, request.index)
        return {"message": "Success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/rewrite")
async def rewrite(request: RewriteRequest, storage: StorageManager = Depends(get_storage)):
    """重写历史并重新开始生成"""
    storage.rollback_to(request.conversation_id, request.index - 1)
    storage.append_message(request.conversation_id, request.role, request.new_content)
    updated_messages = storage.get_messages(request.conversation_id)
    
    task_key = f"{DEFAULT_USER}_{request.conversation_id}"
    stop_events[task_key] = asyncio.Event()

    async def generate_stream():
        full_response = ""
        try:
            llm_stream = await llm_client.chat_completion(updated_messages, stream=True)
            async for chunk in llm_stream:
                if stop_events[task_key].is_set():
                    yield f"data: {json.dumps({'type': 'stopped', 'content': full_response})}\n\n"
                    break
                if chunk:
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'delta', 'content': chunk})}\n\n"
            
            if not stop_events[task_key].is_set():
                storage.append_message(request.conversation_id, "assistant", full_response)
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            else:
                storage.append_message(request.conversation_id, "assistant", full_response + " [Stopped]")
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            if task_key in stop_events:
                del stop_events[task_key]

    return StreamingResponse(generate_stream(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
