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
#  Session 钩子：Allure 环境配置 + 报告提示
# ═══════════════════════════════════════════

def pytest_sessionstart(session):
    """测试开始前写入 Allure 环境配置 + 清理旧报告服务"""
    import shutil
    import subprocess
    from datetime import datetime

    allure_dir = os.path.join(os.path.dirname(__file__), "allure-results")
    config_dir = os.path.join(os.path.dirname(__file__), "allure_config")

    # 确保目录存在
    os.makedirs(allure_dir, exist_ok=True)

    # ── 0. 关闭旧的 Allure 服务（释放 18080 端口）──
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "$c = Get-NetTCPConnection -LocalPort 18080 -ErrorAction SilentlyContinue; "
             "if ($c) { $c | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force } }"],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass

    # ── 1. 写入 environment.properties（中文转 Unicode 防止乱码）──
    env_props = {
        "项目名称": "收银3.0收银台",
        "接口地址": BASE_URL,
        "门店ID": os.getenv("SHOP_ID", "3226"),
        "包厢ID": os.getenv("BOX_ID", "64291"),
        "测试框架": "pytest + allure-pytest",
        "Python版本": "3.10",
        "报告时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "用例来源": "test_data/ (YAML 多模块)",
        "认证方式": "收银员Token自动验签",
    }
    env_path = os.path.join(allure_dir, "environment.properties")
    with open(env_path, "w", encoding="utf-8") as f:
        for k, v in env_props.items():
            k_asc = k.encode("ascii", "backslashreplace").decode("ascii")
            v_asc = v.encode("ascii", "backslashreplace").decode("ascii")
            f.write(f"{k_asc}={v_asc}\n")

    # ── 2. 拷贝 categories.json ──
    cat_src = os.path.join(config_dir, "categories.json")
    cat_dst = os.path.join(allure_dir, "categories.json")
    if os.path.isfile(cat_src):
        shutil.copy(cat_src, cat_dst)


def pytest_sessionfinish(session, exitstatus):
    """测试结束后自动打开 Allure 报告（内置 HTTP 服务）"""
    import subprocess
    from pathlib import Path

    project_dir = Path(__file__).parent
    allure_results = project_dir / "allure-results"

    if not allure_results.is_dir():
        return

    # ── 定位 allure 可执行路径 ──
    allure_exe = None
    for candidate in [
        Path(os.environ.get("USERPROFILE", "")) / "tools" / "allure" / "allure-2.30.0" / "bin" / "allure.bat",
    ]:
        if candidate and candidate.is_file():
            allure_exe = str(candidate)
            break
    if allure_exe is None:
        allure_exe = "allure"

    # ── 构造环境变量 ──
    env = os.environ.copy()
    for jdk_path in [
        r"C:\Program Files\Java\jre1.8.0_77",
        r"C:\Program Files\Java\jdk-17",
    ]:
        if os.path.isdir(jdk_path):
            env["JAVA_HOME"] = jdk_path
            break

    # ── allure serve 一键生成 + HTTP 服务 + 浏览器打开 ──
    try:
        subprocess.Popen(
            [allure_exe, "serve", "-p", "18080", str(allure_results)],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print(f"\n[报告] Allure 报告已启动: http://192.168.6.197:18080/")
        print(f"[报告] 每次运行后自动覆盖，浏览器打开上述地址即可查看")
    except FileNotFoundError:
        print("\n[报告] 未找到 allure 命令，请确认已安装 Allure 命令行工具")
    except Exception as e:
        print(f"\n[报告] 报告启动异常: {e}")
