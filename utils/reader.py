"""测试数据读取工具 — 多文件 YAML 模块化加载"""
import json
import logging
from pathlib import Path

import yaml


def read_cases(filepath: str = None) -> list[dict]:
    """
    从 test_data/ 目录加载所有 YAML 模块文件，返回 list[dict]。

    支持两种模式:
      - 默认: 扫描 test_data/ 目录下所有 .yaml/.yml 文件，按文件名排序加载
      - 指定文件: 传入单个 .yaml 路径则只加载该文件
    """
    if filepath is None:
        return _read_dir(Path(__file__).parent.parent / "test_data")
    path = Path(filepath)
    if path.is_dir():
        return _read_dir(path)
    return _read_one(path)


# ══════════════════════════════════════
# 内部实现
# ══════════════════════════════════════

def _read_dir(data_dir: Path) -> list[dict]:
    """扫描目录下所有 .yaml/.yml 文件，按文件名排序后加载"""
    files = sorted(data_dir.glob("*.yaml")) + sorted(data_dir.glob("*.yml"))
    if not files:
        raise FileNotFoundError(f"未找到任何 YAML 文件: {data_dir}")

    all_cases = []
    for f in files:
        logging.info(f"  加载模块: {f.name}")
        cases = _read_one(f)
        all_cases.extend(cases)
    logging.info(f"  共加载 {len(all_cases)} 条用例 ({len(files)} 个模块)")
    return all_cases


def _read_one(filepath: Path) -> list[dict]:
    """读取单个 YAML 文件，返回 list[dict]"""
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


def _serialize(val) -> str:
    """将值转为字符串，保留兼容格式"""
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
