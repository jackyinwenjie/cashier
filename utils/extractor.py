"""响应提取工具"""
import json
import logging


def extract_by_path(data: dict, path: str):
    """
    按点号路径从响应 JSON 中提取值。
    例: "data.storing_wine_id" / "data.deposit.[0].goods_id"
    """
    parts = path.split(".")
    cur = data
    for part in parts:
        if part.startswith("[") and part.endswith("]"):
            idx = int(part[1:-1])
            if isinstance(cur, list) and idx < len(cur):
                cur = cur[idx]
            else:
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
        if cur is None:
            return None
    return cur


def json_extractor(case: dict, all_dict: dict, response_data: dict):
    """
    从响应中按 extract 规则提取值，存入 all_dict。
    extract 格式（JSON 字符串）: {"变量名": "响应路径", ...}
    """
    extract_str = case.get("extract", "").strip()
    if not extract_str:
        return

    try:
        rules = json.loads(extract_str)
    except json.JSONDecodeError:
        logging.warning(f"extract JSON 解析失败: {extract_str}")
        return

    for var_name, path in rules.items():
        val = extract_by_path(response_data, path)
        if val is not None:
            all_dict[var_name] = val
            logging.info(f"  提取: {var_name} = {val}")
