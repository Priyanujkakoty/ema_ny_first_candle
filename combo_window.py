"""Portfolio stats restricted to a date window (apples-to-apples with the NY report)."""
from __future__ import annotations

import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "results", "combo")


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "core"
    start = sys.argv[2] if len(sys.argv) > 2 else "2021-11-05"
    end = sys.argv[3] if len(sys.argv) > 3 else "2026-11-03"
    d = BASE if tag == "core" else os.path.join(BASE, tag)
    trades = [t for t in csv.DictReader(open(os.path.join(d, "trades_combo.csv"), encoding="utf-8"))
              if start <= t["date"] <= end]
    daily: dict[str, float] = {}
    for t in trades:
        daily[t["date"]] = daily.get(t["date"], 0.0) + float(t["R"])
    eq = peak = worst = 0.0
    for k in sorted(daily):
        eq += daily[k]
        peak = max(peak, eq)
        worst = min(worst, eq - peak)
    r = np.array([float(t["R"]) for t in trades])
    print(f"{start} -> {end}: trades={len(trades)} days={len(daily)} "
          f"totR={r.sum():+.1f} avgR={r.mean():+.3f} maxDD={worst:.1f}R "
          f"calmar={r.sum()/abs(worst):.1f} t={r.mean()/(r.std(ddof=1)/np.sqrt(len(r))):+.2f}")
    for s in sorted({t["strategy"] for t in trades}):
        sub = [t for t in trades if t["strategy"] == s]
        rr = np.array([float(t["R"]) for t in sub])
        print(f"  {s:<12} n={len(sub):>5} totR={rr.sum():+8.1f} avgR={rr.mean():+.3f}")


if __name__ == "__main__":
    main()
