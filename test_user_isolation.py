"""
User Isolation and Authentication Test
======================================

该脚本用于验证阶段三引入的用户系统：
1. 未登录访问被拒绝 (401)。
2. 登录后可正常操作。
3. 不同用户之间的数据物理隔离（目录隔离）。
4. Session 记录 user_id 并正确应用于 StorageManager。

根据 trae_prompt.md 原则：
- 使用中文注释说明生成依据。
- reStructuredText 格式 docstring。
- 使用 logging 模块。
"""

import unittest
import logging
import os
import shutil
from fastapi.testclient import TestClient
from app.main import app, llm_client
import app.main as app_main

# 配置日志
logging.basicConfig(level=logging.INFO)

def setup_mock_llm():
    """
    设置 Mock LLM 客户端以避免真实 API 调用。
    """
    class MockLLMClient:
        async def chat_completion(self, messages, stream=False):
            async def _gen():
                yield "Mock response"
            return _gen()
    
    app_main.llm_client = MockLLMClient()

class TestUserIsolation(unittest.TestCase):
    """
    用户隔离与认证测试类。
    """

    @classmethod
    def setUpClass(cls):
        """
        测试前的全局设置。
        """
        setup_mock_llm()
        # 清理可能的测试数据
        cls.test_data_dir = os.path.join(os.path.dirname(__file__), "data", "conversations")
        if os.path.exists(cls.test_data_dir):
            shutil.rmtree(cls.test_data_dir)

    def setUp(self):
        """
        每个测试用例前的设置。
        """
        # 为每个用户创建独立的 TestClient 以模拟不同的 Session
        self.client_a = TestClient(app)
        self.client_b = TestClient(app)

    def test_unauthorized_access(self):
        """
        验证未登录时访问 API 会返回 401。
        
        Sample Input: GET /api/conversations (no session)
        Sample Output: 401 Unauthorized
        """
        logging.info("Testing unauthorized access...")
        response = self.client_a.get("/api/conversations")
        self.assertEqual(response.status_code, 401)
        self.assertIn("Not authenticated", response.json()["detail"])

    def test_login_and_me(self):
        """
        验证登录功能及 /api/me 接口。
        
        Sample Input: POST /api/login {user_id: "user_a"}
        Sample Output: 200 OK, user_id: "user_a"
        """
        logging.info("Testing login and /api/me...")
        # 登录
        login_resp = self.client_a.post("/api/login", json={"user_id": "user_a"})
        self.assertEqual(login_resp.status_code, 200)
        self.assertEqual(login_resp.json()["user_id"], "user_a")

        # 检查当前用户
        me_resp = self.client_a.get("/api/me")
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(me_resp.json()["user_id"], "user_a")

    def test_data_isolation(self):
        """
        验证不同用户之间的数据隔离。
        
        1. User A 创建一个对话。
        2. User B 登录，检查对话列表应为空。
        3. 验证文件系统中的目录结构。
        """
        logging.info("Testing data isolation...")
        
        # User A 登录并创建对话
        self.client_a.post("/api/login", json={"user_id": "user_a"})
        create_resp = self.client_a.post("/api/conversations", json={"name": "User A's Chat"})
        self.assertEqual(create_resp.status_code, 200)
        conv_id_a = create_resp.json()["id"]

        # User B 登录并查看对话
        self.client_b.post("/api/login", json={"user_id": "user_b"})
        list_resp_b = self.client_b.get("/api/conversations")
        self.assertEqual(list_resp_b.status_code, 200)
        self.assertEqual(len(list_resp_b.json()), 0, "User B should not see User A's conversations")

        # User A 再次查看
        list_resp_a = self.client_a.get("/api/conversations")
        self.assertEqual(len(list_resp_a.json()), 1)
        self.assertEqual(list_resp_a.json()[0]["id"], conv_id_a)

        # 验证物理目录
        user_a_dir = os.path.join(self.test_data_dir, "user_a")
        user_b_dir = os.path.join(self.test_data_dir, "user_b")
        self.assertTrue(os.path.exists(user_a_dir))
        self.assertTrue(os.path.exists(user_b_dir))
        self.assertTrue(os.path.exists(os.path.join(user_a_dir, f"{conv_id_a}.md")))

    def test_logout(self):
        """
        验证登出功能。
        """
        logging.info("Testing logout...")
        self.client_a.post("/api/login", json={"user_id": "user_a"})
        
        # 登出前可以访问
        self.assertEqual(self.client_a.get("/api/me").status_code, 200)
        
        # 登出
        logout_resp = self.client_a.post("/api/logout")
        self.assertEqual(logout_resp.status_code, 200)
        
        # 登出后无法访问
        self.assertEqual(self.client_a.get("/api/me").status_code, 401)

if __name__ == "__main__":
    unittest.main()
