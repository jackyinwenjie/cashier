"""测试结果收集器 —— 跨用例收集执行结果，供 HTML 报告使用"""
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TestResult:
    """单条用例的执行结果"""
    __test__ = False  # 抑制 pytest 收集警告
    case_id: str
    title: str
    feature: str
    story: str
    method: str
    path: str
    status: str = "PASS"          # PASS / FAIL
    duration: float = 0.0          # 秒
    error_msg: str = ""            # 失败信息
    request_url: str = ""          # 完整 URL
    request_method: str = ""       # GET/POST
    request_body: Optional[dict] = None   # 请求参数
    response_body: Optional[dict] = None  # 响应体


class ResultCollector:
    """全局结果收集器（类级单例）"""
    results: list = []
    _start_time: float = 0.0

    @classmethod
    def reset(cls):
        cls.results.clear()
        cls._start_time = time.time()

    @classmethod
    def add(cls, result: TestResult):
        cls.results.append(result)

    @classmethod
    def get_summary(cls) -> dict:
        total = len(cls.results)
        passed = sum(1 for r in cls.results if r.status == "PASS")
        failed = total - passed
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "duration": round(time.time() - cls._start_time, 2),
            "pass_rate": f"{passed / total * 100:.1f}%" if total else "N/A",
        }

    @classmethod
    def get_results(cls) -> list:
        return cls.results
