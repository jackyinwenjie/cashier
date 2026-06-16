"""
收银3.0收银台 - 接口测试用例
基于 pytest 框架，自动验签 + 收银员 token（type=cashier）
"""
import json
import time
from datetime import datetime, timedelta

import pytest

from conftest import BASE_URL, signed_body
from utils.handlers import handle_websocket_open_table


# ══════════════════════════════════════════════════════════════
# 一、登录验证
# ══════════════════════════════════════════════════════════════

def test_login_success(api):
    """[登录-正向] 收银员登录 → 获取 token，验证 fixture 可用"""
    assert api is not None





# ══════════════════════════════════════════════════════════════
# 二、用户/店铺数据
# ══════════════════════════════════════════════════════════════

def test_userdata(api):
    """[用户-正向] 获取当前收银员信息 → code=1，含 userdata 字段"""
    resp = api.get("/shop/userdata", shop_id=SHOP_ID)
    data = resp.json()
    print(f"\n[用户数据] {json.dumps(data, ensure_ascii=False)}")
    assert data.get("code") == 1, f"期望 code=1, 实际 code={data.get('code')}"
    d = data.get("data", {})
    assert "id" in d, "返回数据应包含 id"
    assert "name" in d, "返回数据应包含 name"
    assert "account" in d, "返回数据应包含 account"
    # 收银员特有字段
    assert "cashier_version" in d, "收银员数据应包含 cashier_version"


def test_shop_datalist(api):
    """[店铺-正向] 获取店铺数据列表 → code=1"""
    resp = api.get("/shop/shop/datalist", shop_id="3226")
    data = resp.json()
    print(f"\n[店铺列表] code={data.get('code')}, msg={data.get('msg')}")
    assert data.get("code") == 1, f"期望 code=1, 实际 code={data.get('code')}"


# ══════════════════════════════════════════════════════════════
# 三、收银流程（开台 → 点单 → 退品 → 赠送 → 付款 → 结账 → 关房）
# 用例按顺序执行，动态传递上游返回的订单 ID 等参数
# ══════════════════════════════════════════════════════════════

BOX_ID = "64291"
SHOP_ID = "3226"
STORING_BOX_ID = "64399"     # 寄存用的包厢（不同于收银包厢）
RESERVE_BOX_ID = "64398"     # 预订用的包厢


@pytest.fixture(scope="class")
def ensure_box_closed(client):
    """流程前后确保包厢空闲，避免"包厢正在使用中"导致开台失败"""
    client.post("/cashier/order/editboxstatus",
        box_status="50", box_id=BOX_ID, shop_id=SHOP_ID)
    yield
    client.post("/cashier/order/editboxstatus",
        box_status="50", box_id=BOX_ID, shop_id=SHOP_ID)


