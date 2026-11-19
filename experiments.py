"""Variant experiments for the NY first-candle EMA20 strategy.

Runs the baseline plus the three requested fixes:
  1. displacement filter  - signal candle must clear EMA20 by 0.5 x ATR
  2. fixed 2R target      - replaces the EMA-cross exit
  3. 15m EMA200 filter    - trade only with the higher-timeframe bias
and the combinations.
"""
from __future__ import annotations

import csv
import json
import os

import backtest as b

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    df = b.load_m1(b.DEFAULT_FILES)
    df = b.add_indicators(df)
    idx_et = b.et_index(df)
    trend = b.build_trend(df, idx_et)

    last_ms = int(df["timestamp"].iloc[-1])
    start_ms = last_ms - b.WINDOW_DAYS * 86400_000

    variants = [
        ("baseline", {}),
        ("displacement 0.5 ATR", {"min_disp_atr": 0.5}),
        ("displacement 1.0 ATR", {"min_disp_atr": 1.0}),
        ("fixed 2R target", {"target_R": 2.0}),
        ("fixed 3R target", {"target_R": 3.0}),
        ("15m EMA200 filter", {"trend": trend}),
        ("disp 0.5 + 2R", {"min_disp_atr": 0.5, "target_R": 2.0}),
        ("disp 0.5 + trend", {"min_disp_atr": 0.5, "trend": trend}),
        ("disp 0.5 + trend + 2R", {"min_disp_atr": 0.5, "target_R": 2.0, "trend": trend}),
        ("baseline 09:30 ET", {"session_start_min": 9 * 60 + 30}),
        ("fade 08:00 ET", {"fade": True}),
        ("fade 09:30 ET", {"fade": True, "session_start_min": 9 * 60 + 30}),
        ("fade + 2R", {"fade": True, "target_R": 2.0}),
    ]

    results = []
    trades_by_label: dict[str, list[dict]] = {}
    for label, kwargs in variants:
        trades = b.run_backtest(df, idx_et, 1.5, **kwargs)
        trades = [t for t in trades if t["entry_ms"] >= start_ms]
        trades_by_label[label] = trades
        results.append(b.summarize(trades, label))

    for s in results:
        b.print_summary(s)

    # best by total R, ties by PF
    best = max(results, key=lambda s: (s.get("total_R", -1e9), s.get("profit_factor", 0)))
    print(f"\nbest: {best['label']}")
    best_trades = trades_by_label[best["label"]]

    if best_trades:
        path = os.path.join(OUT_DIR, "trades_best.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(best_trades[0].keys()))
            w.writeheader()
            w.writerows(best_trades)
        print(f"trades -> {path}")

        by_month: dict[str, list[dict]] = {}
        for t in best_trades:
            by_month.setdefault(t["date"][:7], []).append(t)
        print("\nbest by month")
        for month in sorted(by_month):
            b.print_summary(b.summarize(by_month[month], month))

    path = os.path.join(OUT_DIR, "variants.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=float)
    print(f"summary -> {path}")


if __name__ == "__main__":
    main()
