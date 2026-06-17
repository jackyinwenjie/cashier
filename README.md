# 收银3.0收银台 - 自动化接口测试

## 项目简介

基于 **pytest + YAML 数据驱动 + Allure 报告** 的收银台（POS）自动化接口测试框架，支持自动验签和收银员登录。

## 与商家后台项目的区别

| 项目 | 登录类型 | API 域 |
|------|---------|--------|
| 收银3.0商家后台 | `type=shop` | api-v3.ytsaas.com |
| 收银3.0收银台 | `type=cashier` | api-v3.ytsaas.com |

## 项目结构

```
├── conftest.py          # 框架核心（验签、登录、Session 钩子、Allure 报告自动启动）
├── test_runner.py       # pytest 用例执行器（YAML 驱动：渲染 → 请求 → 断言 → Allure 注解）
├── test_data/           # YAML 用例数据（多文件模块化）
├── utils/               # 工具包（完整复用）
│   ├── analyse_case.py  # Jinja2 渲染 + 请求结构解析
│   ├── asserts.py       # HTTP 断言
│   ├── extractor.py     # 响应值提取
│   ├── handlers.py      # 特殊动作处理器（前置/结算/后置/WebSocket）
│   ├── reader.py        # YAML 多文件模块化加载
│   ├── send_request.py  # HTTP 请求发送
│   └── sign.py          # SHA1 自动验签
├── allure_config/       # Allure 配置
│   └── categories.json  # 中文失败分类
├── pytest.ini           # pytest 配置（自动 --alluredir + --clean-alluredir）
└── requirements.txt     # 依赖
```

## 运行测试

```bash
pip install -r requirements.txt

# 运行全部用例
pytest

# 运行指定模块
pytest -k "vip"

# 运行单条用例
pytest -k "case0"

# 收集用例（不执行）
pytest --collect-only -q
```

## Allure 报告

运行 `pytest` 后自动在 `http://192.168.6.197:18080/` 打开报告。

## 添加用例

在 `test_data/` 对应模块 YAML 文件中新增用例：

```yaml
- id: my_new_case
  title: '[模块-正向] 用例标题'
  method: POST                    # GET / POST
  path: /cashier/user/vip/recharge
  data:
    param1: 'value1'
    shop_id: '{{ SHOP_ID }}'      # 自动注入全局变量
  extract:
    order_id: data.id              # 提取响应值到上下文
  special: my_handler              # 可选：特殊处理器
  assert:
    code: 1
    msg: 成功
```

支持的全局变量：`{{ SHOP_ID }}` `{{ BOX_ID }}` `{{ VIP_ID }}` `{{ TODAY }}` `{{ TOMORROW }}` `{{ USER_PHONE }}` 等。

## Git 工作流

```
dev 分支开发 → main 分支合并 → 推送 main 到远程
```