class TestCashierFlow:
    """收银完整业务流程"""

    # 类变量，跨测试实例共享（pytest 每个方法创建新实例）
    order_id = None           # 来自 WebSocket 推送
    goods_orders_id = None     # 点单批次 ID
    first_line_id = None       # 第一个商品行 ID（用于退品）
    goods_money = None         # 当前商品行金额（动态查询）

    def test_01_open_table(self, api, ws_token, ensure_box_closed):
        """[开台-正向] 正常开台 → 通过 WebSocket 获取真实 order_id"""

        # 构造 all_dict 供 handler 使用
        context = {
            "ws_token": ws_token,
            "SHOP_ID": SHOP_ID,
            "order_id": None,
        }

        # 复用 handlers 模块的 WebSocket 开台处理器
        ws_close = handle_websocket_open_table(api, {}, context)

        # 开台
        resp = api.post("/cashier/order/store",
            box_id=BOX_ID,
            billing_type="20",
            goods_pricing_schemes_id="7",
            box_pricing_schemes_id="21",
            purchase_time="480",
            shop_user_sales_id="",
            shop_user_waiter_id="",
            user_vip_id="",
            sales_name="",
            shop_id=SHOP_ID,
        )
        data = resp.json()
        print(f"\n[开台-正向] {json.dumps(data, ensure_ascii=False)}")
        assert data.get("code") == 1, f"期望 code=1, 实际 code={data.get('code')}"
        assert data.get("msg") == "成功"

        # 等待 WebSocket 推送 order_id
        ws_close()

        assert context.get("order_id") is not None, "WebSocket 未推送 order_id"
        TestCashierFlow.order_id = context["order_id"]
        print(f"  → 最终 order_id={TestCashierFlow.order_id}")

    def test_02_add_goods(self, api):
        """[点单-正向] 点单下单 → code=1，查询各行 ID 和金额"""
        goods_array = [
            {"goods_id": 15, "goods_name": "国宾啤酒", "num": 2, "unit_name": "瓶", "unit_id": 38, "type": 1},
            {"goods_id": 16, "goods_name": "可乐", "num": 2, "unit_name": "听", "unit_id": 47, "type": 1},
        ]
        resp = api.post("/cashier/goodsorders/store",
            box_id=BOX_ID,
            shop_user_sales_id="",
            goods_array=goods_array,
            desc="",
            shop_id=SHOP_ID,
        )
        data = resp.json()
        print(f"\n[点单-正向] {json.dumps(data, ensure_ascii=False)}")
        assert data.get("code") == 1, f"期望 code=1, 实际 code={data.get('code')}"
        assert data.get("msg") == "成功"
        TestCashierFlow.goods_orders_id = data["data"]
        print(f"  → 批次 goods_orders_id={TestCashierFlow.goods_orders_id}")

        # 查询 goodsorders/index 获取各行 ID 和金额
        idx_resp = api.get("/cashier/goodsorders/index",
            order_id=TestCashierFlow.order_id,
            shop_id=SHOP_ID,
        )
        idx_data = idx_resp.json()
        goods_items = idx_data.get("data", {}).get("goods_data", [])
        assert len(goods_items) > 0, "goodsorders/index 未返回商品行"
        TestCashierFlow.first_line_id = goods_items[0]["id"]
        TestCashierFlow.goods_money = float(goods_items[0]["money"])
        print(f"  → 第一行 id={TestCashierFlow.first_line_id}, money={TestCashierFlow.goods_money}")
        for item in goods_items:
            print(f"    行 id={item['id']} name={item['goods_name']} num={item['num']} money={item['money']}")

    def test_03_goods_refund(self, api):
        """[退品-正向] 退品操作 → code=1（使用商品行 ID 而非批次 ID）"""
        goods_orders = [
            {"goods_orders_id": TestCashierFlow.first_line_id, "num": 1},
        ]
        resp = api.post("/cashier/order/goods_refund_save",
            order_id=TestCashierFlow.order_id,
            goods_orders=goods_orders,
            shop_id=SHOP_ID,
        )
        data = resp.json()
        print(f"\n[退品-正向] {json.dumps(data, ensure_ascii=False)}")
        assert data.get("code") == 1, f"期望 code=1, 实际 code={data.get('code')}"
        assert data.get("msg") == "成功"

    def test_04_give_order(self, api):
        """[赠送-正向] 赠送商品 → code=1"""
        goods_array = [
            {"goods_id": 15, "goods_name": "国宾啤酒", "num": 1, "unit_name": "瓶", "unit_id": 38, "type": 1},
        ]
        resp = api.post("/cashier/goodsorders/store",
            box_id=BOX_ID,
            give_id="21053",
            goods_array=goods_array,
            send_remark="",
            shop_id=SHOP_ID,
        )
        data = resp.json()
        print(f"\n[赠送-正向] {json.dumps(data, ensure_ascii=False)}")
        assert data.get("code") == 1, f"期望 code=1, 实际 code={data.get('code')}"
        assert data.get("msg") == "成功"

    def test_05_good_settlement(self, api):
        """[付款-正向] 单品结算 → code=1（动态金额，单行ID，跳过赠送行 state!=1）"""
        # 重新查询当前商品行，过滤 state=1 的未付款行，且排除赠送行（money=0）
        idx_resp = api.get("/cashier/goodsorders/index",
            order_id=TestCashierFlow.order_id,
            shop_id=SHOP_ID,
        )
        idx_data = idx_resp.json()
        goods_items = idx_data.get("data", {}).get("goods_data", [])
        # 选一个未付款且金额>0的行
        candidate = None
        for item in goods_items:
            if item.get("state") == 1 and float(item.get("receivable_money", 0)) > 0:
                candidate = item
                break
        debug_items = [(i["id"], i["money"], i.get("state")) for i in goods_items]
        assert candidate is not None, f"无可用结算行（items id/money/state={debug_items}）"
        line_id = candidate["id"]
        line_money = float(candidate["receivable_money"])
        print(f"  → 结算行 id={line_id} receivable_money={line_money}")
        payment_method = [
            {"id": 37, "money": line_money, "type": 1},
        ]
        resp = api.post("/cashier/orderpayments/goodSettlement",
            box_id=BOX_ID,
            type="0",
            payment_method=payment_method,
            goods=[line_id],
            payRemark="",
            shop_id=SHOP_ID,
        )
        data = resp.json()
        print(f"\n[付款-正向] {json.dumps(data, ensure_ascii=False)}")
        assert data.get("code") == 1, f"期望 code=1, 实际 code={data.get('code')}"
        assert data.get("msg") == "成功"

    def test_06_set_settlement(self, api):
        """[结账-正向] 整体结账 → code=1（仅统计 state=1 未付款行）"""
        # 查询当前未付款商品行（赠送行 state!=1 会被自动排除）
        idx_resp = api.get("/cashier/goodsorders/index",
            order_id=TestCashierFlow.order_id,
            shop_id=SHOP_ID,
        )
        idx_data = idx_resp.json()
        goods_items = idx_data.get("data", {}).get("goods_data", [])
        # 只统计 state=1（未支付）且金额>0 的行（赠送行 money=0）
        current_total = int(sum(
            float(item["receivable_money"]) for item in goods_items
            if item.get("state") == 1 and float(item.get("money", 0)) > 0
        ))
        print(f"  → 未付款应收总金额={current_total}")
        payment_method = [
            {"id": 37, "money": current_total, "type": 1},
        ]
        resp = api.post("/cashier/orderpayments/setsettlement",
            box_id=BOX_ID,
            type="1",
            payment_method=payment_method,
            payRemark="",
            shop_id=SHOP_ID,
        )
        data = resp.json()
        print(f"\n[结账-正向] {json.dumps(data, ensure_ascii=False)}")
        assert data.get("code") == 1, f"期望 code=1, 实际 code={data.get('code')}"
        assert data.get("msg") == "成功"

    def test_07_close_box(self, api):
        """[关房-正向] 关房操作 → code=1"""
        resp = api.post("/cashier/order/editboxstatus",
            box_status="50",
            box_id=BOX_ID,
            shop_id=SHOP_ID,
        )
        data = resp.json()
        print(f"\n[关房-正向] {json.dumps(data, ensure_ascii=False)}")
        assert data.get("code") == 1, f"期望 code=1, 实际 code={data.get('code')}"
        assert data.get("msg") == "成功"


