#!/usr/bin/env python3
"""Compute valuation metrics and historical percentiles."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


def to_series(data: Dict[str, Any]) -> pd.Series:
    if not data:
        return pd.Series(dtype=float)
    series = pd.Series(data)
    series.index = pd.to_datetime(series.index, errors="coerce", utc=True).tz_localize(
        None
    )
    series = pd.to_numeric(series, errors="coerce")
    series = series.dropna().sort_index()
    return series


def to_price_series(payload: Dict[str, Any]) -> pd.Series:
    price_df = pd.DataFrame(payload.get("price_history", {}))
    if price_df.empty:
        return pd.Series(dtype=float)
    price_df.index = pd.to_datetime(
        price_df.index, errors="coerce", utc=True
    ).tz_localize(None)
    for key in ["Close", "Adj Close", "收盘", "close"]:
        if key in price_df.columns:
            series = pd.to_numeric(price_df[key], errors="coerce")
            return series.dropna()
    return pd.Series(dtype=float)


def nearest_price(price_series: pd.Series, date: pd.Timestamp) -> Optional[float]:
    if price_series.empty:
        return None
    subset = price_series[price_series.index <= date]
    if subset.empty:
        return None
    return float(subset.iloc[-1])


def compute_ratio_history(
    numerator_series: pd.Series,
    denominator_series: pd.Series,
    price_series: pd.Series,
    shares_outstanding: Optional[float],
) -> Dict[str, float]:
    if (
        numerator_series.empty
        or denominator_series.empty
        or price_series.empty
        or not shares_outstanding
    ):
        return {}
    history: Dict[str, float] = {}
    for date, value in denominator_series.items():
        if value == 0 or np.isnan(value):
            continue
        price = nearest_price(price_series, date)
        if price is None:
            continue
        market_cap = price * shares_outstanding
        ratio = market_cap / value
        history[str(date.date())] = float(ratio)
    return history


def percentile(current: Optional[float], history: Dict[str, float]) -> Optional[float]:
    if current is None or not history:
        return None
    values = [v for v in history.values() if v > 0]
    if not values:
        return None
    return float(sum(v <= current for v in values) / len(values) * 100)


def compute_dcf(
    free_cash_flow: Optional[float],
    shares_outstanding: Optional[float],
    discount_rate: float = 0.1,
    growth_rate: float = 0.05,
    terminal_growth: float = 0.02,
    years: int = 5,
) -> Dict[str, Any]:
    if free_cash_flow is None or free_cash_flow <= 0 or not shares_outstanding:
        return {}
    pv = 0.0
    for year in range(1, years + 1):
        pv += free_cash_flow * (1 + growth_rate) ** year / (1 + discount_rate) ** year
    terminal_value = (
        free_cash_flow
        * (1 + growth_rate) ** years
        * (1 + terminal_growth)
        / (discount_rate - terminal_growth)
    )
    pv_terminal = terminal_value / (1 + discount_rate) ** years
    equity_value = pv + pv_terminal
    per_share = equity_value / shares_outstanding
    return {
        "assumptions": {
            "discount_rate": discount_rate,
            "growth_rate": growth_rate,
            "terminal_growth": terminal_growth,
            "years": years,
        },
        "equity_value": float(equity_value),
        "per_share": float(per_share),
    }


def build_valuation(data: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    info = data.get("info", {}) or {}
    shares_outstanding = info.get("sharesOutstanding")
    market_cap = info.get("marketCap")
    current_price = analysis.get("price", {}).get("latest")

    net_income_series = to_series(analysis.get("financials", {}).get("net_income", {}))
    revenue_series = to_series(analysis.get("financials", {}).get("revenue", {}))
    equity_series = to_series(analysis.get("financials", {}).get("total_equity", {}))
    fcf_series = to_series(analysis.get("financials", {}).get("free_cash_flow", {}))

    price_series = to_price_series(data)

    trailing_pe = info.get("trailingPE")
    price_to_book = info.get("priceToBook")
    price_to_sales = info.get("priceToSalesTrailing12Months")
    peg = info.get("pegRatio")
    ev_to_ebitda = info.get("enterpriseToEbitda")

    pe_history = compute_ratio_history(
        net_income_series, net_income_series, price_series, shares_outstanding
    )
    ps_history = compute_ratio_history(
        revenue_series, revenue_series, price_series, shares_outstanding
    )
    pb_history = compute_ratio_history(
        equity_series, equity_series, price_series, shares_outstanding
    )

    valuation = {
        "symbol": analysis.get("symbol"),
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "current": {
            "price": current_price,
            "market_cap": market_cap,
        },
        "metrics": {
            "pe": trailing_pe,
            "ps": price_to_sales,
            "pb": price_to_book,
            "peg": peg,
            "ev_to_ebitda": ev_to_ebitda,
        },
        "history": {
            "pe": pe_history,
            "ps": ps_history,
            "pb": pb_history,
        },
        "percentiles": {
            "pe": percentile(trailing_pe, pe_history),
            "ps": percentile(price_to_sales, ps_history),
            "pb": percentile(price_to_book, pb_history),
        },
        "dcf": compute_dcf(
            float(fcf_series.iloc[-1]) if not fcf_series.empty else None,
            shares_outstanding,
        ),
    }

    return valuation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute valuation metrics")
    parser.add_argument("--input", required=True, help="Data JSON path")
    parser.add_argument("--analysis", required=True, help="Analysis JSON path")
    parser.add_argument("--output", default="./output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with open(args.input, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    with open(args.analysis, "r", encoding="utf-8") as handle:
        analysis = json.load(handle)

    valuation = build_valuation(data, analysis)
    output_path = f"{args.output}/{analysis['symbol'].replace('.', '_')}_valuation.json"
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(valuation, handle, ensure_ascii=False, indent=2)

    print(f"Saved valuation to {output_path}")


if __name__ == "__main__":
    main()
