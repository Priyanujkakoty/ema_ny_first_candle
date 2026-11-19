"""Monthly P&L summary for the combined portfolio (static $5,000 base)."""
from __future__ import annotations

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "results", "combo")


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "core"
    d = BASE if tag == "core" else os.path.join(BASE, tag)
    prop = os.path.join(d, "prop")
    for name in sorted(os.listdir(prop)):
        if not name.startswith("monthly_"):
            continue
        rows = list(csv.DictReader(open(os.path.join(prop, name), encoding="utf-8")))
        v = [float(r["usd_static"]) for r in rows]
        pos = sum(1 for x in v if x > 0)
        print(f"{name:<24} months={len(v):>3} pos={pos:>3} ({100*pos/len(v):4.1f}%) "
              f"total=${sum(v):>9,.0f} mean=${sum(v)/len(v):>7,.0f} "
              f"best=${max(v):>7,.0f} worst=${min(v):>8,.0f}")


if __name__ == "__main__":
    main()
