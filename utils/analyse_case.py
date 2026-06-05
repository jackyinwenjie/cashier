"""用例分析工具：Jinja2 渲染 + 请求结构解析"""
import json
import logging

from jinja2 import Template


def analyse_case(case: dict, all_dict: dict) -> dict:
    """
    1. 用 Jinja2 渲染 case 中的 {{ var }} 变量
    2. 解析为请求所需的结构
    返回: {"method": str, "url": str, "data": dict, "sign": bool}
    """
    # ── Jinja2 渲染 case ──
    rendered = {}
    for k, v in case.items():
        if isinstance(v, str) and "{{" in v:
            try:
                tpl = Template(v)
                rendered[k] = tpl.render(**all_dict)
            except Exception as e:
                logging.warning(f"渲染字段 [{k}] 失败: {e}")
                rendered[k] = v
        else:
            rendered[k] = v

    # ── 解析 method / path / data ──
    method = rendered.get("method", "POST").strip().upper()
    path = rendered.get("path", "").strip()
    base_url = all_dict.get("BASE_URL",
        "https://api-v3.ytsaas.com")
    url = f"{base_url}{path}"

    # ── 解析 data 字段（JSON 字符串 → dict）──
    data = {}
    data_str = rendered.get("data", "").strip()
    if data_str:
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            logging.warning(f"data JSON 解析失败: {data_str[:100]}...")

    # ── 解析 sign ──
    sign = True
    sign_str = rendered.get("sign", "").strip()
    if sign_str.lower() in ("false", "0", "no"):
        sign = False

    return {
        "method": method,
        "url": url,
        "data": data,
        "sign": sign,
        "special": rendered.get("special", "").strip(),
        "fixture": rendered.get("fixture", "api").strip(),
    }
