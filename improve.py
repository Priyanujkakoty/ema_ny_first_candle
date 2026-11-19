"""One-factor-at-a-time improvements on the bias ORB, pooled over 5 years.

Base: bias range/flat, 0.8 pip cost. Each variant changes exactly one thing.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as b
import orb

ROOT = r"E:\FOREX INTEL"
FILES = [
    os.path.join(ROOT, "market_data", "EURUSD", "1m", "yearly", f"eurusd_1m_{y}.csv")
    for y in range(2021, 2027)
]
YEARS = 5


def pooled(trades: list[dict], last_ms: int) -> dict:
    p = np.array([t["pips"] for t in trades])
    r = np.array([t["R"] for t in trades])
    wins = p[p > 0]
    losses = p[p <= 0]
    eq = 0.0; peak = 0.0; dd = 0.0
    for x in sorted(trades, key=lambda t: t["exit_ms"]):
        eq += x["R"]; peak = max(peak, eq); dd = min(dd, eq - peak)
    yearly = []
    for k in range(YEARS):
        end = last_ms - k * 365 * 86400_000
        start = end - 365 * 86400_000
        yearly.append(sum(t["pips"] for t in trades if start <= t["entry_ms"] < end))
    return {
        "n": len(trades),
        "win": 100 * len(wins) / len(p),
        "pips": p.sum(),
        "ev": p.mean(),
        "pf": wins.sum() / abs(losses.sum()) if losses.sum() else float("inf"),
        "dd": dd,
        "t": p.mean() / (p.std(ddof=1) / np.sqrt(len(p))),
        "yearly": yearly,
        "pos_years": sum(1 for y in yearly if y > 0),
    }


def main() -> None:
    df = b.load_m1(FILES)
    df = b.add_indicators(df)
    idx = b.et_index(df)
    trend15 = b.build_trend(df, idx, tf_min=15)
    trend60 = b.build_trend(df, idx, tf_min=60)
    last_ms = int(df["timestamp"].iloc[-1])
    start_ms = last_ms - YEARS * 365 * 86400_000

    base = dict(use_bias=True, stop_mode="range", exit_mode="flat")
    variants = [
        ("base", {}, trend15),
        ("min range 3p", dict(min_range_pips=3.0), trend15),
        ("min range 4p", dict(min_range_pips=4.0), trend15),
        ("max range 8p", dict(max_range_pips=8.0), trend15),
        ("range 3-8p", dict(min_range_pips=3.0, max_range_pips=8.0), trend15),
        ("cutoff 10:00", dict(cutoff_min=10 * 60), trend15),
        ("cutoff 11:00", dict(cutoff_min=11 * 60), trend15),
        ("buffer 0.5p", dict(buffer_pips=0.5), trend15),
        ("buffer 1.0p", dict(buffer_pips=1.0), trend15),
        ("bias 1h EMA200", {}, trend60),
        ("breakeven +1R", dict(be_at_R=1.0), trend15),
        ("skip Monday", dict(skip_weekdays={0}), trend15),
        ("skip Friday", dict(skip_weekdays={4}), trend15),
        ("combo min3+cut11+BE", dict(min_range_pips=3.0, cutoff_min=11 * 60, be_at_R=1.0), trend15),
    ]

    for label, extra, trend in variants:
        kw = dict(base); kw.update(extra)
        trades = [t for t in orb.run_orb(df, idx, trend, **kw) if t["entry_ms"] >= start_ms]
        s = pooled(trades, last_ms)
        yr = " ".join(f"{y:+.0f}" for y in s["yearly"])
        print(
            f"{label:<22} n={s['n']:>4}  win={s['win']:5.1f}%  pips={s['pips']:+8.1f}  "
            f"EV={s['ev']:+5.2f}p  PF={s['pf']:5.2f}  DD={s['dd']:6.1f}R  "
            f"t={s['t']:+5.2f}  yrs+={s['pos_years']}/5  [{yr}]"
        )


if __name__ == "__main__":
    main()