# ══════════════════════════════════════════════════════════════
# 四、寄存-支取流程
# ══════════════════════════════════════════════════════════════

class TestStoringWineFlow:
    """寄存 → 查询详情 → 支取"""

    storing_wine_id = None       # 寄存 ID（寄存后获得）
    deposit_goods_id = None      # 寄存商品明细 ID（查询后获得）
    deposit_goods_data = None    # 寄存商品信息（寄存响应中提取）

    def test_01_store_wine(self, api):
        """[寄存-正向] 寄存酒水 → code=1，获取 storing_wine_id"""
        resp = api.post("/cashier/storingwines/store",
            user_type="1",
            name="自动化",
            phone="18222222222",
            day="30",
            remark="",
            shop_user_id="",
            client_user_id="",
            box_id=STORING_BOX_ID,
            goods_array=[
                {"goods_id": "16", "num": "2", "unit_id": "1", "unit_num": "0"},
            ],
            shop_id=SHOP_ID,
        )
        data = resp.json()
        print(f"\n[寄存-正向] {json.dumps(data, ensure_ascii=False)}")
        assert data.get("code") == 1, f"期望 code=1, 实际 code={data.get('code')}"
        # 注意：msg 可能是 "当前操作成功，短信发送失败..." 而非纯 "成功"
        assert data.get("data") is not None, "寄存未返回 data"

        deposit = data["data"]
        TestStoringWineFlow.storing_wine_id = deposit["storing_wine_id"]
        TestStoringWineFlow.deposit_goods_data = deposit.get("deposit", [])
        print(f"  → storing_wine_id={TestStoringWineFlow.storing_wine_id}")

    def test_02_query_store_detail(self, api):
        """[查询寄存-正向] 查询寄存索引获取商品明细 ID，供支取使用"""
        resp = api.get("/cashier/storingwines/index",
            storing_wines_id=TestStoringWineFlow.storing_wine_id,
            shop_id=SHOP_ID,
        )
        data = resp.json()
        print(f"\n[查询寄存-正向] code={data.get('code')}")
        assert data.get("code") == 1, f"期望 code=1, 实际 code={data.get('code')}"

        # data.data 是列表，每项的 children 包含商品明细
        list_data = data.get("data", {})
        items = list_data.get("data", []) if isinstance(list_data, dict) else []
        if items and len(items) > 0:
            children = items[0].get("children", [])
            if children and len(children) > 0:
                TestStoringWineFlow.deposit_goods_id = children[0]["id"]
                print(f"  → 从 children[0] 提取 deposit_goods_id={TestStoringWineFlow.deposit_goods_id}")

        # 兜底：从寄存响应 deposit 字段中提取
        if TestStoringWineFlow.deposit_goods_id is None:
            dlist = TestStoringWineFlow.deposit_goods_data
            if dlist and len(dlist) > 0:
                TestStoringWineFlow.deposit_goods_id = dlist[0].get("id")
                print(f"  → 兜底提取 deposit_goods_id={TestStoringWineFlow.deposit_goods_id}")

        assert TestStoringWineFlow.deposit_goods_id is not None, "未找到寄存商品明细 ID"

    def test_03_take_wine(self, api):
        """[支取-正向] 支取酒水 → code=1（动态传参）"""
        deposit_goods = TestStoringWineFlow.deposit_goods_data[0] if TestStoringWineFlow.deposit_goods_data else {}
        goods_id = str(deposit_goods.get("goods_id", "16"))
        goods_num = str(deposit_goods.get("num", "2"))

        goods_array = [{
            "goods_id": goods_id,
            "id": TestStoringWineFlow.deposit_goods_id,
            "num": goods_num,
            "storing_wines_id": TestStoringWineFlow.storing_wine_id,
        }]
        resp = api.post("/cashier/storingwines/takewine",
            storing_wines_id=TestStoringWineFlow.storing_wine_id,
            box_id=BOX_ID,
            wine_shop_id=SHOP_ID,
            goods_array=goods_array,
            takeWineBatch="1",
            remark="",
            is_custom="2",
            shop_id=SHOP_ID,
        )
        data = resp.json()
        print(f"\n[支取-正向] {json.dumps(data, ensure_ascii=False)}")
        assert data.get("code") == 1, f"期望 code=1, 实际 code={data.get('code')}"


