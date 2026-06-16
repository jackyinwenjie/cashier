"""测试数据读取工具 — 支持 YAML 和 Excel 两种格式"""
import json
import logging
from pathlib import Path
from typing import Optional

import openpyxl
import yaml


def read_cases(filepath: Optional[str] = None) -> list[dict]:
    """
    自动检测文件格式，读取测试用例。
    返回 list[dict]，每个用例字段值统一为字符串（兼容下游 analyse_case）。
    """
    if filepath is None:
        yaml_path = Path(__file__).parent.parent / "test_data.yaml"
        xlsx_path = Path(__file__).parent.parent / "test_data.xlsx"
        if yaml_path.exists():
            filepath = str(yaml_path)
            logging.info(f"  使用 YAML 数据源: {yaml_path.name}")
        else:
            filepath = str(xlsx_path)
            logging.info(f"  使用 Excel 数据源: {xlsx_path.name}")

    filepath = Path(filepath)
    if filepath.suffix.lower() in (".yaml", ".yml"):
        return _read_yaml(filepath)
    else:
        return _read_excel(filepath)


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


# ══════════════════════════════════════
# Excel 读取（保持原有逻辑不变）
# ══════════════════════════════════════

def _read_excel(filepath: Path) -> list[dict]:
    """读取测试用例 Excel，返回 list[dict]"""
    wb = openpyxl.load_workbook(str(filepath), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError(f"Excel 文件为空: {filepath}")

    headers = [str(h).strip() if h else "" for h in rows[0]]
    cases = []
    for row in rows[1:]:
        if all(c is None for c in row):
            continue
        case = {}
        for i, header in enumerate(headers):
            val = row[i] if i < len(row) else None
            case[header] = str(val).strip() if val is not None else ""
        cases.append(case)
    wb.close()
    return cases
