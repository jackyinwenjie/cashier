# 收银3.0收银台 - 自动化接口测试

## 项目简介

基于 pytest + requests 的收银台（POS）自动化接口测试框架，支持自动验签和收银员登录。

## 与商家后台项目的区别

| 项目 | 登录类型 | API 域 |
|------|---------|--------|
| 收银3.0商家后台 | `type=shop` | api-v3.ytsaas.com |
| 收银3.0收银台 | `type=cashier` | api-v3.ytsaas.com |

## 项目结构

```
├── conftest.py      # 框架核心（自动验签、收银员登录）
├── test_api.py      # 接口测试用例
├── pytest.ini       # pytest 配置
├── requirements.txt # 依赖
└── README.md        # 项目说明
```

## 运行测试

```bash
pip install -r requirements.txt
pytest test_api.py -v
```

## 添加用例

在 `test_api.py` 中编写测试函数：

```python
def test_example(api):
    """用例描述"""
    resp = api.get("/path/to/api", param1="value1")
    data = resp.json()
    assert data.get("code") == 1
```

框架自动处理验签（sign + time）和 token 注入。