# ══════════════════════════════════════════════════════════════
# 五、预订-取消预订流程
# ══════════════════════════════════════════════════════════════

class TestReserveFlow:
    """预订 → 查询 → 取消预订"""

    reserve_id = None           # 预订 ID（store 返回 data=[]，需通过 index 查询获取）

    def test_01_reserve(self, api):
        """[预订-正向] 预订包厢 → code=1"""
        eta_time = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        resp = api.post("/cashier/reserve/store",
            box_id=RESERVE_BOX_ID,
            name="自动化预订",
            phone="18222222222",
            shop_user_id="21053",
            sales_name="自动化测试",
            eta_time=eta_time,
            sex="1",
            remark="",
            type="1",
            vod_theme_id="",
            shop_id=SHOP_ID,
        )
        data = resp.json()
        print(f"\n[预订-正向] eta_time={eta_time} {json.dumps(data, ensure_ascii=False)}")
        assert data.get("code") == 1, f"期望 code=1, 实际 code={data.get('code')}"
        assert data.get("msg") == "成功"

    def test_02_query_reserve(self, api):
        """[查询预订-正向] 查询预订列表获取本次创建的预订 ID"""
        resp = api.get("/cashier/reserve/index",
            shop_id=SHOP_ID,
        )
        data = resp.json()
        print(f"\n[查询预订-正向] code={data.get('code')}")
        assert data.get("code") == 1, f"期望 code=1, 实际 code={data.get('code')}"

        list_data = data.get("data", {})
        items = list_data.get("data", []) if isinstance(list_data, dict) else list_data
        assert items and len(items) > 0, f"预订列表为空（data={json.dumps(data, ensure_ascii=False)[:200]}）"
        # store 不返回 ID，取列表中最大 ID（最新创建的）
        TestReserveFlow.reserve_id = max(item["id"] for item in items)
        assert TestReserveFlow.reserve_id is not None, "未找到预订 ID"
        print(f"  → reserve_id={TestReserveFlow.reserve_id}（max of {[i['id'] for i in items]}）")

    def test_03_cancel_reserve(self, api):
        """[取消预订-正向] 取消预订 → code=1（动态传参）"""
        resp = api.post("/cashier/reserve/del",
            id=TestReserveFlow.reserve_id,
            shop_id=SHOP_ID,
        )
        data = resp.json()
        print(f"\n[取消预订-正向] {json.dumps(data, ensure_ascii=False)}")
        assert data.get("code") == 1, f"期望 code=1, 实际 code={data.get('code')}"
        assert data.get("msg") == "成功"


