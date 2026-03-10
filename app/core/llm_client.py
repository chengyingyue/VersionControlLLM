import json
import os
import httpx
import logging
import hashlib
import re
from typing import AsyncGenerator, List, Dict, Any, Union
from datetime import datetime
import requests

# Load config
# The config file is located one level above the project root directory
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "LLM_config.json")

def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load config from {CONFIG_PATH}: {e}")
        return {}

config = load_config()

class LLMClient:
    def __init__(self):
        self.api_key = config.get("deepseek_api_key")
        self.base_url = config.get("deepseek_base_url")
        self.model_name = config.get("model_name", "deepseek-chat")
        self.debug_mode = config.get("debug_mode", False)
        # Mock 分片数量，默认 10，可从 config.json 中读取
        # 你是根据用户要求在 config.json 里改动分片数量的反馈修改的。使用中文注释。
        self.mock_chunk_count = config.get("mock_chunk_count", 10)

        self.log_dir = os.path.join(os.path.dirname(__file__), "log")
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Mock 响应存储路径
        # 你是根据 traeprompt.md 的原则 5 修改的。使用中文注释。
        self.mock_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "mock_responses")
        os.makedirs(self.mock_dir, exist_ok=True)
        
        if not self.api_key or self.api_key == "YOUR_KEY":
            logging.warning("Warning: API Key not set in config.json")
        
        if self.debug_mode:
            logging.info("LLM 调试模式已开启：将优先使用 data/mock_responses 中的打桩数据")

        # 初始化持久化的 AsyncClient，显式禁用 HTTP/2 以匹配 requests 的行为
        # 增加 trust_env=True 以确保能够读取系统的代理设置
        # 你是根据 traeprompt.md 的原则 1 和 5 修改的。使用中文注释。
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(6000.0, connect=60.0),
            http1=True,
            http2=False,
            trust_env=True
        )

    def _generate_hash(self, messages: List[Dict[str, str]]) -> str:
        """
        根据 messages 内容生成 SHA256 Hash 值。
        用于标识唯一的请求并作为 Mock 文件名。
        """
        # 将消息内容序列化为 JSON 字符串，确保 key 排序以保证 Hash 一致
        message_str = json.dumps(messages, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(message_str.encode('utf-8')).hexdigest()[:16]

    def _parse_mock_markdown(self, file_path: str) -> Dict[str, Any]:
        """
        解析 Markdown 格式的 Mock 数据。
        支持从结构化 Markdown（含 Metadata, Request, Response）中提取 Response。
        你是根据用户“保留 Request/Metadata 信息，只去除 stream chunks”的反馈修改的。使用中文注释。
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 使用正则提取 Response 章节的内容
            # 匹配 ## Response 之后直到下一个 ## 或文件末尾的内容
            response_pattern = r"## Response\n(.*?)(?:\n## |\Z)"
            response_match = re.search(response_pattern, content, re.DOTALL)
            response_content = response_match.group(1).strip() if response_match else content.strip()
            
            # 将回复内容动态分片（根据配置的 mock_chunk_count）
            stream_chunks = self._split_into_chunks(response_content)
                
            return {
                "response_content": response_content,
                "stream_chunks": stream_chunks
            }
        except Exception as e:
            logging.error(f"解析 Markdown Mock 文件失败: {e}")
            return {"response_content": "", "stream_chunks": []}

    def _split_into_chunks(self, text: str) -> List[str]:
        """
        根据 self.mock_chunk_count 将文本平分为 N 份。
        用于模拟流式输出。
        """
        if not text:
            return []
        
        num_chunks = self.mock_chunk_count
        length = len(text)
        size = max(1, length // num_chunks)
        chunks = []
        for i in range(num_chunks):
            start = i * size
            if i == num_chunks - 1:
                chunk = text[start:]
            else:
                chunk = text[start:start + size]
            if chunk:
                chunks.append(chunk)
        return chunks

    def _log_to_markdown(self, messages: List[Dict[str, str]], response_content: str):
        """
        根据 traeprompt.md 的原则，所有输出必须使用 logging 模块。
        此函数将对话记录到本地 markdown 文件中，方便调试。
        你是根据 traeprompt.md 的原则 3 和 5 生成的。使用中文注释。
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        log_file_path = os.path.join(self.log_dir, f"log_{timestamp}.md")

        try:
            with open(log_file_path, "w", encoding="utf-8") as f:
                f.write("# LLM Conversation Log\n\n")
                
                f.write("## Request\n\n")
                for message in messages:
                    f.write(f"**Role:** {message['role']}\n\n")
                    f.write("\n")
                    f.write(f"{message['content']}\n")
                    f.write("\n\n")

                f.write("---\n\n")
                
                f.write("## Response\n\n")
                f.write("\n")
                f.write(f"{response_content}\n")
                f.write("\n")
            logging.info(f"LLM 对话已记录到: {log_file_path}")
        except Exception as e:
            logging.error(f"记录 LLM 对话失败: {e}")

    async def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.7, stream: bool = False) -> Union[str, AsyncGenerator[str, None]]:
        """
        异步调用 DeepSeek API 进行聊天补全。
        支持流式（streaming）和非流式两种模式。
        你是根据 traeprompt.md 的原则 1, 2, 3, 5 生成的。使用中文注释。

        :param messages: 包含对话历史的消息列表。
        :type messages: List[Dict[str, str]]
        :param temperature: 控制生成文本的随机性。
        :type temperature: float
        :param stream: 是否启用流式响应。
        :type stream: bool
        :return: 非流式模式下返回响应字符串，流式模式下返回异步生成器。
        :rtype: Union[str, AsyncGenerator[str, None]]

        Sample Input:
        messages = [{"role": "user", "content": "你好"}]
        
        Sample Output (stream=False):
        "你好！有什么我可以帮您的吗？"
        """
        # 计算请求 Hash
        request_hash = self._generate_hash(messages)
        
        # 记录请求信息
        logging.info(f"===================== LLM Request (Hash: {request_hash}) =====================")
        logging.info(json.dumps(messages, indent=2, ensure_ascii=False))
        logging.info("=====================================================")

        # 如果开启了调试模式且存在 Mock 文件，则直接返回 Mock 数据
        if self.debug_mode:
            mock_file_path = None
            if isinstance(self.debug_mode, str):
                mock_file_path = os.path.join(self.mock_dir, self.debug_mode)
            elif self.debug_mode is True:
                # 优先匹配 .md，其次是 .json
                md_file = os.path.join(self.mock_dir, f"{request_hash}.md")
                json_file = os.path.join(self.mock_dir, f"{request_hash}.json")
                if os.path.exists(md_file):
                    mock_file_path = md_file
                elif os.path.exists(json_file):
                    mock_file_path = json_file

            if mock_file_path and os.path.exists(mock_file_path):
                try:
                    if mock_file_path.endswith(".json"):
                        with open(mock_file_path, "r", encoding="utf-8") as f:
                            mock_data = json.load(f)
                    else:
                        mock_data = self._parse_mock_markdown(mock_file_path)
                    
                    logging.info(f"使用 Mock 数据返回: {mock_file_path}")
                    
                    if stream:
                        async def mock_stream_generator():
                            for chunk in mock_data.get("stream_chunks", []):
                                yield chunk
                        return mock_stream_generator()
                    else:
                        return mock_data.get("response_content", "")
                except Exception as e:
                    logging.error(f"读取 Mock 文件失败: {e}，将回退到真实 API 调用。")

        # 2. 正常 API 调用
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "stream": stream
        }

        try:
            response = requests.post(url, headers=headers, json=data, stream=stream, timeout=120)
            response.raise_for_status()

            if stream:
                async def async_stream_generator():
                    full_response_for_log = ""
                    stream_chunks = []
                    for chunk in response.iter_lines():
                        if chunk:
                            decoded_chunk = chunk.decode('utf-8')
                            if decoded_chunk.startswith('data: '):
                                json_data_str = decoded_chunk[6:]
                                if json_data_str.strip() == '[DONE]':
                                    break
                                try:
                                    json_data = json.loads(json_data_str)
                                    delta_content = json_data.get('choices', [{}])[0].get('delta', {}).get('content', '')
                                    if delta_content:
                                        full_response_for_log += delta_content
                                        stream_chunks.append(delta_content)
                                        yield delta_content
                                except:
                                    continue
                    # 记录对话日志
                    self._log_to_markdown(messages, full_response_for_log)
                    # 录制 Mock 数据
                    self._save_mock_data(request_hash, messages, full_response_for_log, is_stream=True)

                return async_stream_generator()
            else:
                output_content = response.json()['choices'][0]['message']['content']
                self._log_to_markdown(messages, output_content)
                # 录制 Mock 数据
                self._save_mock_data(request_hash, messages, output_content, is_stream=False)
                return output_content

        except Exception as e:
            logging.error(f"LLM API 调用失败: {e}")
            if stream:
                async def error_gen(): yield f"Error: {str(e)}"
                return error_gen()
            return f"Error: {str(e)}"

    def _save_mock_data(self, request_hash: str, messages: List[Dict[str, str]], response_content: str, is_stream: bool = False):
        """
        保存 Mock 数据到本地，同时更新 latest.md。
        保存结构化的 Markdown（含 Metadata, Request, Response），但不在文件中保存 Stream Chunks。
        分片逻辑在回放时通过 self.mock_chunk_count 动态生成。
        你是根据用户“保留 Request/Metadata，只去除 stream chunks”的反馈修改的。使用中文注释。
        """
        try:
            # 构建结构化 Markdown 内容
            md_content = f"# LLM Mock Data\n\n"
            md_content += f"## Metadata\n"
            md_content += f"- Hash: {request_hash}\n"
            md_content += f"- Timestamp: {datetime.now().isoformat()}\n\n"
            md_content += f"---\n\n"
            
            md_content += f"## Request\n"
            for msg in messages:
                md_content += f"**{msg['role']}**: {msg['content']}\n\n"
            
            md_content += f"---\n\n"
            
            md_content += f"## Response\n"
            md_content += f"{response_content}\n\n"
            
            md_content += f"---\n"

            # 1. 保存为 Hash 命名的 .md 文件
            full_path = os.path.join(self.mock_dir, f"{request_hash}.md")
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            
            # 2. 同时保存为 latest.md，方便用户快速定位
            latest_path = os.path.join(self.mock_dir, "latest.md")
            with open(latest_path, "w", encoding="utf-8") as f:
                f.write(md_content)
                
            logging.info(f"Mock 数据已保存: {full_path} 并同步到 latest.md")
        except Exception as e:
            logging.error(f"保存 Mock 数据失败: {e}")

llm_client = LLMClient()
