"""Losing-streak analysis for the combined portfolio: observed + Monte Carlo."""
from __future__ import annotations

import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "results", "combo")


def load(tag: str):
    d = BASE if tag == "core" else os.path.join(BASE, tag)
    trades = list(csv.DictReader(open(os.path.join(d, "trades_combo.csv"), encoding="utf-8")))
    trades.sort(key=lambda t: int(t["exit_ms"]))
    return trades


def max_streak(r: np.ndarray) -> int:
    loss = r <= 0
    if loss.all():
        return len(r)
    idx = np.where(~loss)[0]
    edges = np.concatenate([[-1], idx, [len(r)]])
    return int((np.diff(edges) - 1).max())


def streak_report(r: np.ndarray, label: str) -> None:
    best = cur = 0
    start = best_start = 0
    for i, x in enumerate(r):
        if x <= 0:
            if cur == 0:
                start = i
            cur += 1
            if cur > best:
                best, best_start = cur, start
        else:
            cur = 0
    seg = r[best_start:best_start + best]
    print(f"{label:<28} max losing streak = {best} trades, sum {seg.sum():+.2f}R, "
          f"avg {seg.mean():+.2f}R")


def main() -> None:
    tag = sys.argv[1] if len(sys.argv) > 1 else "core"
    trades = load(tag)
    r = np.array([float(t["R"]) for t in trades])

    print(f"dataset combo/{tag}: {len(trades)} trades, {trades[0]['date']} -> {trades[-1]['date']}\n")
    streak_report(r, "all trades, time order")

    # consecutive losing days
    daily: dict[str, float] = {}
    for t in trades:
        daily[t["date"]] = daily.get(t["date"], 0.0) + float(t["R"])
    days = sorted(daily)
    dv = np.array([daily[d] for d in days])
    best = cur = 0
    best_end = 0
    for i, x in enumerate(dv):
        if x <= 0:
            cur += 1
            if cur > best:
                best, best_end = cur, i
        else:
            cur = 0
    print(f"{'losing days':<28} max = {best} days, sum {dv[best_end-best+1:best_end+1].sum():+.1f}R, "
          f"ending {days[best_end]}")

    # per strategy
    print()
    for s in sorted({t["strategy"] for t in trades}):
        sub = np.array([float(t["R"]) for t in trades if t["strategy"] == s])
        streak_report(sub, s)

    # ---- Monte Carlo over whole days
    day_r: dict[str, list[float]] = {}
    for t in trades:
        day_r.setdefault(t["date"], []).append(float(t["R"]))
    days_sorted = sorted(day_r)
    width = max(len(v) for v in day_r.values())
    mat = np.full((len(days_sorted), width), np.nan)
    for i, d in enumerate(days_sorted):
        v = day_r[d]
        mat[i, :len(v)] = v

    rng = np.random.default_rng(7)
    runs = 4000
    nd = len(days_sorted)
    out = np.empty(runs, dtype=int)
    for k in range(runs):
        pick = rng.integers(0, nd, nd)
        flat = mat[pick].ravel()
        flat = flat[~np.isnan(flat)]
        out[k] = max_streak(flat)

    print(f"\nMonte Carlo, {runs} runs of {nd} resampled days (~{int(np.nanmean(np.sum(~np.isnan(mat), axis=1))*nd):,} trades):")
    for q in (50, 75, 90, 95, 99, 99.9):
        print(f"  p{q:<5} = {np.percentile(out, q):.0f} losing trades in a row")
    print(f"  worst = {out.max()} losing trades in a row")

    # $ impact at candidate risks (avg loss ~1R)
    print("\n$ impact of the p99 streak at flat risk (1R per loss):")
    for risk in (0.0010, 0.00125, 0.0015):
        n = np.percentile(out, 99)
        print(f"  {100*risk:.3f}%/trade -> {n:.0f}R = ${5000*risk*n:,.0f} "
              f"({100*risk*n:.1f}% of a $5,000 account)")


if __name__ == "__main__":
    main()
