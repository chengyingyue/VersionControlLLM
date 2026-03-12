import os
import re
import uuid
import shutil
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

# --- Constants ---
BASE_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
CONVERSATIONS_DIR = os.path.join(BASE_DATA_DIR, "conversations")

class StorageManager:
    """
    负责“一文件一对话”的 Markdown 存储管理。
    支持 Frontmatter 元数据与 # Message X 消息分段。
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.user_path = os.path.join(CONVERSATIONS_DIR, user_id)
        os.makedirs(self.user_path, exist_ok=True)

    def _get_file_path(self, conversation_id: str) -> str:
        return os.path.join(self.user_path, f"{conversation_id}.md")

    def list_conversations(self) -> List[Dict[str, Any]]:
        """列出用户所有对话及其元数据"""
        convs = []
        for filename in os.listdir(self.user_path):
            if filename.endswith(".md"):
                conv_id = filename[:-3]
                meta = self.get_metadata(conv_id)
                if meta:
                    convs.append(meta)
        return sorted(convs, key=lambda x: x.get("updated_at", ""), reverse=True)

    def get_metadata(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """从文件 Frontmatter 解析元数据"""
        path = self._get_file_path(conversation_id)
        if not os.path.exists(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            if not content.startswith("---"):
                return None
            
            parts = content.split("---", 2)
            if len(parts) < 3:
                return None
            
            yaml_content = parts[1].strip()
            metadata = {}
            for line in yaml_content.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip()] = value.strip()
            
            return metadata
        except Exception as e:
            logging.error(f"Error parsing metadata for {conversation_id}: {e}")
            return None

    def get_messages(self, conversation_id: str) -> List[Dict[str, str]]:
        """从文件解析消息列表"""
        path = self._get_file_path(conversation_id)
        if not os.path.exists(path):
            return []

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # 跳过 Frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            body = parts[2] if len(parts) > 2 else ""
        else:
            body = content

        # 匹配 # Message X (Role)
        # 支持格式: # Message 0 (System) 或 # Message 1 (User)
        pattern = r"# Message \d+ \((.*?)\)\n(.*?)(?=\n# Message \d+ \(|\Z)"
        matches = re.finditer(pattern, body, re.DOTALL)
        
        messages = []
        for match in matches:
            role = match.group(1).lower()
            text = match.group(2).strip()
            messages.append({"role": role, "content": text})
            
        return messages

    def create_conversation(self, name: str, system_prompt: str = "You are a helpful AI assistant.") -> str:
        """创建新对话文件"""
        conv_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        
        content = f"""---
id: {conv_id}
name: {name}
created_at: {now}
updated_at: {now}
---
# Message 0 (System)
{system_prompt}
"""
        path = self._get_file_path(conv_id)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return conv_id

    def append_message(self, conversation_id: str, role: str, text: str):
        """向对话追加一条消息"""
        path = self._get_file_path(conversation_id)
        messages = self.get_messages(conversation_id)
        next_index = len(messages)
        
        # 转换 role 首字母大写用于标题
        display_role = role.capitalize()
        
        new_block = f"\n# Message {next_index} ({display_role})\n{text}\n"
        
        with open(path, "a", encoding="utf-8") as f:
            f.write(new_block)
            
        # 更新时间戳
        self._update_timestamp(conversation_id)

    def fork_conversation(self, conversation_id: str, new_name: str) -> str:
        """Fork 对话：复制文件并更新元数据"""
        old_path = self._get_file_path(conversation_id)
        if not os.path.exists(old_path):
            raise ValueError("Source conversation not found")

        new_id = str(uuid.uuid4())[:8]
        new_path = self._get_file_path(new_id)
        
        with open(old_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # 替换 Frontmatter 中的 ID 和 Name
        now = datetime.now().isoformat()
        parts = content.split("---", 2)
        if len(parts) >= 3:
            # 重新构建元数据部分
            new_meta = f"""---
id: {new_id}
name: {new_name}
created_at: {now}
updated_at: {now}
---"""
            new_content = new_meta + parts[2]
        else:
            # 如果没有 Frontmatter (异常情况)，则创建
            new_content = f"""---
id: {new_id}
name: {new_name}
created_at: {now}
updated_at: {now}
---
{content}"""

        with open(new_path, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        return new_id

    def rollback_to(self, conversation_id: str, index: int):
        """回退/重写：将对话截断到指定索引（包含该索引）"""
        path = self._get_file_path(conversation_id)
        if not os.path.exists(path):
            return

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        parts = content.split("---", 2)
        meta_section = parts[1] if len(parts) > 1 else ""
        body_section = parts[2] if len(parts) > 2 else ""

        # 分割消息块
        # 使用正向前瞻匹配消息头，保留分隔符
        blocks = re.split(r"(?=# Message \d+ \(.*?\))", body_section)
        # 过滤空块
        blocks = [b for b in blocks if b.strip()]
        
        # 截断
        if index < len(blocks):
            truncated_blocks = blocks[:index + 1]
            new_body = "".join(truncated_blocks)
            
            new_content = f"---{meta_section}---{new_body}"
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
                
            self._update_timestamp(conversation_id)

    def _update_timestamp(self, conversation_id: str):
        """更新 updated_at 字段"""
        path = self._get_file_path(conversation_id)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            
        now = datetime.now().isoformat()
        # 简单的正则替换
        new_content = re.sub(r"updated_at: .*", f"updated_at: {now}", content)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

    def rename_conversation(self, conversation_id: str, new_name: str):
        """重命名对话"""
        path = self._get_file_path(conversation_id)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        new_content = re.sub(r"name: .*", f"name: {new_name}", content)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        self._update_timestamp(conversation_id)

    def update_system_prompt(self, conversation_id: str, new_prompt: str):
        """修改 System Prompt (Message 0)"""
        path = self._get_file_path(conversation_id)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 匹配 # Message 0 (System) 及其后的内容直到下一个消息或结束
        pattern = r"(# Message 0 \(System\)\n).*?(?=\n# Message \d+ \(|\Z)"
        new_content = re.sub(pattern, rf"\1{new_prompt}\n", content, flags=re.DOTALL)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        self._update_timestamp(conversation_id)

    def get_raw_markdown(self, conversation_id: str) -> str:
        """获取完整的 Markdown 内容用于复制/导出"""
        path = self._get_file_path(conversation_id)
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def save_raw_markdown(self, conversation_id: str, markdown_content: str):
        """
        保存完整的 Markdown 内容到对话文件。
        :param conversation_id: 对话 ID
        :param markdown_content: 完整的 Markdown 内容
        """
        path = self._get_file_path(conversation_id)
        if not os.path.exists(path):
            logging.error(f"Conversation file not found for saving: {conversation_id}")
            raise ValueError("Conversation not found")
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        
        # 更新 updated_at 时间戳
        self._update_timestamp(conversation_id)

    def delete_conversation(self, conversation_id: str):
        """删除对话文件"""
        path = self._get_file_path(conversation_id)
        if os.path.exists(path):
            os.remove(path)
