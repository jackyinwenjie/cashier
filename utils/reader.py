"""测试数据读取工具 — YAML 格式"""
import json
import logging
from pathlib import Path

import yaml


def read_cases(filepath: str = None) -> list[dict]:
    """从 test_data.yaml 读取用例，返回 list[dict]（值均为字符串）"""
    if filepath is None:
        filepath = Path(__file__).parent.parent / "test_data.yaml"
    elif not isinstance(filepath, Path):
        filepath = Path(filepath)

    logging.info(f"  使用 YAML 数据源: {filepath.name}")
    return _read_yaml(filepath)


# ══════════════════════════════════════
# YAML 读取（返回与 Excel 一致的 list[dict]）
# ══════════════════════════════════════

def _serialize(val) -> str:
    """将值转为字符串，保留 Excel 兼容格式"""
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def _read_yaml(filepath: Path) -> list[dict]:
    """从 YAML 文件读取，返回 list[dict]（值均为字符串）"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        raise ValueError(f"YAML 文件为空: {filepath}")

    cases = []
    for suite in data:
        feature = suite.get("feature", "")
        story = suite.get("story", "")
        tests = suite.get("tests", [])
        for test in tests:
            case = {
                "id":       test.get("id", ""),
                "feature":  feature,
                "story":    story,
                "title":    test.get("title", ""),
                "method":   test.get("method", "POST"),
                "path":     test.get("path", ""),
                "data":     _serialize(test.get("data", {})),
                "assert":   _serialize(test.get("assert", {})),
                "extract":  _serialize(test.get("extract", {})),
                "special":  test.get("special") or "",
                "sign":     _serialize(test.get("sign", True)),
                "fixture":  test.get("fixture", "api"),
            }
            cases.append(case)
    return cases

