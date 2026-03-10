"""
Manual API Test (FastAPI TestClient)
===================================

该脚本用于验证 `todo.md` 中“阶段一验证方法 (Manual API Test)”覆盖的核心 API 行为：

- 创建对话：`POST /api/conversations`
- 流式对话：`POST /api/chat`（SSE: delta/complete）
- 对话 Fork：`POST /api/fork`
- 历史重写：`POST /api/rewrite`
- 中止生成：`POST /api/chat/stop`（SSE: stopped + 文件保存 [Stopped]）
- 改名与导出：`POST /api/conversations/rename`、`GET /api/conversations/{id}/export`

该脚本不依赖真实 LLM 配置：通过替换 `app.main.llm_client` 为本地 Mock，保证可重复、可离线运行。

Sample Input:
    python manual_api_test.py

Sample Output:
    INFO - test_create_conversation_and_file_created ... ok
    INFO - test_stream_chat_appends_messages_and_sse_events ... ok
    INFO - test_fork_creates_new_file_with_new_id_and_name ... ok
    INFO - test_rewrite_truncates_and_regenerates_messages ... ok
    INFO - test_stop_chat_stops_stream_and_persists_stopped_marker ... ok
    INFO - test_rename_and_export ... ok
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncGenerator, Dict, Iterable, List, Optional, Tuple

from fastapi.testclient import TestClient

import app.main as app_main


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
)


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def _conversation_md_path(conversation_id: str, user_id: str = "debug_user") -> Path:
    return _project_root() / "data" / "conversations" / user_id / f"{conversation_id}.md"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _split_frontmatter(markdown: str) -> Tuple[str, str]:
    if not markdown.startswith("---"):
        return "", markdown
    parts = markdown.split("---", 2)
    if len(parts) < 3:
        return "", markdown
    return parts[1], parts[2]


def _iter_sse_json_objects(lines: Iterable[object]) -> Iterable[Dict[str, object]]:
    for raw_line in lines:
        if raw_line is None:
            continue
        if isinstance(raw_line, bytes):
            line = raw_line.decode("utf-8", errors="replace")
        else:
            line = str(raw_line)
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload:
            continue
        yield json.loads(payload)


@dataclass(frozen=True)
class _MockLLMScenario:
    response_text: str
    chunk_delay_s: float = 0.0

    def chunks(self) -> List[str]:
        chunk_size = 16
        return [self.response_text[i : i + chunk_size] for i in range(0, len(self.response_text), chunk_size)]


class _MockLLMClient:
    def __init__(self, chunk_delay_s: float = 0.0, response_repeat: int = 1):
        self._chunk_delay_s = float(chunk_delay_s)
        self._response_repeat = max(1, int(response_repeat))

    async def chat_completion(
        self, messages: List[Dict[str, str]], temperature: float = 0.7, stream: bool = False
    ) -> AsyncGenerator[str, None]:
        last_user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = msg.get("content", "")
                break

        scenario = _MockLLMScenario(
            response_text=(f"MOCK_RESPONSE::{last_user}") * self._response_repeat,
            chunk_delay_s=self._chunk_delay_s,
        )

        async def _gen() -> AsyncGenerator[str, None]:
            for chunk in scenario.chunks():
                if scenario.chunk_delay_s > 0:
                    await asyncio.sleep(scenario.chunk_delay_s)
                yield chunk

        return _gen()


class ManualApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._original_llm_client = app_main.llm_client
        app_main.llm_client = _MockLLMClient(chunk_delay_s=0.0)
        cls.client = TestClient(app_main.app)

    @classmethod
    def tearDownClass(cls) -> None:
        app_main.llm_client = cls._original_llm_client
        cls.client.close()

    def _create_conversation(self, name: str = "测试对话", system_prompt: str = "你是一个助手") -> str:
        resp = self.client.post(
            "/api/conversations",
            json={"name": name, "system_prompt": system_prompt},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        conv_id = resp.json()["id"]
        self.assertTrue(conv_id)
        return conv_id

    def test_create_conversation_and_file_created(self) -> None:
        conv_id = self._create_conversation(name="创建对话-文件生成")
        md_path = _conversation_md_path(conv_id)
        self.assertTrue(md_path.exists(), f"对话文件未生成: {md_path}")

        content = _read_text(md_path)
        self.assertTrue(content.startswith("---"), "缺少 Frontmatter")
        self.assertIn(f"id: {conv_id}", content)
        self.assertIn("name: 创建对话-文件生成", content)
        self.assertIn("# Message 0 (System)", content)

    def test_stream_chat_appends_messages_and_sse_events(self) -> None:
        conv_id = self._create_conversation(name="流式对话-SSE")
        user_message = "你好，给我一个简短回复"

        deltas: List[str] = []
        got_complete = False
        with self.client.stream(
            "POST",
            "/api/chat",
            json={"conversation_id": conv_id, "message": user_message},
        ) as resp:
            self.assertEqual(resp.status_code, 200, f"status_code={resp.status_code}")
            for obj in _iter_sse_json_objects(resp.iter_lines()):
                obj_type = obj.get("type")
                if obj_type == "delta":
                    deltas.append(str(obj.get("content", "")))
                elif obj_type == "complete":
                    got_complete = True
                    break
                elif obj_type == "error":
                    self.fail(f"SSE 返回 error: {obj}")

        self.assertTrue(deltas, "未收到任何 delta")
        self.assertTrue(got_complete, "未收到 complete 事件")

        md_path = _conversation_md_path(conv_id)
        content = _read_text(md_path)
        self.assertIn("# Message 1 (User)", content)
        self.assertIn(user_message, content)
        self.assertIn("# Message 2 (Assistant)", content)
        self.assertIn("".join(deltas), content)

    def test_fork_creates_new_file_with_new_id_and_name(self) -> None:
        conv_id = self._create_conversation(name="Fork-源对话")
        _ = self.client.post("/api/chat", json={"conversation_id": conv_id, "message": "用于 fork 的消息"}).close()

        resp = self.client.post(
            "/api/fork",
            json={"conversation_id": conv_id, "new_name": "Fork-新分支"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        fork_id = resp.json()["id"]
        self.assertNotEqual(fork_id, conv_id)

        src_content = _read_text(_conversation_md_path(conv_id))
        fork_content = _read_text(_conversation_md_path(fork_id))

        src_meta, src_body = _split_frontmatter(src_content)
        fork_meta, fork_body = _split_frontmatter(fork_content)

        self.assertIn(f"id: {conv_id}", src_meta)
        self.assertIn(f"id: {fork_id}", fork_meta)
        self.assertIn("name: Fork-新分支", fork_meta)
        self.assertEqual(src_body, fork_body, "Fork 后消息体内容应保持一致")

    def test_rewrite_truncates_and_regenerates_messages(self) -> None:
        conv_id = self._create_conversation(name="Rewrite-对话")
        first_user = "第一次提问"
        with self.client.stream(
            "POST",
            "/api/chat",
            json={"conversation_id": conv_id, "message": first_user},
        ) as resp:
            for obj in _iter_sse_json_objects(resp.iter_lines()):
                if obj.get("type") in {"complete", "error"}:
                    break

        before = _read_text(_conversation_md_path(conv_id))
        self.assertIn(first_user, before)
        self.assertIn("# Message 2 (Assistant)", before)

        rewritten_user = "重写后的提问"
        deltas: List[str] = []
        got_complete = False
        with self.client.stream(
            "POST",
            "/api/rewrite",
            json={"conversation_id": conv_id, "index": 1, "new_content": rewritten_user, "role": "user"},
        ) as resp:
            self.assertEqual(resp.status_code, 200, f"status_code={resp.status_code}")
            for obj in _iter_sse_json_objects(resp.iter_lines()):
                obj_type = obj.get("type")
                if obj_type == "delta":
                    deltas.append(str(obj.get("content", "")))
                elif obj_type == "complete":
                    got_complete = True
                    break
                elif obj_type == "error":
                    self.fail(f"rewrite 返回 error: {obj}")

        self.assertTrue(got_complete, "rewrite 未收到 complete")

        after = _read_text(_conversation_md_path(conv_id))
        self.assertNotIn(first_user, after, "rewrite 后旧的 Message 1 应被替换")
        self.assertIn(rewritten_user, after)
        self.assertIn("".join(deltas), after)

        body = _split_frontmatter(after)[1]
        self.assertEqual(body.count("# Message 0 (System)"), 1)
        self.assertEqual(body.count("# Message 1 (User)"), 1)
        self.assertEqual(body.count("# Message 2 (Assistant)"), 1)

    def test_stop_chat_stops_stream_and_persists_stopped_marker(self) -> None:
        conv_id = self._create_conversation(name="Stop-对话")
        app_main.llm_client = _MockLLMClient(chunk_delay_s=0.01, response_repeat=200)

        received_types: List[str] = []
        thread_errors: List[str] = []

        def _run_stream_request() -> None:
            try:
                with TestClient(app_main.app) as client_stream:
                    with client_stream.stream(
                        "POST",
                        "/api/chat",
                        json={"conversation_id": conv_id, "message": "触发 stop 的长输出"},
                    ) as resp:
                        if resp.status_code != 200:
                            thread_errors.append(f"stream status_code={resp.status_code}")
                            return
                        for obj in _iter_sse_json_objects(resp.iter_lines()):
                            obj_type = str(obj.get("type"))
                            received_types.append(obj_type)
                            if obj_type in {"complete", "stopped", "error"}:
                                break
            except Exception as e:
                thread_errors.append(str(e))

        t = threading.Thread(target=_run_stream_request, daemon=True)
        t.start()

        stop_sent = False
        stop_resp = None
        deadline = time.time() + 3.0
        while time.time() < deadline:
            with TestClient(app_main.app) as client_stop:
                stop_resp = client_stop.post("/api/chat/stop", params={"conversation_id": conv_id})
            if stop_resp.status_code == 200 and stop_resp.json().get("message") == "Stop signal sent":
                stop_sent = True
                break
            time.sleep(0.05)

        self.assertTrue(stop_sent, f"stop 信号未发送成功，last_resp={getattr(stop_resp, 'text', None)}")
        self.assertEqual(stop_resp.status_code, 200, stop_resp.text)

        t.join(timeout=5.0)
        self.assertFalse(thread_errors, f"stream 线程异常: {thread_errors}")
        self.assertIn("stopped", received_types, f"未收到 stopped 事件，实际: {received_types}")

        content = _read_text(_conversation_md_path(conv_id))
        self.assertIn("[Stopped]", content, "stop 后文件应包含 [Stopped] 标记")

        app_main.llm_client = _MockLLMClient(chunk_delay_s=0.0)

    def test_rename_and_export(self) -> None:
        conv_id = self._create_conversation(name="Rename-对话")

        rename_resp = self.client.post(
            "/api/conversations/rename",
            json={"conversation_id": conv_id, "new_name": "Rename-对话-新名称"},
        )
        self.assertEqual(rename_resp.status_code, 200, rename_resp.text)

        export_resp = self.client.get(f"/api/conversations/{conv_id}/export")
        self.assertEqual(export_resp.status_code, 200, export_resp.text)

        exported = export_resp.text
        self.assertIn("name: Rename-对话-新名称", exported)
        self.assertIn(f"id: {conv_id}", exported)


if __name__ == "__main__":
    start = time.time()
    result = unittest.main(exit=False)
    elapsed = time.time() - start
    logging.info("manual_api_test completed: %s, elapsed=%.2fs", result.result.wasSuccessful(), elapsed)
