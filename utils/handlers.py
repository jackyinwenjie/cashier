"""特殊动作处理器
每个处理器对应 Excel 中 special 列的值，处理前后钩子逻辑。
"""
import gzip
import base64
import json
import logging
import threading
import time
from datetime import datetime, timedelta

import websocket


# ══════════════════════════════════════════════════════
# WebSocket 开台 → 提取 order_id
# ══════════════════════════════════════════════════════

def handle_websocket_open_table(client, case: dict, all_dict: dict):
    """WebSocket 监听开台 → 需要 ws_token"""
    ws_url = (
        f"ws://wsv3.ytsaas.com?"
        f"token={all_dict.get('ws_token', '')}"
        f"&shop_id={all_dict.get('SHOP_ID', '')}"
        f"&ipv4=192.168.6.197"
    )
    logging.info("  [WS] 连接中...")

    ws_order_id = None
    ws_event = threading.Event()

    def on_message(ws, raw_msg):
        nonlocal ws_order_id
        try:
            decoded = raw_msg
            if isinstance(raw_msg, bytes):
                decoded = gzip.decompress(raw_msg).decode("utf-8")
            elif isinstance(raw_msg, str) and raw_msg.startswith("H4sIA"):
                decoded = gzip.decompress(base64.b64decode(raw_msg)).decode("utf-8")
            ws_data = json.loads(decoded)
            box_list = ws_data.get("data", {}).get("data", [])
            if box_list and isinstance(box_list, list):
                for box in box_list:
                    oid = box.get("order_id", 0)
                    if oid and oid != 0 and box.get("box_status") == 31:
                        ws_order_id = oid
                        ws_event.set()
                        logging.info(f"  [WS] order_id={oid}")
        except Exception:
            pass

    ws = websocket.WebSocketApp(ws_url,
        on_message=on_message,
        on_error=lambda ws, e: logging.warning(f"  [WS 错误] {e}"),
        on_close=lambda ws, c, m: None,
        on_open=lambda ws: None)
    ws_thread = threading.Thread(target=ws.run_forever, daemon=True)
    ws_thread.start()
    time.sleep(1.5)

    # 返回关闭回调
    def wait_and_close():
        ws_event.wait(timeout=10)
        ws.close()
        time.sleep(0.5)
        assert ws_order_id is not None, "WebSocket 未推送 order_id"
        all_dict["order_id"] = ws_order_id
        logging.info(f"  [WS] 最终 order_id={ws_order_id}")

    return wait_and_close


# ══════════════════════════════════════════════════════
# 请求前钩子（修改 all_dict 或返回额外参数）
# ══════════════════════════════════════════════════════

def _get_goodsorders(client, all_dict: dict):
    """通用：查询商品行列表"""
    from .sign import signed_body
    from .extractor import extract_by_path

    resp = client.get_explicit(
        f"{all_dict['BASE_URL']}/cashier/goodsorders/index",
        signed_body({
            "order_id": all_dict["order_id"],
            "shop_id": all_dict["SHOP_ID"],
        })
    )
    data = resp.json()
    assert data.get("code") == 1, f"查询商品行失败: {data}"
    items = data.get("data", {}).get("goods_data", [])
    assert len(items) > 0, "未返回商品行"
    return items


def pre_add_goods_extract(client, case: dict, all_dict: dict) -> dict:
    """点单后查询并提取商品行信息（post 钩子实际执行）"""
    return {}  # 请求前无需额外参数


def post_add_goods_extract(client, case: dict, all_dict: dict, response_data: dict):
    """点单后查询商品行 → 提取 first_line_id, goods_money"""
    items = _get_goodsorders(client, all_dict)
    all_dict["first_line_id"] = items[0]["id"]
    all_dict["goods_money"] = float(items[0]["money"])
    logging.info(f"  → 第一行 id={all_dict['first_line_id']} "
                 f"money={all_dict['goods_money']}")
    for item in items:
        logging.info(f"    行 id={item['id']} name={item['goods_name']} "
                     f"num={item['num']} money={item['money']}")


def pre_goods_refund_param(client, case: dict, all_dict: dict) -> dict:
    """退品前：查询可退商品行"""
    all_dict["_refund_num"] = 1
    items = _get_goodsorders(client, all_dict)
    for item in items:
        if item.get("state") == 1 and int(item.get("num", 0)) > 0:
            all_dict["_refund_line_id"] = item["id"]
            logging.info(f"  → 退品行 id={item['id']}")
            return {}
    all_dict["_refund_line_id"] = all_dict.get("first_line_id")
    return {}


def settle_goods_refund_param(client, case: dict, all_dict: dict) -> dict:
    """退品：合并额外参数到请求体"""
    return {
        "goods_orders": [{
            "goods_orders_id": all_dict["_refund_line_id"],
            "num": all_dict["_refund_num"],
        }],
    }


def pre_settlement_param(client, case: dict, all_dict: dict) -> dict:
    """单品结算前：查询可结算行"""
    items = _get_goodsorders(client, all_dict)
    for item in items:
        if item.get("state") == 1 and float(item.get("receivable_money", 0)) > 0:
            all_dict["_settle_line_id"] = item["id"]
            all_dict["_settle_money"] = float(item["receivable_money"])
            logging.info(f"  → 结算行 id={all_dict['_settle_line_id']} "
                         f"money={all_dict['_settle_money']}")
            return {}
    debug = [(i["id"], i["money"], i.get("state")) for i in items]
    raise AssertionError(f"无可用结算行: {debug}")


