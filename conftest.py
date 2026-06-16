"""
收银3.0收银台 - 框架核心
pytest 全局配置和 fixtures，自动处理验签和登录（收银员类型）。
"""
import logging
import os

import pytest
import requests
from dotenv import load_dotenv

load_dotenv()

from utils.result_collector import ResultCollector
from utils.html_reporter import generate_html
from utils.sign import SIGN_KEY, make_sign as sign, signed_body

# ========== 全局配置 ==========
BASE_URL = os.getenv("BASE_URL", "https://api-v3.ytsaas.com")

# 收银员登录凭证
LOGIN_ACCOUNT = os.getenv("LOGIN_ACCOUNT", "zdh")
LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD", "1")


# ========== Fixtures ==========
# 全局存储 websocket_token，供测试用例使用
WEBSOCKET_TOKEN = None


@pytest.fixture(scope="session")
def ws_token():
    """WebSocket 连接用的 JWT token"""
    global WEBSOCKET_TOKEN
    if WEBSOCKET_TOKEN is None:
        s = requests.Session()
        s.trust_env = False
        s.headers.update({"Content-Type": "application/json", "User-Agent": "AutoTest/1.0"})
        resp = s.post(f"{BASE_URL}/shop/login", json=signed_body({
            "account": LOGIN_ACCOUNT,
            "password": LOGIN_PASSWORD,
            "type": "cashier",
            "sms_code": "0",
        }))
        login_data = resp.json()
        if login_data.get("code") == 1 and isinstance(login_data.get("data"), dict):
            WEBSOCKET_TOKEN = login_data["data"].get("websocket_token")
        s.close()
    return WEBSOCKET_TOKEN


@pytest.fixture(scope="session")
def client():
    """API 客户端（收银员登录，自动验签）"""
    global WEBSOCKET_TOKEN
    s = requests.Session()
    s.trust_env = False
    s.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "AutoTest/1.0",
    })

    # 收银员登录（type=cashier）
    resp = s.post(f"{BASE_URL}/shop/login", json=signed_body({
        "account": LOGIN_ACCOUNT,
        "password": LOGIN_PASSWORD,
        "type": "cashier",
        "sms_code": "0",
    }))
    data = resp.json()
    token = None
    if isinstance(data.get("data"), dict):
        token = data["data"].get("access_token")
        WEBSOCKET_TOKEN = data["data"].get("websocket_token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
        print(f"\n[收银员登录] 成功, token: {token[:30]}...")
    else:
        print(f"\n[收银员登录] 失败: {data.get('msg')}")

    class Client:
        def __init__(self, session):
            self._s = session

        def get(self, path, **params):
            """GET 请求（自动加签）"""
            return self._s.get(f"{BASE_URL}{path}", params=signed_body(params))

        def post(self, path, **params):
            """POST 请求（自动加签）"""
            return self._s.post(f"{BASE_URL}{path}", json=signed_body(params))

        def put(self, path, **params):
            """PUT 请求（自动加签）"""
            return self._s.put(f"{BASE_URL}{path}", json=signed_body(params))

        def delete(self, path, **params):
            """DELETE 请求（自动加签）"""
            return self._s.delete(f"{BASE_URL}{path}", json=signed_body(params))

        # ── 原始方法（参数已加签，直接发送）──
        def get_explicit(self, url: str, params: dict):
            return self._s.get(url, params=params)

        def post_explicit(self, url: str, data: dict):
            return self._s.post(url, json=data)

    yield Client(s)
    s.close()


@pytest.fixture
def api(client):
    """简写别名"""
    return client


# ═══════════════════════════════════════════
#  Session 钩子：自动生成 HTML 测试报告
# ═══════════════════════════════════════════

def pytest_sessionstart(session):
    """测试开始前重置收集器"""
    ResultCollector.reset()


def pytest_sessionfinish(session, exitstatus):
    """测试结束后自动生成 HTML 报告"""
    report_path = generate_html()
    print(f"\n[报告] 测试报告已生成: {report_path}")
    summary = ResultCollector.get_summary()
    print(f"[报告] 总计: {summary['total']} | 通过: {summary['passed']} | "
          f"失败: {summary['failed']} | 通过率: {summary['pass_rate']}")
