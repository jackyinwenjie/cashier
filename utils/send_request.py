"""HTTP 请求发送工具"""
import logging

import requests

from .sign import signed_body


# 全局 session 缓存
_raw_session = None


def _get_raw_session() -> requests.Session:
    global _raw_session
    if _raw_session is None:
        _raw_session = requests.Session()
        _raw_session.trust_env = False
        _raw_session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "AutoTest/1.0",
        })
    return _raw_session


def send_http_request(client, method: str, url: str, data: dict,
                      sign: bool = True, **kwargs) -> dict:
    """
    发送 HTTP 请求。

    参数:
        client:  conftest.py 的 Client 实例（已含 token）
        method:  GET / POST
        url:     完整 URL
        data:    请求参数
        sign:    是否加签
    返回:      响应 JSON dict
    """
    body = signed_body(data) if sign else dict(data)

    if method == "GET":
        resp = client.get_explicit(url, body)
    else:
        resp = client.post_explicit(url, body)

    try:
        return resp.json()
    except Exception:
        return {"code": -1, "msg": str(resp.text)[:200]}


def send_http_request_raw(method: str, url: str, data: dict,
                          sign: bool = True) -> dict:
    """
    发送无认证 HTTP 请求（用于登录反向等）。
    """
    s = _get_raw_session()
    body = signed_body(data) if sign else dict(data)

    logging.info(f"  [RAW] {method} {url}")

    if method == "GET":
        resp = s.get(url, params=body)
    else:
        resp = s.post(url, json=body)

    try:
        return resp.json()
    except Exception:
        return {"code": -1, "msg": str(resp.text)[:200]}
