"""
收银3.0收银台 - Excel 数据驱动测试框架
├── test_data.xlsx   ← 📋 用例数据（新增用例只需加一行）
├── test_runner.py   ← 🚀 测试执行器（无需改代码）
└── utils/           ← 🔧 工具模块
    ├── excel_utils   - 读取 Excel
    ├── analyse_case  - Jinja2 渲染 + 解析
    ├── send_request  - HTTP 请求发送
    ├── extractor     - JSON 响应提取
    ├── asserts       - 断言检查
    ├── sign          - 签名工具
    └── handlers      - 特殊动作（WebSocket / 动态参数）
"""
import json
import logging
import time
from datetime import datetime, timedelta

import pytest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)

from utils.asserts import http_assert, jdbc_assert
from utils.analyse_case import analyse_case
from utils.excel_utils import read_excel
from utils.extractor import json_extractor
from utils.send_request import send_http_request, send_http_request_raw
from utils.handlers import (
    WS_SPECIALS, WS_HANDLERS, HANDLER_PRE, HANDLER_SETTLE, HANDLER_POST,
)
from utils.result_collector import ResultCollector, TestResult

# 读取测试用例（模块级，确保 IDE 测试发现能解析）
_test_cases = read_excel()

# ══════════════════════════════════════════════════════════
# 全局配置（注入 context_template 供 Jinja2 模板使用）
# ══════════════════════════════════════════════════════════

class TestRunner:
    """Excel 驱动测试运行器：读 Excel → 渲染 → 发送 → 断言 → 提取"""

    # 全局上下文（可变，跨用例共享动态提取值如 order_id / storing_wine_id）
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    context = {
        "BASE_URL":       "https://api-v3.ytsaas.com",
        "SHOP_ID":        "3226",
        "BOX_ID":         "64291",
        "BOX_ID_NEW":     "64545",
        "STORING_BOX_ID": "64399",
        "RESERVE_BOX_ID": "64398",
        "VIP_ID":         "4",
        "GIVE_USER_ID":   "21053",
        "USER_PHONE":     "18222222222",
        "LOGIN_ACCOUNT":  "zdh",
        "LOGIN_PASSWORD": "1",
        "TODAY":          today,
        "TOMORROW":       tomorrow,
    }

    @pytest.mark.parametrize("case", _test_cases)
    def test_case(self, client, ws_token, case):
        """核心用例执行流程"""

        case_id = case.get("id", "?")
        case_title = case.get("title", "")
        case_feature = case.get("feature", "")
        case_story = case.get("story", "")
        t_start = time.time()

        # 引用全局上下文（用于跨用例共享动态提取值如 order_id）
        all_dict = TestRunner.context
        # 注入 ws_token 供 WebSocket 处理使用
        all_dict["ws_token"] = ws_token

        fixture_type = case.get("fixture", "api").strip()

        # ══ 步骤 1: 用例信息日志 ══
        logging.info(
            f"[{case_id}] "
            f"模块:{case_feature} "
            +
            f"场景:{case_story} "
            f"标题:{case_title}"
        )

        # ══ 步骤 2: Jinja2 渲染 + 解析请求数据 ══
        request_data = analyse_case(case, all_dict)

        special = request_data.get("special", "")
        req_method = request_data.get("method", "")
        req_url = request_data.get("url", "")
        req_body = request_data.get("data", {})

        logging.info(f"  → {req_method} {req_url}")

        # ── 请求快照（失败时写入报告）──
        req_snapshot = {
            "method": req_method,
            "url": req_url,
            "body": dict(req_body) if isinstance(req_body, dict) else req_body,
        }

        res = None
        ws_close = None
        try:
            # ══ 步骤 3: 特殊动作 — 请求前 ══
            if special in WS_SPECIALS:
                ws_close = WS_HANDLERS[special](client, case, all_dict)
            elif special in HANDLER_PRE:
                HANDLER_PRE[special](client, case, all_dict)

            # ══ 步骤 4: 合并特殊参数 ══
            if special in HANDLER_SETTLE:
                extra = HANDLER_SETTLE[special](client, case, all_dict)
                request_data["data"].update(extra)
                req_snapshot["body"] = dict(request_data["data"])

            # ══ 步骤 5: 发送 HTTP 请求 ══
            if fixture_type == "none":
                res = send_http_request_raw(
                    method=req_method,
                    url=req_url,
                    data=request_data["data"],
                    sign=request_data.get("sign", True),
                )
            else:
                res = send_http_request(client, **request_data)

            logging.info(f"  ← {json.dumps(res, ensure_ascii=False)[:200]}")

            # ══ 步骤 6: WebSocket 收尾 ══
            if ws_close:
                ws_close()

            # ══ 步骤 7: JSON 提取 ══
            json_extractor(case, all_dict, res)

            # ══ 步骤 8: 特殊动作 — 请求后 ══
            if special in HANDLER_POST:
                HANDLER_POST[special](client, case, all_dict, res)

            # ══ 步骤 9: 断言 ══
            http_assert(case, res)
            jdbc_assert(case)

            # ✅ 通过
            elapsed = time.time() - t_start
            ResultCollector.add(TestResult(
                case_id=case_id,
                title=case_title,
                feature=case_feature,
                story=case_story,
                method=req_method,
                path=req_url,
                status="PASS",
                duration=round(elapsed, 3),
            ))
            logging.info(f"  ✅ [{case_id}] 通过 ({elapsed:.2f}s)")

        except Exception as e:
            elapsed = time.time() - t_start
            error_text = str(e)

            logging.error(f"  ❌ [{case_id}] 失败 ({elapsed:.2f}s): {error_text}")

            # 记录失败详情
            ResultCollector.add(TestResult(
                case_id=case_id,
                title=case_title,
                feature=case_feature,
                story=case_story,
                method=req_method,
                path=req_url,
                status="FAIL",
                duration=round(elapsed, 3),
                error_msg=error_text,
                request_method=req_method,
                request_url=req_url,
                request_body=req_snapshot.get("body"),
                response_body=res,
            ))

            # 重新抛出，让 pytest 标记为失败
            raise
