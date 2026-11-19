"""Screen intraday strategy families across the five available M1 pairs.

Search window 2016-01-01 .. 2026-11-03. Ranking metric is Calmar-like:
total R divided by max R drawdown, because the prop constraint is a trailing
drawdown limit, not a return target.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lab

START = "2016-01-01"
END = "2026-11-03"
OUT = os.path.join(HERE, "results", "lab")


def clip(trades, start=START, end=END):
    return [t for t in trades if start <= t["date"] <= end]


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    rows = []
    baselines = {}

    for pair in lab.PAIRS:
        print(f"loading {pair} ...", flush=True)
        base = clip(lab.session_orb(pair, 8 * 60, 5, 12 * 60, 16 * 60, 1.0, True, "range", "orb_ny"))
        baselines[pair] = lab.daily_r(base)
        s = lab.stats(base, "orb_ny")
        rows.append(dict(pair=pair, family="orb_ny", s=s, corr=1.0))

        cands = {
            "orb_london": lambda: lab.session_orb(pair, 3 * 60, 5, 12 * 60, 16 * 60, 1.0, True, "range", "orb_london"),
            "orb_london_nobias": lambda: lab.session_orb(pair, 3 * 60, 5, 12 * 60, 16 * 60, 1.0, False, "range", "orb_london"),
            "level_pd_london": lambda: lab.level_break(pair, "prev_day", 3 * 60, 12 * 60, 16 * 60, 1.0, True, "other_side", 1.0, "level_pd_london"),
            "level_pd_ny": lambda: lab.level_break(pair, "prev_day", 8 * 60, 12 * 60, 16 * 60, 1.0, True, "other_side", 1.0, "level_pd_ny"),
            "momentum_1000": lambda: lab.time_momentum(pair, 10 * 60, 120, 1.0, 16 * 60, 0.0, True, "momentum_1000"),
            "momentum_1000_loose": lambda: lab.time_momentum(pair, 10 * 60, 120, 1.0, 16 * 60, 0.0, False, "momentum_1000_loose"),
            "reversal_1500": lambda: lab.close_reversal(pair, 15 * 60, 120, 1.0, 16 * 60, 0.5, "reversal_1500"),
            "reversal_1500_wide": lambda: lab.close_reversal(pair, 15 * 60, 120, 1.5, 16 * 60, 1.0, "reversal_1500_wide"),
        }
        for name, fn in cands.items():
            tr = clip(fn())
            s = lab.stats(tr, name)
            c = lab.corr(lab.daily_r(tr), baselines[pair])
            rows.append(dict(pair=pair, family=name, s=s, corr=c))
            print(f"  {name:<20} n={s['trades']:>4} avgR={s['avg_R']:+.3f} totR={s['total_R']:+7.1f} "
                  f"DD={s['max_dd_R']:7.1f} calmar={s['calmar']:5.2f} t={s['t']:+5.2f} "
                  f"pos_years={s['positive_years']}/{s['n_years']} corr={c:+.2f}", flush=True)

    # compact ranking
    flat = []
    for r in rows:
        s = r["s"]
        if s["trades"] < 100:
            continue
        flat.append({
            "pair": r["pair"], "family": r["family"], "trades": s["trades"],
            "avg_R": s["avg_R"], "total_R": s["total_R"], "max_dd_R": s["max_dd_R"],
            "calmar": s["calmar"], "t": s["t"], "pf": s["pf"],
            "positive_years": s["positive_years"], "n_years": s["n_years"],
            "corr_orb": r["corr"], "years": s["years"],
        })
    flat.sort(key=lambda x: -x["calmar"])
    print("\n=== ranked by return / drawdown ===")
    for f in flat[:15]:
        print(f"{f['pair']:<7} {f['family']:<20} n={f['trades']:>4} totR={f['total_R']:+7.1f} "
              f"DD={f['max_dd_R']:7.1f} calmar={f['calmar']:5.2f} t={f['t']:+5.2f} "
              f"yr={f['positive_years']}/{f['n_years']} corr={f['corr_orb']:+.2f}")

    with open(os.path.join(OUT, "screen.json"), "w", encoding="utf-8") as f:
        json.dump(flat, f, indent=2, default=float)
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
