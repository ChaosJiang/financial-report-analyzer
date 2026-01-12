#!/usr/bin/env python3
"""Generate PNG charts from analysis output."""

from __future__ import annotations

import argparse
import json
import os
from typing import Dict, Optional

import matplotlib.pyplot as plt
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


def plot_series(
    series_list: Dict[str, pd.Series], title: str, ylabel: str, output_path: str
) -> None:
    if not series_list:
        return
    plt.figure(figsize=(9, 4.5))
    plotted = False
    for label, series in series_list.items():
        if series.empty:
            continue
        plt.plot(series.index, series.values, marker="o", label=label)
        plotted = True
    if not plotted:
        plt.close()
        return
    plt.title(title)
    plt.ylabel(ylabel)
    plt.xlabel("Date")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate charts from analysis JSON")
    parser.add_argument("--analysis", required=True, help="Path to analysis JSON")
    parser.add_argument("--output", required=True, help="Output directory for charts")
    args = parser.parse_args()

    with open(args.analysis, "r", encoding="utf-8") as handle:
        analysis = json.load(handle)

    ensure_dir(args.output)

    revenue = series_from_dict(analysis.get("financials", {}).get("revenue", {}))
    net_income = series_from_dict(analysis.get("financials", {}).get("net_income", {}))
    gross_margin = series_from_dict(analysis.get("ratios", {}).get("gross_margin", {}))
    net_margin = series_from_dict(analysis.get("ratios", {}).get("net_margin", {}))
    roe = series_from_dict(analysis.get("ratios", {}).get("roe", {}))
    roa = series_from_dict(analysis.get("ratios", {}).get("roa", {}))
    debt_to_equity = series_from_dict(
        analysis.get("ratios", {}).get("debt_to_equity", {})
    )
    price = series_from_dict(analysis.get("price", {}).get("history", {}))

    plot_series(
        {"Revenue": revenue, "Net Income": net_income},
        "Revenue & Net Income",
        "Amount",
        os.path.join(args.output, "revenue_net_income.png"),
    )

    plot_series(
        {"Gross Margin": gross_margin, "Net Margin": net_margin},
        "Margin Trends",
        "Ratio",
        os.path.join(args.output, "margin_trends.png"),
    )

    plot_series(
        {"ROE": roe, "ROA": roa},
        "ROE & ROA",
        "Ratio",
        os.path.join(args.output, "roe_roa.png"),
    )

    plot_series(
        {"Debt/Equity": debt_to_equity},
        "Debt to Equity",
        "Ratio",
        os.path.join(args.output, "debt_to_equity.png"),
    )

    plot_series(
        {"Price": price},
        "Stock Price",
        "Price",
        os.path.join(args.output, "price_history.png"),
    )

    print(f"Saved charts to {args.output}")


if __name__ == "__main__":
    main()
