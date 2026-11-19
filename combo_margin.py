"""Worst simultaneous margin usage of the combined portfolio, by risk level."""
from __future__ import annotations

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "results", "combo")
CONTRACT = 100_000.0
LEVERAGE = 100.0
START = 5_000.0


def max_margin(trades, risk_money):
    events = []
    for t in trades:
        lots = risk_money / (float(t["stop_pips"]) * float(t["pip_value"]))
        m = lots * CONTRACT / LEVERAGE
        events.append((int(t["entry_ms"]), 1, m))
        events.append((int(t["exit_ms"]), -1, m))
    events.sort()
    cur = worst = 0.0
    for _ms, kind, m in events:
        cur += kind * m
        worst = max(worst, cur)
    return worst


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "core"
    d = BASE if tag == "core" else os.path.join(BASE, tag)
    trades = list(csv.DictReader(open(os.path.join(d, "trades_combo.csv"), encoding="utf-8")))
    print(f"{'risk':>8} {'risk $/trade':>13} {'max margin $':>13} {'% of 5k':>9}")
    for risk in (0.0005, 0.0010, 0.00125, 0.0015, 0.0025):
        m = max_margin(trades, START * risk)
        print(f"{100*risk:7.3f}% {START*risk:13.2f} {m:13.0f} {100*m/START:8.1f}%")


if __name__ == "__main__":
    main()
