#!/usr/bin/env python3
"""Generate a markdown report from analysis outputs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

import pandas as pd


def series_from_dict(data: Dict[str, float]) -> pd.Series:
    if not data:
        return pd.Series(dtype=float)
    series = pd.Series(data)
    series.index = pd.to_datetime(series.index, errors="coerce", utc=True).tz_localize(
        None
    )
    series = pd.to_numeric(series, errors="coerce").dropna().sort_index()
    return series


def format_number(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        return f"{value:,.2f}"
    return str(value)


def format_percent(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        return f"{value * 100:.2f}%"
    return str(value)


def build_financial_table(analysis: Dict[str, Any]) -> str:
    revenue = series_from_dict(analysis.get("financials", {}).get("revenue", {}))
    net_income = series_from_dict(analysis.get("financials", {}).get("net_income", {}))
    gross_margin = series_from_dict(analysis.get("ratios", {}).get("gross_margin", {}))
    net_margin = series_from_dict(analysis.get("ratios", {}).get("net_margin", {}))
    roe = series_from_dict(analysis.get("ratios", {}).get("roe", {}))
    free_cash_flow = series_from_dict(
        analysis.get("financials", {}).get("free_cash_flow", {})
    )

    base_series = revenue if not revenue.empty else net_income
    if base_series.empty:
        return "数据不足，无法生成财务对比表。"

    dates = list(base_series.index[-5:])
    headers = [date.strftime("%Y-%m-%d") for date in dates]

    rows = [
        ("Revenue", revenue),
        ("Net Income", net_income),
        ("Gross Margin", gross_margin),
        ("Net Margin", net_margin),
        ("ROE", roe),
        ("Free Cash Flow", free_cash_flow),
    ]

    table = [
        "| 指标 | " + " | ".join(headers) + " |",
        "| --- | " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for label, series in rows:
        if series.empty:
            values = ["-"] * len(headers)
        else:
            values = []
            for date in dates:
                value = series.get(date)
                if label.endswith("Margin") or label in {"ROE"}:
                    values.append(format_percent(value) if value is not None else "-")
                else:
                    values.append(format_number(value) if value is not None else "-")
        table.append("| " + label + " | " + " | ".join(values) + " |")

    return "\n".join(table)


def build_valuation_table(valuation: Dict[str, Any]) -> str:
    metrics = valuation.get("metrics", {})
    percentiles = valuation.get("percentiles", {})

    rows = [
        ("P/E", metrics.get("pe"), percentiles.get("pe")),
        ("P/S", metrics.get("ps"), percentiles.get("ps")),
        ("P/B", metrics.get("pb"), percentiles.get("pb")),
        ("PEG", metrics.get("peg"), None),
        ("EV/EBITDA", metrics.get("ev_to_ebitda"), None),
    ]

    table = ["| 指标 | 当前值 | 5年分位 |", "| --- | --- | --- |"]
    for label, value, pct in rows:
        table.append(
            "| "
            + label
            + " | "
            + format_number(value)
            + " | "
            + (f"{pct:.2f}%" if pct is not None else "-")
            + " |"
        )
    return "\n".join(table)


def build_analyst_section(analyst: Dict[str, Any]) -> str:
    rating = analyst.get("rating", {})
    targets = analyst.get("price_targets", {})

    distribution = rating.get("recent_distribution", {})
    distribution_text = ", ".join(
        [f"{key}: {value}" for key, value in distribution.items()]
    )

    lines = [
        f"- 评级关键词: {rating.get('recommendation_key', '-')}",
        f"- 平均评级: {rating.get('recommendation_mean', '-')}",
        f"- 近 90 天评级分布: {distribution_text or '-'}",
        f"- 目标价区间: {format_number(targets.get('low'))} ~ {format_number(targets.get('high'))}",
        f"- 目标价均值: {format_number(targets.get('mean'))}",
    ]
    return "\n".join(lines)


def build_report(
    analysis: Dict[str, Any], valuation: Dict[str, Any], analyst: Dict[str, Any]
) -> str:
    company = analysis.get("company", {})
    symbol = analysis.get("symbol")

    report_lines = [
        f"# 财报分析报告 - {company.get('name') or symbol}",
        "",
        f"生成时间: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}",
        "",
        "## 一、公司概况",
        f"- 公司名称: {company.get('name') or '-'}",
        f"- 行业: {company.get('industry') or '-'}",
        f"- 领域: {company.get('sector') or '-'}",
        "",
        "## 二、业务模式分析",
        "- （此部分由 AI 根据财报与公开信息生成）",
        "",
        "## 三、竞争格局",
        "- （此部分由 AI 根据行业信息生成）",
        "",
        "## 四、财务分析",
        build_financial_table(analysis),
        "",
        "## 五、估值分析",
        build_valuation_table(valuation),
        "",
        "## 六、分析师预期",
        build_analyst_section(analyst),
        "",
        "## 七、图表",
        "- revenue_net_income.png",
        "- margin_trends.png",
        "- roe_roa.png",
        "- debt_to_equity.png",
        "- price_history.png",
        "",
        "## 八、投资建议",
        "- （基于基本面优先的综合建议，由 AI 生成）",
    ]

    return "\n".join(report_lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate report from analysis outputs"
    )
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--valuation", required=False)
    parser.add_argument("--analyst", required=False)
    parser.add_argument("--output", default="./output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with open(args.analysis, "r", encoding="utf-8") as handle:
        analysis = json.load(handle)

    valuation = {}
    if args.valuation:
        with open(args.valuation, "r", encoding="utf-8") as handle:
            valuation = json.load(handle)

    analyst = {}
    if args.analyst:
        with open(args.analyst, "r", encoding="utf-8") as handle:
            analyst = json.load(handle)

    report = build_report(analysis, valuation, analyst)
    output_path = f"{args.output}/{analysis['symbol'].replace('.', '_')}_report.md"
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(report)

    print(f"Saved report to {output_path}")


if __name__ == "__main__":
    main()
