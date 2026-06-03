from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

from .llm import LLMClient


DISCLAIMER = "本文仅用于个人研究和持仓观察，不构成投资建议；基金有风险，申购需谨慎。"


def build_report_payload(settings_raw: Dict[str, Any], market_data: Dict[str, Any], news_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "user": settings_raw.get("user", {}),
        "funds_config": settings_raw.get("funds", []),
        "market_data": market_data,
        "news_results": news_results,
        "disclaimer": DISCLAIMER,
    }


def generate_report(payload: Dict[str, Any], llm: LLMClient) -> str:
    if not llm.available:
        return generate_template_report(payload)

    system = (
        "你是一个谨慎的个人基金投研日报助手。你的目标是帮助用户理解基金受哪些市场因素影响，"
        "不是预测涨跌，也不是给确定性买卖建议。\n"
        "硬性要求：\n"
        "1. 只能基于输入数据和检索摘要，不要编造事实。\n"
        "2. 明确区分：已发生事实、可能影响、个人操作观察。\n"
        "3. 输出必须是中文 Markdown。\n"
        "4. 操作建议只能使用：继续定投、暂停定投、观察、降低仓位、提高现金仓位、等待确认。\n"
        "5. 每只基金给出 风险等级/影响因素/今日动作建议/理由。\n"
        "6. 对没有来源或缺失数据的内容必须标注“不确定”。\n"
        "7. 不要说保证收益、必涨、必跌。"
    )
    user = (
        "请根据以下 JSON 生成一份个人基金日报。结构：\n"
        "# 今日基金观察日报\n"
        "## 1. 今日结论\n"
        "## 2. 市场与新闻要点\n"
        "## 3. 关注基金逐只分析\n"
        "## 4. 操作观察清单\n"
        "## 5. 明天/本周重点关注\n"
        "## 6. 数据缺口与风险提示\n\n"
        "JSON 输入如下：\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, default=str)[:45000]}\n```"
    )
    return llm.chat([{"role": "system", "content": system}, {"role": "user", "content": user}])


def generate_template_report(payload: Dict[str, Any]) -> str:
    md: List[str] = []
    md.append("# 今日基金观察日报\n")
    md.append(f"> {DISCLAIMER}\n")
    md.append("## 1. 今日结论\n")
    md.append("- 未配置 LLM_API_KEY，本报告为规则模板版。\n- 已完成基金/指数数据抓取与新闻检索占位；配置模型后可生成完整归因分析。\n")

    md.append("## 2. 指数概览\n")
    indices = payload.get("market_data", {}).get("indices", [])
    if not indices:
        md.append("- 暂无指数数据。\n")
    for i in indices:
        md.append(
            f"- **{i.get('name')}**：最新 {i.get('latest_close')}，1日 {fmt_pct(i.get('change_1d_pct'))}，"
            f"近观察期 {fmt_pct(i.get('change_lookback_pct'))}，来源：{i.get('source')}。\n"
        )

    md.append("\n## 3. 关注基金逐只分析\n")
    funds = payload.get("market_data", {}).get("funds", [])
    if not funds:
        md.append("- 暂无基金数据。\n")
    for f in funds:
        action = simple_action(f)
        md.append(f"### {f.get('name')}（{f.get('code')}）\n")
        md.append(f"- 类别：{f.get('category', '未填写')}\n")
        md.append(f"- 最新净值：{f.get('latest_nav')}；1日变化：{fmt_pct(f.get('change_1d_pct'))}；近观察期：{fmt_pct(f.get('change_lookback_pct'))}\n")
        md.append(f"- 数据源：{f.get('source')}\n")
        md.append(f"- 动作观察：**{action}**\n")
        if f.get("errors"):
            md.append(f"- 数据提示：{'; '.join(f.get('errors', []))}\n")
        md.append("\n")

    md.append("## 4. 新闻检索摘要\n")
    news = payload.get("news_results", [])
    for n in news:
        md.append(f"### 查询：{n.get('query')}\n")
        if n.get("error"):
            md.append(f"- 检索失败：{n.get('error')}\n")
        else:
            ans = n.get("answer", "")
            md.append(f"{ans[:1200] if ans else '- 无摘要。'}\n")
        cites = n.get("citations") or []
        if cites:
            md.append("来源：\n")
            for c in cites[:6]:
                md.append(f"- {c}\n")
        md.append("\n")

    md.append("## 5. 数据缺口与风险提示\n")
    md.append("- 开放式基金净值通常不是实时数据，日报应以净值公告和基金公司披露为准。\n")
    md.append("- 基金持仓一般按季度披露，不能代表当天真实持仓。\n")
    md.append("- 未配置搜索或 LLM 时，不应据此做申购/赎回决策。\n")
    return "".join(md)


def fmt_pct(x: Any) -> str:
    try:
        if x is None:
            return "未知"
        return f"{float(x):+.2f}%"
    except Exception:
        return "未知"


def simple_action(fund: Dict[str, Any]) -> str:
    c1 = fund.get("change_1d_pct")
    c30 = fund.get("change_lookback_pct")
    try:
        c1 = float(c1) if c1 is not None else 0.0
        c30 = float(c30) if c30 is not None else 0.0
    except Exception:
        return "观察"
    if c1 < -2.5 or c30 < -8:
        return "观察；不要情绪化补仓，等待连续数据确认"
    if c1 > 2.5 or c30 > 8:
        return "继续观察；不建议因单日上涨追高"
    return "按原计划继续定投/持有观察"