# ══════════════════════════════════════════════════════════════
# 六、会员充值-扣款流程
# ══════════════════════════════════════════════════════════════

class TestVipFlow:
    """会员充值 → 会员扣款"""

    VIP_ID = "4"
    PAY_WAYS = [
        {"id": "37", "money": "1000", "type": "3", "type_pay": "2"},
    ]

    def test_01_recharge(self, api):
        """[充值-正向] 会员充值 → code=1"""
        resp = api.post("/cashier/user/vip/recharge",
            money="1000",
            id=TestVipFlow.VIP_ID,
            type="1",
            gift="1000",
            pay_ways=TestVipFlow.PAY_WAYS,
            php_shop_user_id="",
            shop_id=SHOP_ID,
        )
        data = resp.json()
        print(f"\n[充值-正向] {json.dumps(data, ensure_ascii=False)}")
        assert data.get("code") == 1, f"期望 code=1, 实际 code={data.get('code')}"

    def test_02_deduction(self, api):
        """[扣款-正向] 会员扣款 → code=1"""
        resp = api.post("/cashier/user/vip/deduction",
            money="1000",
            gift="1000",
            remark="自动化扣款",
            id=TestVipFlow.VIP_ID,
            pay_ways=TestVipFlow.PAY_WAYS,
            shop_id=SHOP_ID,
        )
        data = resp.json()
        print(f"\n[扣款-正向] {json.dumps(data, ensure_ascii=False)}")
        assert data.get("code") == 1, f"期望 code=1, 实际 code={data.get('code')}"
        assert data.get("msg") == "成功"

