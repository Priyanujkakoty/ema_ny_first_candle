"""Robustness checks for the NY range-breakout variants.

Runs the promising configurations across five rolling 1-year windows and
a cost ladder, so a single lucky year cannot masquerade as an edge.
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as b
import orb

ROOT = r"E:\FOREX INTEL"
FILES = [
    os.path.join(ROOT, "market_data", "EURUSD", "1m", "yearly", f"eurusd_1m_{y}.csv")
    for y in range(2021, 2027)
]

CONFIGS = [
    ("bias range/flat", dict(use_bias=True, stop_mode="range", exit_mode="flat")),
    ("bias atr/flat", dict(use_bias=True, stop_mode="atr", exit_mode="flat")),
    ("bias range/3R", dict(use_bias=True, stop_mode="range", exit_mode="target", target_R=3.0)),
    ("no bias range/flat", dict(use_bias=False, stop_mode="range", exit_mode="flat")),
]


def main() -> None:
    df = b.load_m1(FILES)
    df = b.add_indicators(df)
    idx = b.et_index(df)
    trend = b.build_trend(df, idx)

    last_ms = int(df["timestamp"].iloc[-1])
    windows = [last_ms - k * 365 * 86400_000 for k in range(5)]
    windows = [w for w in windows if w > int(df["timestamp"].iloc[0]) + 400 * 86400_000]

    for name, kw in CONFIGS:
        all_trades = orb.run_orb(df, idx, trend, **kw)
        print(f"\n=== {name} ===")
        for end in windows:
            start = end - 365 * 86400_000
            trades = [t for t in all_trades if start <= t["entry_ms"] < end]
            if not trades:
                print(f"  {end}: no trades")
                continue
            s = b.summarize(trades, "window")
            pips = sum(t["pips"] for t in trades)
            print(
                f"  {end}: n={s['trades']:>3}  win={s['win_rate']:5.1f}%  "
                f"pips={pips:+7.1f}  totR={s['total_R']:+7.1f}  PF={s['profit_factor']:5.2f}  "
                f"maxDD={s['max_dd_R']:6.1f}R  t={s['t_stat']:+5.2f}"
            )

        # cost ladder on the most recent year
        print("  cost ladder (latest year):")
        start = windows[0] - 365 * 86400_000
        for cost in (0.0, 0.8, 1.2, 1.6):
            trades = orb.run_orb(df, idx, trend, cost_pips=cost, **kw)
            trades = [t for t in trades if start <= t["entry_ms"] < windows[0]]
            pips = sum(t["pips"] for t in trades)
            s = b.summarize(trades, "c")
            print(
                f"    cost {cost:.1f}p: n={s['trades']:>3}  pips={pips:+7.1f}  "
                f"PF={s['profit_factor']:5.2f}  t={s['t_stat']:+5.2f}"
            )


if __name__ == "__main__":
    main()
