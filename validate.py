"""Validate the two surviving families out of sample and under stress.

Families kept from the screen:
  orb_london      - 03:00 ET range breakout, EMA200 bias, range stop, 16:00 ET exit
  level_pd_london - previous-day high/low breakout during the London session

Tests:
  1. split-sample: 2011-2015 (never used for selection), 2016-2020, 2021-2026
  2. doubled costs
  3. parameter perturbation around the chosen values
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lab

OUT = os.path.join(HERE, "results", "lab")
SPLITS = [("2011-2015", "2011-01-01", "2015-12-31"),
          ("2016-2020", "2016-01-01", "2020-12-31"),
          ("2021-2026", "2021-01-01", "2026-11-03")]


def clipped(trades, a, b):
    return [t for t in trades if a <= t["date"] <= b]


def line(label, s):
    return (f"{label:<34} n={s['trades']:>4} avgR={s['avg_R']:+.3f} totR={s['total_R']:+7.1f} "
            f"DD={s['max_dd_R']:7.1f} calmar={s['calmar']:5.2f} t={s['t']:+5.2f} "
            f"yr={s['positive_years']}/{s['n_years']}")


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    report = {}

    for pair in lab.PAIRS:
        print(f"\n===== {pair} =====", flush=True)
        lab._cache.clear()

        orb = lab.session_orb(pair, 3 * 60, 5, 12 * 60, 16 * 60, 1.0, True, "range", "orb_london")
        lvl = lab.level_break(pair, "prev_day", 3 * 60, 12 * 60, 16 * 60, 1.0, True, "other_side", 1.0, "level_pd_london")

        report[pair] = {"splits": {}, "stress": {}, "grid": {}}

        print("-- split sample --")
        for name, a, b in SPLITS:
            for fam, tr in (("orb_london", orb), ("level_pd_london", lvl)):
                s = lab.stats(clipped(tr, a, b), f"{fam}_{name}")
                print(line(f"{fam} {name}", s), flush=True)
                report[pair]["splits"].setdefault(fam, {})[name] = {
                    k: s[k] for k in ("trades", "avg_R", "total_R", "max_dd_R", "calmar", "t")}

        # doubled costs
        print("-- doubled costs --")
        orig = lab.PAIRS[pair]["cost"]
        lab.PAIRS[pair]["cost"] = orig * 2
        orb2 = lab.session_orb(pair, 3 * 60, 5, 12 * 60, 16 * 60, 1.0, True, "range", "orb_london")
        lvl2 = lab.level_break(pair, "prev_day", 3 * 60, 12 * 60, 16 * 60, 1.0, True, "other_side", 1.0, "level_pd_london")
        lab.PAIRS[pair]["cost"] = orig
        for fam, tr in (("orb_london", orb2), ("level_pd_london", lvl2)):
            s = lab.stats(clipped(tr, "2016-01-01", "2026-11-03"), f"{fam}_2x")
            print(line(f"{fam} 2x cost", s), flush=True)
            report[pair]["stress"][f"{fam}_2x_cost"] = {
                k: s[k] for k in ("trades", "avg_R", "total_R", "max_dd_R", "calmar", "t")}

        # parameter perturbation on orb_london
        print("-- orb_london parameter grid (2016-2026) --")
        best = None
        for rb in (3, 5, 7):
            for buf in (0.0, 1.0, 2.0):
                for cut in (12, 14):
                    tr = lab.session_orb(pair, 3 * 60, rb, cut * 60, 16 * 60, buf, True, "range", "g")
                    s = lab.stats(clipped(tr, "2016-01-01", "2026-11-03"), f"rb{rb}_b{buf}_c{cut}")
                    key = f"rb{rb}_buf{buf}_cut{cut}"
                    report[pair]["grid"][key] = {
                        k: s[k] for k in ("trades", "avg_R", "total_R", "max_dd_R", "calmar", "t")}
                    if best is None or s["calmar"] > best[1]:
                        best = (key, s["calmar"], s["t"], s["trades"], s["avg_R"])
        print(f"  grid best: {best[0]} calmar={best[1]:.2f} t={best[2]:+.2f} n={best[3]} avgR={best[4]:+.3f}")

        # perturbation summary: worst and median calmar across the grid
        cal = sorted(v["calmar"] for v in report[pair]["grid"].values())
        print(f"  grid calmar min={cal[0]:.1f} median={cal[len(cal)//2]:.1f} max={cal[-1]:.1f}")

    with open(os.path.join(OUT, "validation.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=float)
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
