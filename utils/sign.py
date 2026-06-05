"""签名工具"""
import hashlib
import time
from typing import Any

SIGN_KEY = "JOqA4dzZDych2oaTPsJksryVeahpbHWa"


def make_sign(params: dict[str, Any]) -> str:
    """SHA1 签名，跳过 list/dict 类型字段"""
    filtered = {}
    for k, v in params.items():
        if isinstance(v, (list, dict)):
            continue
        filtered[k] = "" if v is None else (v.strip() if isinstance(v, str) else v)
    keys = sorted(filtered.keys())
    s = "&".join(f"{k}={filtered[k]}" for k in keys)
    return hashlib.sha1(f"{s}&key={SIGN_KEY}".encode()).hexdigest().lower()


def signed_body(params: dict[str, Any]) -> dict[str, Any]:
    """给参数加上 time 和 sign"""
    body = dict(params)
    body["time"] = int(time.time() * 1000)
    body["sign"] = make_sign(body)
    return body
