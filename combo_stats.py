"""Descriptive statistics for the combined portfolio (no prop rules)."""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lab

BASE = os.path.join(HERE, "results", "combo")


def main() -> None:
    tag = sys.argv[1] if len(sys.argv) > 1 else "core"
    d = BASE if tag == "core" else os.path.join(BASE, tag)
    trades = list(csv.DictReader(open(os.path.join(d, "trades_combo.csv"), encoding="utf-8")))
    days = list(csv.DictReader(open(os.path.join(d, "days.csv"), encoding="utf-8")))

    r = np.array([float(t["R"]) for t in trades])
    daily = {x["date"]: float(x["R"]) for x in days}

    eq = peak = worst = 0.0
    dd_series = []
    for k in sorted(daily):
        eq += daily[k]
        peak = max(peak, eq)
        worst = min(worst, eq - peak)
        dd_series.append(eq - peak)

    # longest losing streaks
    tr = sorted(trades, key=lambda t: int(t["exit_ms"]))
    best = cur = 0
    for t in tr:
        if float(t["R"]) <= 0:
            cur += 1; best = max(best, cur)
        else:
            cur = 0
    best_d = cur_d = 0
    for k in sorted(daily):
        if daily[k] <= 0:
            cur_d += 1; best_d = max(best_d, cur_d)
        else:
            cur_d = 0

    print(f"trades={len(trades)}  days={len(days)}  avgR={r.mean():+.3f}  "
          f"totR={r.sum():+.1f}  maxDD={worst:.1f}R  calmar={r.sum()/abs(worst):.1f}")
    print(f"loss streak: {best} trades / {best_d} days")
    print(f"positive days: {100*sum(1 for v in daily.values() if v>0)/len(daily):.1f}%")
    print(f"daily R: mean={np.mean(list(daily.values())):+.3f} sd={np.std(list(daily.values()),ddof=1):.3f} "
          f"worst={min(daily.values()):+.2f} best={max(daily.values()):+.2f}")

    # yearly
    print("\nyear   trades   totR    avgR   maxDD_R")
    by_year: dict[str, list[dict]] = {}
    for t in trades:
        by_year.setdefault(t["date"][:4], []).append(t)
    for y in sorted(by_year):
        yy = np.array([float(t["R"]) for t in by_year[y]])
        dyy = {}
        for t in by_year[y]:
            dyy[t["date"]] = dyy.get(t["date"], 0.0) + float(t["R"])
        e = p = w = 0.0
        for k in sorted(dyy):
            e += dyy[k]; p = max(p, e); w = min(w, e - p)
        print(f"{y}  {len(yy):>6}  {yy.sum():+8.1f}  {yy.mean():+.3f}  {w:8.1f}")

    # per strategy per year
    print("\nper-strategy yearly R")
    years = sorted(by_year)
    print(f"{'strategy':<12}" + "".join(f"{y:>9}" for y in years))
    for s in ("ny_orb", "london_orb", "prev_level"):
        row = []
        for y in years:
            v = sum(float(t["R"]) for t in by_year[y] if t["strategy"] == s)
            row.append(f"{v:+9.1f}")
        print(f"{s:<12}" + "".join(row))

    # risk of ruin sanity: DD in % at candidate risks
    print("\nmax DD if risk were flat (historical path):")
    for risk in (0.0005, 0.00075, 0.0010, 0.00125, 0.0015, 0.0020, 0.0025):
        print(f"  {100*risk:.3f}%/trade -> {100*abs(worst)*risk:.2f}% of balance")


if __name__ == "__main__":
    main()
