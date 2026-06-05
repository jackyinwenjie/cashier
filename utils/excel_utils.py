"""Excel 读取工具"""
from pathlib import Path

import openpyxl


def read_excel(filepath: str = None) -> list[dict]:
    """
    读取测试用例 Excel，返回 list[dict]。
    首行为表头，每行一个用例。
    """
    if filepath is None:
        filepath = Path(__file__).parent.parent / "test_data.xlsx"
    else:
        filepath = Path(filepath)

    wb = openpyxl.load_workbook(str(filepath), data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError(f"Excel 文件为空: {filepath}")

    headers = [str(h).strip() if h else "" for h in rows[0]]
    cases = []

    for row in rows[1:]:
        if all(c is None for c in row):
            continue  # 跳过空行
        case = {}
        for i, header in enumerate(headers):
            val = row[i] if i < len(row) else None
            case[header] = str(val).strip() if val is not None else ""
        cases.append(case)

    wb.close()
    return cases
