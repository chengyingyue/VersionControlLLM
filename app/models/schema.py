from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    conversation_id: str
    message: str

class CreateConversationRequest(BaseModel):
    name: str
    system_prompt: Optional[str] = "You are a helpful AI assistant."

class RewriteRequest(BaseModel):
    conversation_id: str
    index: int  # 要回退到的消息索引
    new_content: str
    role: str = "user"

class ForkRequest(BaseModel):
    conversation_id: str
    new_name: str

class RenameRequest(BaseModel):
    conversation_id: str
    new_name: str

class UpdateSystemPromptRequest(BaseModel):
    conversation_id: str
    new_prompt: str

class RollbackRequest(BaseModel):
    conversation_id: str
    index: int

class ConversationNodeResponse(BaseModel):
    id: str
    parent_id: Optional[str]
    messages: List[Message]
    response: str
    timestamp: str
