"""HTML 测试报告生成器"""
import json
import os
from datetime import datetime

from .result_collector import ResultCollector, TestResult


# ── CSS 样式（内联，无外部依赖）──
_CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background: #f5f7fa; color: #333; padding: 24px; }
.container { max-width: 1200px; margin: 0 auto; }
.header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #fff; padding: 32px; border-radius: 12px; margin-bottom: 24px; }
.header h1 { font-size: 26px; margin-bottom: 8px; }
.header .time { opacity: 0.85; font-size: 14px; }
.summary { display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
.card { background: #fff; border-radius: 10px; padding: 20px 28px; flex: 1; min-width: 140px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); text-align: center; }
.card .num { font-size: 36px; font-weight: 700; }
.card .label { font-size: 14px; color: #888; margin-top: 4px; }
.card.total .num { color: #409eff; }
.card.pass .num { color: #67c23a; }
.card.fail .num { color: #f56c6c; }
.card.rate .num { color: #e6a23c; font-size: 28px; }
table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
th { background: #f0f2f5; padding: 12px 14px; text-align: left; font-size: 13px; font-weight: 600; color: #666; border-bottom: 2px solid #e4e7ed; }
td { padding: 10px 14px; font-size: 13px; border-bottom: 1px solid #ebeef5; }
tr:hover { background: #f5f7fa; }
.status { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.status.pass { background: #f0f9eb; color: #67c23a; }
.status.fail { background: #fef0f0; color: #f56c6c; }
.time-cell { color: #909399; font-size: 12px; }
.detail-row { display: none; }
.detail-row.show { display: table-row; }
.detail-row td { background: #fafafa; padding: 16px 24px; }
.detail-box { background: #fff; border: 1px solid #e4e7ed; border-radius: 8px; padding: 16px; }
.detail-box h4 { font-size: 14px; margin-bottom: 10px; color: #333; }
.detail-box pre { background: #2d2d2d; color: #abb2bf; padding: 14px; border-radius: 6px; font-size: 12px; overflow-x: auto; max-height: 400px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; }
.toggle-btn { cursor: pointer; font-size: 12px; color: #409eff; background: none; border: none; padding: 2px 8px; }
.toggle-btn:hover { text-decoration: underline; }
.error-msg { color: #f56c6c; font-size: 12px; max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.feature-tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; background: #ecf5ff; color: #409eff; margin-right: 4px; }
.footer { text-align: center; padding: 24px; color: #999; font-size: 12px; }
.clickable { cursor: pointer; color: #409eff; }
.no-data { text-align: center; padding: 60px; color: #999; }
"""

_JS = """
function toggleDetail(rowId) {
    var row = document.getElementById(rowId);
    var btn = document.getElementById('btn-' + rowId);
    if (row.classList.contains('show')) {
        row.classList.remove('show');
        btn.textContent = '展开';
    } else {
        row.classList.add('show');
        btn.textContent = '收起';
    }
}
"""


def _format_json(obj) -> str:
    """格式化 JSON，失败则返回原始字符串"""
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return str(obj)


def generate_html(output_path: str = None) -> str:
    """
    生成 HTML 报告文件。
    返回生成的文件路径。
    """
    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "test_report.html",
        )

    results = ResultCollector.get_results()
    summary = ResultCollector.get_summary()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── 表格行 ──
    rows = []
    for i, r in enumerate(results):
        status_cls = "pass" if r.status == "PASS" else "fail"
        duration_str = f"{r.duration:.2f}s" if r.duration > 0 else "-"

        if r.status == "FAIL":
            error_display = r.error_msg[:80] + "..." if len(r.error_msg) > 80 else r.error_msg
            detail_id = f"detail-{i}"
            req_json = _format_json(r.request_body) if r.request_body else "（无）"
            resp_json = _format_json(r.response_body) if r.response_body else "（无）"

            rows.append(f"""
            <tr>
                <td>{i + 1}</td>
                <td><span class="feature-tag">{r.feature or '-'}</span></td>
                <td>{r.title or r.case_id}</td>
                <td><span class="status {status_cls}">{r.status}</span></td>
                <td class="time-cell">{duration_str}</td>
                <td>
                    <span class="error-msg" title="{r.error_msg}">{error_display}</span>
                    <button class="toggle-btn" id="btn-{detail_id}" onclick="toggleDetail('{detail_id}')">展开</button>
                </td>
            </tr>
            <tr class="detail-row" id="{detail_id}">
                <td colspan="6">
                    <div class="detail-box">
                        <h4>📤 请求 — {r.method} {r.path}</h4>
                        <pre>{req_json}</pre>
                        <h4 style="margin-top:14px;">📥 响应</h4>
                        <pre>{resp_json}</pre>
                    </div>
                </td>
            </tr>""")
        else:
            rows.append(f"""
            <tr>
                <td>{i + 1}</td>
                <td><span class="feature-tag">{r.feature or '-'}</span></td>
                <td>{r.title or r.case_id}</td>
                <td><span class="status {status_cls}">{r.status}</span></td>
                <td class="time-cell">{duration_str}</td>
                <td>-</td>
            </tr>""")

    table_body = "\n".join(rows)

    # ── 汇总卡片 ──
    total = summary["total"]
    passed = summary["passed"]
    failed = summary["failed"]
    pass_rate = summary["pass_rate"]

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>收银3.0收银台 — 测试报告</title>
<style>{_CSS}</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>收银3.0收银台 自动化测试报告</h1>
        <div class="time">生成时间：{now}　|　总耗时：{summary['duration']}s</div>
    </div>

    <div class="summary">
        <div class="card total">
            <div class="num">{total}</div>
            <div class="label">用例总数</div>
        </div>
        <div class="card pass">
            <div class="num">{passed}</div>
            <div class="label">通过</div>
        </div>
        <div class="card fail">
            <div class="num">{failed}</div>
            <div class="label">失败</div>
        </div>
        <div class="card rate">
            <div class="num">{pass_rate}</div>
            <div class="label">通过率</div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th style="width:50px">#</th>
                <th style="width:100px">模块</th>
                <th>用例标题</th>
                <th style="width:70px">结果</th>
                <th style="width:80px">耗时</th>
                <th style="width:300px">详情</th>
            </tr>
        </thead>
        <tbody>
            {table_body}
        </tbody>
    </table>

    <div class="footer">收银3.0收银台 · AutoTest Framework</div>
</div>
<script>{_JS}</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path