def settle_settlement_param(client, case: dict, all_dict: dict) -> dict:
    """单品结算：合并额外参数"""
    return {
        "payment_method": [{"id": 37, "money": all_dict["_settle_money"], "type": 1}],
        "goods": [all_dict["_settle_line_id"]],
    }


def pre_set_settlement_param(client, case: dict, all_dict: dict) -> dict:
    """整体结账前：计算未付款总额"""
    items = _get_goodsorders(client, all_dict)
    total = int(sum(
        float(it["receivable_money"]) for it in items
        if it.get("state") == 1 and float(it.get("money", 0)) > 0
    ))
    all_dict["_settle_total"] = total
    logging.info(f"  → 未付款应收总金额={total}")
    return {}


def settle_set_settlement_param(client, case: dict, all_dict: dict) -> dict:
    """整体结账：合并额外参数"""
    return {
        "payment_method": [{"id": 37, "money": all_dict["_settle_total"], "type": 1}],
    }


def pre_storing_query_extract(client, case: dict, all_dict: dict) -> dict:
    """查询寄存后提取明细 DB id"""
    from .sign import signed_body
    from .extractor import extract_by_path

    resp = client.get_explicit(
        f"{all_dict['BASE_URL']}/cashier/storingwines/index",
        signed_body({
            "storing_wines_id": all_dict["storing_wine_id"],
            "shop_id": all_dict["SHOP_ID"],
        })
    )
    data = resp.json()
    assert data.get("code") == 1, f"查询寄存失败: {data}"
    items = data.get("data", {}).get("data", [])
    if items:
        children = items[0].get("children", [])
        if children:
            all_dict["deposit_detail_id"] = children[0]["id"]
            logging.info(f"  → deposit_detail_id={all_dict['deposit_detail_id']}")
            return {}
    # 兜底
    deposit = all_dict.get("deposit_data", [])
    if deposit:
        all_dict["deposit_detail_id"] = deposit[0].get("id") or \
                                        all_dict.get("deposit_goods_id")
    assert all_dict.get("deposit_detail_id"), "未找到寄存商品明细 DB id"
    return {}


def pre_take_wine_param(client, case: dict, all_dict: dict) -> dict:
    """支取前构造 goods_array"""
    goods_id = str(all_dict.get("deposit_goods_id") or
                   (all_dict.get("deposit_data", [{}])[0].get("goods_id", "16")))
    goods_num = str(all_dict.get("deposit_goods_num") or
                    (all_dict.get("deposit_data", [{}])[0].get("num", "2")))
    detail_id = all_dict.get("deposit_detail_id")
    return {}


def settle_take_wine_param(client, case: dict, all_dict: dict) -> dict:
    """支取：合并 goods_array 到请求体"""
    goods_id = str(all_dict.get("deposit_goods_id") or
                   (all_dict.get("deposit_data", [{}])[0].get("goods_id", "16")))
    goods_num = str(all_dict.get("deposit_goods_num") or
                    (all_dict.get("deposit_data", [{}])[0].get("num", "2")))
    detail_id = all_dict.get("deposit_detail_id")
    return {
        "goods_array": [{
            "goods_id": goods_id,
            "id": detail_id,
            "num": goods_num,
            "storing_wines_id": all_dict["storing_wine_id"],
        }],
    }


def pre_reserve_param(client, case: dict, all_dict: dict) -> dict:
    """预订：生成动态时间"""
    eta = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    all_dict["_eta_time"] = eta
    logging.info(f"  → eta_time={eta}")
    return {}


def settle_reserve_param(client, case: dict, all_dict: dict) -> dict:
    """预订：合并动态时间"""
    return {"eta_time": all_dict["_eta_time"]}


def pre_reserve_query_extract(client, case: dict, all_dict: dict) -> dict:
    """查询预订后提取 max(id)"""
    from .sign import signed_body
    from .extractor import extract_by_path

    resp = client.get_explicit(
        f"{all_dict['BASE_URL']}/cashier/reserve/index",
        signed_body({"shop_id": all_dict["SHOP_ID"]})
    )
    data = resp.json()
    assert data.get("code") == 1, f"查询预订失败: {data}"
    items = data.get("data", {}).get("data", [])
    assert items and len(items) > 0, "预订列表为空"
    all_dict["reserve_id"] = max(it["id"] for it in items)
    logging.info(f"  → reserve_id={all_dict['reserve_id']} "
                 f"(max of {[i['id'] for i in items]})")
    return {}


# ══════════════════════════════════════════════════════
# 处理器注册表
# ══════════════════════════════════════════════════════

# 需要 WebSocket 的 special
WS_SPECIALS = {"websocket_open_table"}

# 三阶段处理：pre(请求前查询) → settle(合并额外参数) → post(请求后)
HANDLER_PRE = {
    "add_goods_extract":     pre_add_goods_extract,
    "goods_refund_param":    pre_goods_refund_param,
    "settlement_param":      pre_settlement_param,
    "set_settlement_param":  pre_set_settlement_param,
    "storing_query_extract": pre_storing_query_extract,
    "take_wine_param":       pre_take_wine_param,
    "reserve_param":         pre_reserve_param,
    "reserve_query_extract": pre_reserve_query_extract,
}

HANDLER_SETTLE = {
    "goods_refund_param":    settle_goods_refund_param,
    "settlement_param":      settle_settlement_param,
    "set_settlement_param":  settle_set_settlement_param,
    "reserve_param":         settle_reserve_param,
    "take_wine_param":       settle_take_wine_param,
}

HANDLER_POST = {
    "add_goods_extract":     post_add_goods_extract,
}
