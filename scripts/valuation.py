#!/usr/bin/env python3
"""Compute valuation metrics and historical percentiles."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import yfinance as yf


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


def align_to_prices(snapshot: pd.Series, prices: pd.Series) -> pd.Series:
    if prices.empty:
        return pd.Series(dtype=float)
    if snapshot.empty:
        return pd.Series(index=prices.index, dtype=float)
    snapshot = snapshot.dropna().sort_index()
    if snapshot.empty:
        return pd.Series(index=prices.index, dtype=float)
    return snapshot.reindex(prices.index, method="ffill")


def series_to_dict(series: pd.Series) -> Dict[str, float]:
    if series.empty:
        return {}
    ordered = series.dropna().sort_index()
    return {str(idx.date()): float(val) for idx, val in ordered.items()}


def fetch_fx_rate(base: Optional[str], quote: Optional[str]) -> Optional[float]:
    if not base or not quote or base == quote:
        return 1.0
    pair = f"{base}{quote}=X"
    for symbol, invert in [(pair, False), (f"{quote}{base}=X", True)]:
        try:
            ticker = yf.Ticker(symbol)
            history = ticker.history(period="5d", auto_adjust=False)
            if "Close" not in history or history["Close"].dropna().empty:
                continue
            rate = float(history["Close"].dropna().iloc[-1])
            if rate == 0:
                continue
            return 1 / rate if invert else rate
        except Exception:
            continue
    return None


def convert_series(
    series: pd.Series, fx_rate: Optional[float], apply_conversion: bool
) -> pd.Series:
    if series.empty:
        return series
    if not apply_conversion:
        return series
    if fx_rate is None:
        return pd.Series(dtype=float)
    return series * fx_rate


def percentile(current: Optional[float], history: pd.Series) -> Optional[float]:
    if current is None or history.empty:
        return None
    values = history.replace([np.inf, -np.inf], np.nan).dropna()
    values = values[values > 0]
    if values.empty:
        return None
    return float((values <= current).sum() / len(values) * 100)


def compute_dcf(
    free_cash_flow: Optional[float],
    net_debt: Optional[float],
    shares_outstanding: Optional[float],
    discount_rate: float = 0.1,
    growth_rate: float = 0.05,
    terminal_growth: float = 0.02,
    years: int = 5,
) -> Dict[str, Any]:
    if free_cash_flow is None or free_cash_flow <= 0:
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
    enterprise_value = pv + pv_terminal

    result: Dict[str, Any] = {
        "assumptions": {
            "discount_rate": discount_rate,
            "growth_rate": growth_rate,
            "terminal_growth": terminal_growth,
            "years": years,
        },
        "enterprise_value": float(enterprise_value),
    }

    if net_debt is not None:
        equity_value = enterprise_value - net_debt
        result["net_debt"] = float(net_debt)
        result["equity_value"] = float(equity_value)
        if shares_outstanding:
            result["per_share"] = float(equity_value / shares_outstanding)

    return result


def build_valuation(data: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    info = data.get("info", {}) or {}
    market_currency = info.get("currency")
    financial_currency = info.get("financialCurrency") or market_currency

    price_series = to_price_series(data)

    currency_mismatch = bool(
        market_currency and financial_currency and market_currency != financial_currency
    )
    fx_rate = (
        fetch_fx_rate(financial_currency, market_currency) if currency_mismatch else 1.0
    )

    eps_ttm = to_series(analysis.get("per_share_ttm", {}).get("eps", {}))
    sales_ttm = to_series(analysis.get("per_share_ttm", {}).get("sales", {}))
    ebitda_ttm = to_series(analysis.get("per_share_ttm", {}).get("ebitda", {}))

    book_per_share = to_series(
        analysis.get("balance_quarterly", {}).get("book_per_share", {})
    )
    net_debt_per_share = to_series(
        analysis.get("balance_quarterly", {}).get("net_debt_per_share", {})
    )
    shares_outstanding = to_series(
        analysis.get("balance_quarterly", {}).get("shares_outstanding", {})
    )

    eps_ttm = convert_series(eps_ttm, fx_rate, currency_mismatch)
    sales_ttm = convert_series(sales_ttm, fx_rate, currency_mismatch)
    ebitda_ttm = convert_series(ebitda_ttm, fx_rate, currency_mismatch)
    book_per_share = convert_series(book_per_share, fx_rate, currency_mismatch)
    net_debt_per_share = convert_series(net_debt_per_share, fx_rate, currency_mismatch)

    eps_daily = align_to_prices(eps_ttm, price_series)
    sales_daily = align_to_prices(sales_ttm, price_series)
    ebitda_daily = align_to_prices(ebitda_ttm, price_series)
    book_daily = align_to_prices(book_per_share, price_series)
    net_debt_daily = align_to_prices(net_debt_per_share, price_series)
    shares_daily = align_to_prices(shares_outstanding, price_series)

    pe_daily = (price_series / eps_daily).where(eps_daily > 0)
    ps_daily = (price_series / sales_daily).where(sales_daily > 0)
    pb_daily = (price_series / book_daily).where(book_daily > 0)
    ev_to_ebitda_daily = ((price_series + net_debt_daily) / ebitda_daily).where(
        ebitda_daily > 0
    )

    market_cap_daily = (price_series * shares_daily).replace([np.inf, -np.inf], np.nan)

    latest_date = price_series.index.max() if not price_series.empty else None
    current_price = float(price_series.iloc[-1]) if latest_date is not None else None
    current_market_cap = (
        float(market_cap_daily.iloc[-1])
        if latest_date is not None and not pd.isna(market_cap_daily.iloc[-1])
        else None
    )

    def latest_value(series: pd.Series) -> Optional[float]:
        if series.empty:
            return None
        value = series.iloc[-1]
        return float(value) if not pd.isna(value) else None

    current_metrics = {
        "pe": latest_value(pe_daily),
        "ps": latest_value(ps_daily),
        "pb": latest_value(pb_daily),
        "ev_to_ebitda": latest_value(ev_to_ebitda_daily),
    }

    valuation_mask = ~(
        pe_daily.isna() & ps_daily.isna() & pb_daily.isna() & ev_to_ebitda_daily.isna()
    )
    window_start = (
        price_series.index[valuation_mask.argmax()]
        if not price_series.empty and valuation_mask.any()
        else None
    )

    fcf_ttm_total = to_series(
        analysis.get("financials_ttm", {}).get("free_cash_flow", {})
    )
    net_debt_total = to_series(
        analysis.get("balance_quarterly", {}).get("net_debt", {})
    )

    fcf_ttm_total = convert_series(fcf_ttm_total, fx_rate, currency_mismatch)
    net_debt_total = convert_series(net_debt_total, fx_rate, currency_mismatch)

    fcf_latest = latest_value(align_to_prices(fcf_ttm_total, price_series))
    net_debt_latest = latest_value(align_to_prices(net_debt_total, price_series))
    shares_latest = latest_value(align_to_prices(shares_outstanding, price_series))

    valuation = {
        "symbol": analysis.get("symbol"),
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "window": {
            "start": str(window_start.date()) if window_start is not None else None,
            "end": str(latest_date.date()) if latest_date is not None else None,
            "price_points": int(len(price_series)),
            "valuation_days": int(valuation_mask.sum())
            if not price_series.empty
            else 0,
            "snapshot_points": {
                "eps_ttm": int(len(eps_ttm)),
                "sales_ttm": int(len(sales_ttm)),
                "ebitda_ttm": int(len(ebitda_ttm)),
                "book_per_share": int(len(book_per_share)),
                "net_debt_per_share": int(len(net_debt_per_share)),
                "shares_outstanding": int(len(shares_outstanding)),
            },
        },
        "current": {
            "date": str(latest_date.date()) if latest_date is not None else None,
            "price": current_price,
            "market_cap": current_market_cap,
        },
        "metrics": current_metrics,
        "history": {
            "pe": series_to_dict(pe_daily),
            "ps": series_to_dict(ps_daily),
            "pb": series_to_dict(pb_daily),
            "ev_to_ebitda": series_to_dict(ev_to_ebitda_daily),
        },
        "percentiles": {
            "pe": percentile(current_metrics["pe"], pe_daily),
            "ps": percentile(current_metrics["ps"], ps_daily),
            "pb": percentile(current_metrics["pb"], pb_daily),
            "ev_to_ebitda": percentile(
                current_metrics["ev_to_ebitda"], ev_to_ebitda_daily
            ),
        },
        "currency": {
            "market": market_currency,
            "financial": financial_currency,
            "fx_rate": fx_rate,
            "converted": bool(currency_mismatch and fx_rate is not None),
        },
        "dcf": compute_dcf(
            fcf_latest,
            net_debt_latest,
            shares_latest,
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
