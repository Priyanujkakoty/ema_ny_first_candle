"""Leave-one-out and subset analysis for the combined portfolio."""
from __future__ import annotations

import csv
import itertools
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "results", "combo")


def curve(trades):
    daily: dict[str, float] = {}
    for t in trades:
        daily[t["date"]] = daily.get(t["date"], 0.0) + float(t["R"])
    eq = peak = worst = 0.0
    for k in sorted(daily):
        eq += daily[k]
        peak = max(peak, eq)
        worst = min(worst, eq - peak)
    r = np.array([float(t["R"]) for t in trades])
    return r.sum(), worst, len(trades), len(daily)


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "core"
    d = BASE if tag == "core" else os.path.join(BASE, tag)
    trades = list(csv.DictReader(open(os.path.join(d, "trades_combo.csv"), encoding="utf-8")))
    strats = sorted({t["strategy"] for t in trades})

    print(f"{'subset':<34}{'trades':>8}{'totR':>10}{'maxDD':>9}{'calmar':>8}{'R/yr':>8}")
    for k in range(1, len(strats) + 1):
        for combo in itertools.combinations(strats, k):
            sub = [t for t in trades if t["strategy"] in combo]
            tot, dd, n, nd = curve(sub)
            label = "+".join(combo)
            print(f"{label:<34}{n:>8}{tot:>+10.1f}{dd:>9.1f}{tot/abs(dd):>8.1f}{tot/11:>8.0f}")

    # drop the single best pair
    pairs = sorted({t["pair"] for t in trades})
    print()
    for p in pairs:
        sub = [t for t in trades if t["pair"] != p]
        tot, dd, n, nd = curve(sub)
        print(f"drop {p:<29}{n:>8}{tot:>+10.1f}{dd:>9.1f}{tot/abs(dd):>8.1f}")


if __name__ == "__main__":
    main()
