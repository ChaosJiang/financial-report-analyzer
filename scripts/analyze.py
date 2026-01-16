#!/usr/bin/env python3
"""Generate normalized financial analysis from fetched data."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

import pandas as pd


ROW_MAP = {
    "revenue": ["Total Revenue", "Revenue", "营业总收入", "营业收入"],
    "net_income": [
        "Net Income",
        "Net Income Common Stockholders",
        "Net Income Applicable To Common Shares",
        "Diluted NI Availto Com Stockholders",
        "净利润",
    ],
    "gross_profit": ["Gross Profit", "毛利润", "营业毛利"],
    "operating_income": [
        "Operating Income",
        "Total Operating Income As Reported",
        "营业利润",
        "营业收益",
    ],
    "ebitda": ["EBITDA", "Normalized EBITDA"],
    "total_assets": ["Total Assets", "资产总计"],
    "total_liabilities": [
        "Total Liabilities",
        "Total Liabilities Net Minority Interest",
        "负债合计",
    ],
    "total_equity": [
        "Total Equity",
        "Total Stockholder Equity",
        "Stockholders Equity",
        "Total Equity Gross Minority Interest",
        "Common Stock Equity",
        "所有者权益合计",
    ],
    "free_cash_flow": ["Free Cash Flow", "自由现金流"],
    "diluted_avg_shares": ["Diluted Average Shares"],
    "basic_avg_shares": ["Basic Average Shares"],
    "shares_outstanding": ["Ordinary Shares Number", "Share Issued"],
    "total_debt": ["Total Debt"],
    "net_debt": ["Net Debt"],
    "cash": [
        "Cash And Cash Equivalents",
        "Cash Cash Equivalents And Short Term Investments",
        "Cash Financial",
    ],
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


def extract_row(df: pd.DataFrame, candidates: Iterable[str]) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=float)
    normalized_index = {normalize_label(idx): idx for idx in df.index}
    for candidate in candidates:
        key = normalize_label(candidate)
        if key in normalized_index:
            return df.loc[normalized_index[key]]
    return pd.Series(dtype=float)


def to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def sort_series(series: pd.Series) -> pd.Series:
    if series.empty:
        return pd.Series(dtype=float)
    index = pd.to_datetime(series.index, errors="coerce", utc=True)
    index = index.tz_localize(None)
    if index.notna().sum() >= 2:
        series = series.copy()
        series.index = index
        series = series.sort_index()
    return series


def series_to_dict(series: pd.Series) -> Dict[str, Any]:
    ordered = to_numeric(sort_series(series)).dropna()
    if ordered.empty:
        return {}
    return {
        str(idx.date() if hasattr(idx, "date") else idx): float(val)
        for idx, val in ordered.items()
    }


def compute_yoy(series: pd.Series) -> Dict[str, Any]:
    ordered = to_numeric(sort_series(series)).dropna()
    if ordered.empty:
        return {}
    yoy = ordered.pct_change().dropna()
    return {
        str(idx.date() if hasattr(idx, "date") else idx): float(val)
        for idx, val in yoy.items()
    }


def compute_cagr(series: pd.Series) -> Optional[float]:
    ordered = to_numeric(sort_series(series)).dropna()
    if len(ordered) < 2:
        return None
    start = float(ordered.iloc[0])
    end = float(ordered.iloc[-1])
    if start == 0:
        return None
    years = max(len(ordered) - 1, 1)
    return float((end / start) ** (1 / years) - 1)


def compute_ttm_sum(series: pd.Series) -> pd.Series:
    ordered = to_numeric(sort_series(series)).dropna()
    if len(ordered) < 4:
        return pd.Series(dtype=float)
    return ordered.rolling(window=4).sum().dropna()


def compute_per_share(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    numerator_series = to_numeric(sort_series(numerator)).dropna()
    denominator_series = to_numeric(sort_series(denominator)).dropna()
    if numerator_series.empty or denominator_series.empty:
        return pd.Series(dtype=float)
    aligned_num, aligned_den = numerator_series.align(denominator_series, join="inner")
    if aligned_num.empty or aligned_den.empty:
        return pd.Series(dtype=float)
    per_share = aligned_num / aligned_den
    per_share = per_share.replace([float("inf"), float("-inf")], pd.NA).dropna()
    return per_share


def compute_average_balance(series: pd.Series) -> pd.Series:
    ordered = to_numeric(sort_series(series)).dropna()
    if len(ordered) < 2:
        return pd.Series(dtype=float)
    return ordered.rolling(window=2).mean().dropna()


def compute_ttm_ratio(
    numerator_ttm: pd.Series, denominator_avg: pd.Series
) -> pd.Series:
    numerator = to_numeric(sort_series(numerator_ttm)).dropna()
    denominator = to_numeric(sort_series(denominator_avg)).dropna()
    if numerator.empty or denominator.empty:
        return pd.Series(dtype=float)
    aligned_num, aligned_den = numerator.align(denominator, join="inner")
    if aligned_num.empty or aligned_den.empty:
        return pd.Series(dtype=float)
    ratios = aligned_num / aligned_den
    ratios = ratios.replace([float("inf"), float("-inf")], pd.NA).dropna()
    return ratios


def extract_quarterly_metrics(
    income: pd.DataFrame, balance: pd.DataFrame, cashflow: pd.DataFrame
) -> Dict[str, pd.Series]:
    income = orient_statement(income)
    balance = orient_statement(balance)
    cashflow = orient_statement(cashflow)

    return {
        "revenue": extract_row(income, ROW_MAP["revenue"]),
        "net_income": extract_row(income, ROW_MAP["net_income"]),
        "gross_profit": extract_row(income, ROW_MAP["gross_profit"]),
        "operating_income": extract_row(income, ROW_MAP["operating_income"]),
        "ebitda": extract_row(income, ROW_MAP["ebitda"]),
        "diluted_avg_shares": extract_row(income, ROW_MAP["diluted_avg_shares"]),
        "basic_avg_shares": extract_row(income, ROW_MAP["basic_avg_shares"]),
        "total_assets": extract_row(balance, ROW_MAP["total_assets"]),
        "total_liabilities": extract_row(balance, ROW_MAP["total_liabilities"]),
        "total_equity": extract_row(balance, ROW_MAP["total_equity"]),
        "shares_outstanding": extract_row(balance, ROW_MAP["shares_outstanding"]),
        "total_debt": extract_row(balance, ROW_MAP["total_debt"]),
        "net_debt": extract_row(balance, ROW_MAP["net_debt"]),
        "cash": extract_row(balance, ROW_MAP["cash"]),
        "free_cash_flow": extract_row(cashflow, ROW_MAP["free_cash_flow"]),
    }


def extract_metrics(
    income: pd.DataFrame, balance: pd.DataFrame, cashflow: pd.DataFrame
) -> Dict[str, pd.Series]:
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
    metrics: Dict[str, pd.Series],
) -> Dict[str, Dict[str, Any]]:
    revenue = metrics["revenue"]
    net_income = metrics["net_income"]
    gross_profit = metrics["gross_profit"]
    total_assets = metrics["total_assets"]
    total_equity = metrics["total_equity"]
    total_liabilities = metrics["total_liabilities"]

    ratios = {
        "gross_margin": series_to_dict(gross_profit / revenue)
        if not gross_profit.empty and not revenue.empty
        else {},
        "net_margin": series_to_dict(net_income / revenue)
        if not net_income.empty and not revenue.empty
        else {},
        "roe": series_to_dict(net_income / total_equity)
        if not net_income.empty and not total_equity.empty
        else {},
        "roa": series_to_dict(net_income / total_assets)
        if not net_income.empty and not total_assets.empty
        else {},
        "debt_to_equity": series_to_dict(total_liabilities / total_equity)
        if not total_liabilities.empty and not total_equity.empty
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

    quarterly_income = df_from_dict(
        payload.get("financials_quarterly", {}).get("income_statement", {})
    )
    quarterly_balance = df_from_dict(
        payload.get("financials_quarterly", {}).get("balance_sheet", {})
    )
    quarterly_cashflow = df_from_dict(
        payload.get("financials_quarterly", {}).get("cashflow", {})
    )

    price_df = df_from_dict(payload.get("price_history", {}))

    metrics = extract_metrics(income, balance, cashflow)
    quarterly_metrics = extract_quarterly_metrics(
        quarterly_income, quarterly_balance, quarterly_cashflow
    )

    price_series = extract_price_series(price_df)

    revenue_q = quarterly_metrics["revenue"]
    net_income_q = quarterly_metrics["net_income"]
    ebitda_q = quarterly_metrics["ebitda"]
    free_cash_flow_q = quarterly_metrics["free_cash_flow"]
    diluted_avg_shares_q = quarterly_metrics["diluted_avg_shares"]

    eps_q = compute_per_share(net_income_q, diluted_avg_shares_q)
    eps_ttm = compute_ttm_sum(eps_q)

    sales_per_share_q = compute_per_share(revenue_q, diluted_avg_shares_q)
    sales_per_share_ttm = compute_ttm_sum(sales_per_share_q)

    ebitda_per_share_q = compute_per_share(ebitda_q, diluted_avg_shares_q)
    ebitda_per_share_ttm = compute_ttm_sum(ebitda_per_share_q)

    fcf_per_share_q = compute_per_share(free_cash_flow_q, diluted_avg_shares_q)
    fcf_per_share_ttm = compute_ttm_sum(fcf_per_share_q)

    revenue_ttm = compute_ttm_sum(revenue_q)
    net_income_ttm = compute_ttm_sum(net_income_q)
    ebitda_ttm = compute_ttm_sum(ebitda_q)
    free_cash_flow_ttm = compute_ttm_sum(free_cash_flow_q)

    total_equity_q = quarterly_metrics["total_equity"]
    total_assets_q = quarterly_metrics["total_assets"]
    net_debt_q = quarterly_metrics["net_debt"]
    total_debt_q = quarterly_metrics["total_debt"]
    cash_q = quarterly_metrics["cash"]
    shares_outstanding_q = quarterly_metrics["shares_outstanding"]

    book_per_share_q = compute_per_share(total_equity_q, shares_outstanding_q)
    net_debt_per_share_q = compute_per_share(net_debt_q, shares_outstanding_q)

    equity_avg_q = compute_average_balance(total_equity_q)
    assets_avg_q = compute_average_balance(total_assets_q)
    roe_ttm = compute_ttm_ratio(net_income_ttm, equity_avg_q)
    roa_ttm = compute_ttm_ratio(net_income_ttm, assets_avg_q)

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
        "financials_quarterly": {
            "revenue": series_to_dict(revenue_q),
            "net_income": series_to_dict(net_income_q),
            "ebitda": series_to_dict(ebitda_q),
            "free_cash_flow": series_to_dict(free_cash_flow_q),
            "diluted_avg_shares": series_to_dict(diluted_avg_shares_q),
        },
        "financials_ttm": {
            "revenue": series_to_dict(revenue_ttm),
            "net_income": series_to_dict(net_income_ttm),
            "ebitda": series_to_dict(ebitda_ttm),
            "free_cash_flow": series_to_dict(free_cash_flow_ttm),
        },
        "per_share_quarterly": {
            "eps": series_to_dict(eps_q),
            "sales": series_to_dict(sales_per_share_q),
            "ebitda": series_to_dict(ebitda_per_share_q),
            "free_cash_flow": series_to_dict(fcf_per_share_q),
        },
        "per_share_ttm": {
            "eps": series_to_dict(eps_ttm),
            "sales": series_to_dict(sales_per_share_ttm),
            "ebitda": series_to_dict(ebitda_per_share_ttm),
            "free_cash_flow": series_to_dict(fcf_per_share_ttm),
        },
        "balance_quarterly": {
            "total_equity": series_to_dict(total_equity_q),
            "shares_outstanding": series_to_dict(shares_outstanding_q),
            "book_per_share": series_to_dict(book_per_share_q),
            "net_debt": series_to_dict(net_debt_q),
            "total_debt": series_to_dict(total_debt_q),
            "cash": series_to_dict(cash_q),
            "net_debt_per_share": series_to_dict(net_debt_per_share_q),
        },
        "ratios": compute_ratios(metrics),
        "ratios_ttm": {
            "roe": series_to_dict(roe_ttm),
            "roa": series_to_dict(roa_ttm),
        },
        "growth": {
            "revenue_yoy": compute_yoy(metrics["revenue"]),
            "net_income_yoy": compute_yoy(metrics["net_income"]),
            "revenue_cagr": compute_cagr(metrics["revenue"]),
            "net_income_cagr": compute_cagr(metrics["net_income"]),
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
