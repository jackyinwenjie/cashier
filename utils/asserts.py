"""断言工具"""
import json
import logging

from .extractor import extract_by_path


def http_assert(case: dict, response_data: dict):
    """
    根据 case["assert"] 对 HTTP 响应做断言。
    支持操作符: code=1, code=!=1, data=not_null, msg=exists
    """
    assert_str = case.get("assert", "").strip()
    if not assert_str:
        return

    try:
        rules = json.loads(assert_str)
    except json.JSONDecodeError:
        logging.warning(f"assert JSON 解析失败: {assert_str}")
        return

    for path, expected in rules.items():
        actual = extract_by_path(response_data, path)

        if isinstance(expected, str):
            if expected.startswith("!="):
                target = expected[2:].strip()
                try:
                    target = int(target)
                except ValueError:
                    pass
                assert actual != target, \
                    f"[{path}] 期望 != {target}, 实际 = {actual}"
            elif expected == "not_null":
                assert actual is not None, \
                    f"[{path}] 期望非空, 实际 = None"
            elif expected == "exists":
                assert actual is not None, \
                    f"[{path}] 字段不存在"
            else:
                assert str(actual) == expected, \
                    f"[{path}] 期望 {expected}, 实际 = {actual}"
        else:
            assert actual == expected, \
                f"[{path}] 期望 {expected}, 实际 = {actual}"

    logging.info(f"  断言通过: {case.get('id', '?')}")


def jdbc_assert(case: dict):
    """数据库断言占位（暂无 JDBC 能力）"""
    pass
