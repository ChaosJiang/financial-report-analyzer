#!/usr/bin/env python3
"""Analyze analyst expectations from fetched data."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import pandas as pd


BUY_KEYWORDS = {"buy", "strong buy", "overweight", "outperform", "add"}
HOLD_KEYWORDS = {"hold", "neutral", "market perform", "equal-weight"}
SELL_KEYWORDS = {"sell", "underperform", "underweight", "reduce"}


def grade_bucket(grade: str) -> str:
    normalized = grade.strip().lower()
    if any(key in normalized for key in BUY_KEYWORDS):
        return "buy"
    if any(key in normalized for key in HOLD_KEYWORDS):
        return "hold"
    if any(key in normalized for key in SELL_KEYWORDS):
        return "sell"
    return "other"


def summarize_recommendations(recommendations: Dict[str, Any]) -> Dict[str, int]:
    if not recommendations:
        return {}
    df = pd.DataFrame(recommendations)
    if df.empty:
        return {}
    df.index = pd.to_datetime(
        df.index, errors="coerce", utc=True, format="mixed"
    ).tz_localize(None)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=90)
    recent = df[df.index >= cutoff]
    if recent.empty:
        recent = df
    buckets = {"buy": 0, "hold": 0, "sell": 0, "other": 0}
    for grade in recent.get("To Grade", []):
        bucket = grade_bucket(str(grade))
        buckets[bucket] += 1
    return {key: value for key, value in buckets.items() if value > 0}


def normalize_summary_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.notna(numeric):
        return float(numeric)
    return str(value)


def summarize_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    if not summary:
        return {}
    df = pd.DataFrame(summary)
    if df.empty:
        return {}
    latest = df.iloc[0].to_dict()
    return {key: normalize_summary_value(value) for key, value in latest.items()}


def build_analyst_report(data: Dict[str, Any]) -> Dict[str, Any]:
    info = data.get("info", {}) or {}
    analyst = data.get("analyst", {}) or {}

    recommendations = analyst.get("recommendations", {})
    recommendations_summary = analyst.get("recommendations_summary", {})

    return {
        "symbol": data.get("symbol"),
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "rating": {
            "recommendation_key": info.get("recommendationKey"),
            "recommendation_mean": info.get("recommendationMean"),
            "summary": summarize_summary(recommendations_summary),
            "recent_distribution": summarize_recommendations(recommendations),
        },
        "price_targets": {
            "mean": info.get("targetMeanPrice"),
            "high": info.get("targetHighPrice"),
            "low": info.get("targetLowPrice"),
            "current": info.get("currentPrice"),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze analyst expectations")
    parser.add_argument("--input", required=True, help="Data JSON path")
    parser.add_argument("--output", default="./output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with open(args.input, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    analyst_report = build_analyst_report(data)
    output_path = f"{args.output}/{data['symbol'].replace('.', '_')}_analyst.json"
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(analyst_report, handle, ensure_ascii=False, indent=2)

    print(f"Saved analyst report to {output_path}")


if __name__ == "__main__":
    main()
