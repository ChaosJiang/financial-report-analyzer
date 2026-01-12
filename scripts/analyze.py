#!/usr/bin/env python3
"""Generate normalized financial analysis from fetched data."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

import numpy as np
import pandas as pd


ROW_MAP = {
    "revenue": ["Total Revenue", "Revenue", "营业总收入", "营业收入"],
    "net_income": [
        "Net Income",
        "Net Income Common Stockholders",
        "Net Income Applicable To Common Shares",
        "净利润",
    ],
    "gross_profit": ["Gross Profit", "毛利润", "营业毛利"],
    "operating_income": ["Operating Income", "营业利润", "营业收益"],
    "ebitda": ["EBITDA"],
    "total_assets": ["Total Assets", "资产总计"],
    "total_liabilities": ["Total Liabilities", "负债合计"],
    "total_equity": ["Total Equity", "Total Stockholder Equity", "所有者权益合计"],
    "free_cash_flow": ["Free Cash Flow", "自由现金流"],
}


def normalize_label(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def df_from_dict(payload: Dict[str, Any]) -> pd.DataFrame:
    if not payload:
        return pd.DataFrame()
    df = pd.DataFrame(payload)
    df.index = [str(idx) for idx in df.index]
    return df


def orient_statement(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if "报告日期" in df.columns:
        df = df.set_index("报告日期").T
    return df


def extract_row(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[pd.Series]:
    if df.empty:
        return None
    normalized_index = {normalize_label(idx): idx for idx in df.index}
    for candidate in candidates:
        key = normalize_label(candidate)
        if key in normalized_index:
            return df.loc[normalized_index[key]]
    return None


def to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def sort_series(series: pd.Series) -> pd.Series:
    if series is None or series.empty:
        return series
    index = pd.to_datetime(series.index, errors="coerce", utc=True)
    index = index.tz_localize(None)
    if index.notna().sum() >= 2:
        series = series.copy()
        series.index = index
        series = series.sort_index()
    return series


def series_to_dict(series: Optional[pd.Series]) -> Dict[str, Any]:
    if series is None or series.empty:
        return {}
    series = sort_series(to_numeric(series)).dropna()
    return {
        str(idx.date() if hasattr(idx, "date") else idx): float(val)
        for idx, val in series.items()
    }


def compute_yoy(series: Optional[pd.Series]) -> Dict[str, Any]:
    if series is None or series.empty:
        return {}
    ordered = sort_series(to_numeric(series)).dropna()
    yoy = ordered.pct_change().dropna()
    return {
        str(idx.date() if hasattr(idx, "date") else idx): float(val)
        for idx, val in yoy.items()
    }


def compute_cagr(series: Optional[pd.Series]) -> Optional[float]:
    if series is None or series.empty:
        return None
    ordered = sort_series(to_numeric(series)).dropna()
    if len(ordered) < 2:
        return None
    start = ordered.iloc[0]
    end = ordered.iloc[-1]
    if start == 0:
        return None
    years = max(len(ordered) - 1, 1)
    return float((end / start) ** (1 / years) - 1)


def extract_metrics(
    income: pd.DataFrame, balance: pd.DataFrame, cashflow: pd.DataFrame
) -> Dict[str, Optional[pd.Series]]:
    income = orient_statement(income)
    balance = orient_statement(balance)
    cashflow = orient_statement(cashflow)

    return {
        "revenue": extract_row(income, ROW_MAP["revenue"]),
        "net_income": extract_row(income, ROW_MAP["net_income"]),
        "gross_profit": extract_row(income, ROW_MAP["gross_profit"]),
        "operating_income": extract_row(income, ROW_MAP["operating_income"]),
        "ebitda": extract_row(income, ROW_MAP["ebitda"]),
        "total_assets": extract_row(balance, ROW_MAP["total_assets"]),
        "total_liabilities": extract_row(balance, ROW_MAP["total_liabilities"]),
        "total_equity": extract_row(balance, ROW_MAP["total_equity"]),
        "free_cash_flow": extract_row(cashflow, ROW_MAP["free_cash_flow"]),
    }


def compute_ratios(
    metrics: Dict[str, Optional[pd.Series]],
) -> Dict[str, Dict[str, Any]]:
    revenue = metrics.get("revenue")
    net_income = metrics.get("net_income")
    gross_profit = metrics.get("gross_profit")
    total_assets = metrics.get("total_assets")
    total_equity = metrics.get("total_equity")
    total_liabilities = metrics.get("total_liabilities")

    ratios = {
        "gross_margin": series_to_dict(to_numeric(gross_profit) / to_numeric(revenue))
        if gross_profit is not None and revenue is not None
        else {},
        "net_margin": series_to_dict(to_numeric(net_income) / to_numeric(revenue))
        if net_income is not None and revenue is not None
        else {},
        "roe": series_to_dict(to_numeric(net_income) / to_numeric(total_equity))
        if net_income is not None and total_equity is not None
        else {},
        "roa": series_to_dict(to_numeric(net_income) / to_numeric(total_assets))
        if net_income is not None and total_assets is not None
        else {},
        "debt_to_equity": series_to_dict(
            to_numeric(total_liabilities) / to_numeric(total_equity)
        )
        if total_liabilities is not None and total_equity is not None
        else {},
    }
    return ratios


def extract_price_series(price_df: pd.DataFrame) -> pd.Series:
    if price_df.empty:
        return pd.Series(dtype=float)
    for candidate in ["Close", "Adj Close", "收盘", "close", "close_price"]:
        if candidate in price_df.columns:
            series = price_df[candidate]
            series.index = price_df.index
            return to_numeric(series)
    return pd.Series(dtype=float)


def build_analysis(payload: Dict[str, Any]) -> Dict[str, Any]:
    info = payload.get("info", {}) or {}
    income = df_from_dict(payload.get("financials", {}).get("income_statement", {}))
    balance = df_from_dict(payload.get("financials", {}).get("balance_sheet", {}))
    cashflow = df_from_dict(payload.get("financials", {}).get("cashflow", {}))
    price_df = df_from_dict(payload.get("price_history", {}))

    metrics = extract_metrics(income, balance, cashflow)
    price_series = extract_price_series(price_df)

    analysis = {
        "symbol": payload.get("symbol"),
        "market": payload.get("market"),
        "company": {
            "name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "currency": info.get("currency"),
        },
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "financials": {key: series_to_dict(value) for key, value in metrics.items()},
        "ratios": compute_ratios(metrics),
        "growth": {
            "revenue_yoy": compute_yoy(metrics.get("revenue")),
            "net_income_yoy": compute_yoy(metrics.get("net_income")),
            "revenue_cagr": compute_cagr(metrics.get("revenue")),
            "net_income_cagr": compute_cagr(metrics.get("net_income")),
        },
        "price": {
            "history": series_to_dict(price_series),
            "latest": float(price_series.dropna().iloc[-1])
            if not price_series.dropna().empty
            else None,
        },
    }

    return analysis


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze fetched financial data")
    parser.add_argument("--input", required=True, help="Path to data JSON")
    parser.add_argument("--output", default="./output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with open(args.input, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    analysis = build_analysis(payload)
    output_path = f"{args.output}/{analysis['symbol'].replace('.', '_')}_analysis.json"
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(analysis, handle, ensure_ascii=False, indent=2)

    print(f"Saved analysis to {output_path}")


if __name__ == "__main__":
    main()
