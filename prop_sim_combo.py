"""Prop-firm simulator for the combined 3-strategy portfolio.

Reuses the engine from prop_sim_portfolio.py (AquaFunded 2-Step Pro rules:
10% / 5% targets, 5% daily, 10% trailing max drawdown). Only the dataset and
the risk ladder change: the combined portfolio has a much larger R return per
year and a larger R drawdown, so the sustainable risk per trade is lower.

Usage:
  python prop_sim_combo.py            # core
  python prop_sim_combo.py wide       # 5-pair variant
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prop_sim_portfolio as P

BASE = os.path.join(HERE, "results", "combo")

RISK_LEVELS = (0.0005, 0.00075, 0.0010, 0.00125, 0.0015, 0.0020, 0.0025, 0.0050)
REPORT_LEVELS = (0.0005, 0.0010, 0.0015, 0.0025)


def load_trades(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    tag = sys.argv[1] if len(sys.argv) > 1 else "core"
    data_dir = BASE if tag == "core" else os.path.join(BASE, tag)
    out_dir = os.path.join(data_dir, "prop")
    os.makedirs(out_dir, exist_ok=True)

    days = P.load_days(os.path.join(data_dir, "days.csv"))
    trades = load_trades(os.path.join(data_dir, "trades_combo.csv"))
    n_trades = sum(d.trades for d in days)
    print(f"dataset: combo/{tag}  days: {len(days)}  {days[0].d} -> {days[-1].d}")
    print(f"trades: {n_trades}  avg/day={n_trades/len(days):.2f}  "
          f"max/day={max(d.trades for d in days)}")

    hist_rows, mc_rows = [], []
    for risk in RISK_LEVELS:
        results = [P.simulate(days, s, risk, trail_intraday=True) for s in range(len(days))]
        row = P.summarize(results, risk)
        hist_rows.append(row)
        mark = "*" if risk in REPORT_LEVELS else " "
        print(f"{mark}risk {risk*100:.3f}%: resolved={row['resolved']:>4} pass={row['passed']:>4} "
              f"({row['pass_rate_resolved']:5.1f}%) p1={row['phase1_rate']:5.1f}% p2={row['phase2_rate']:5.1f}% "
              f"med_days={row['median_days_to_pass']:5.0f} maxDaily=${row['max_daily_dd_$']:5.0f} "
              f"maxDD=${row['max_total_dd_$']:5.0f} fails={row['failed']} "
              f"daily={row['fail_daily_dd']} max={row['fail_max_dd']}")

        mc = P.monte_carlo(days, risk, trail_intraday=True)
        mc_rows.append(mc)
        print(f"MC {risk*100:.3f}%: pass={mc['pass_prob']:5.1f}% daily={mc['daily_breach_prob']:4.1f}% "
              f"maxdd={mc['maxdd_breach_prob']:5.1f}% dd p95={mc['dd_p95']:5.1f}% "
              f"p99={mc['dd_p99']:5.1f}% worst={mc['dd_worst']:5.1f}%")

    hist_eod, mc_eod = [], []
    for risk in RISK_LEVELS:
        results = [P.simulate(days, s, risk, trail_intraday=False) for s in range(len(days))]
        row = P.summarize(results, risk)
        hist_eod.append(row)
        mc = P.monte_carlo(days, risk, trail_intraday=False)
        mc_eod.append(mc)
        print(f"EOD-trail {risk*100:.3f}%: hist pass={row['pass_rate_resolved']:5.1f}% "
              f"MC pass={mc['pass_prob']:5.1f}% maxdd={mc['maxdd_breach_prob']:5.1f}%")

    reset_rows = []
    for risk in REPORT_LEVELS:
        results = [P.simulate(days, s, risk, phase2_reset=True) for s in range(len(days))]
        row = P.summarize(results, risk)
        row["variant"] = "phase2_reset"
        reset_rows.append(row)
        print(f"P2-reset {risk*100:.3f}%: pass={row['pass_rate_resolved']:5.1f}% "
              f"med_days={row['median_days_to_pass']:5.0f}")

    with open(os.path.join(out_dir, "historical.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(hist_rows[0].keys()))
        w.writeheader(); w.writerows(hist_rows)
    with open(os.path.join(out_dir, "monte_carlo.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(mc_rows[0].keys()))
        w.writeheader(); w.writerows(mc_rows)
    with open(os.path.join(out_dir, "historical_eod_trail.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(hist_eod[0].keys()))
        w.writeheader(); w.writerows(hist_eod)
    with open(os.path.join(out_dir, "monte_carlo_eod_trail.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(mc_eod[0].keys()))
        w.writeheader(); w.writerows(mc_eod)
    with open(os.path.join(out_dir, "historical_phase2_reset.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(reset_rows[0].keys()))
        w.writeheader(); w.writerows(reset_rows)

    for risk in (0.0005, 0.0010, 0.0015, 0.0025):
        m = P.monthly(days, risk)
        tagp = f"{risk*100:.2f}".replace(".", "")
        with open(os.path.join(out_dir, f"monthly_{tagp}pct.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["month", "usd_static"])
            for k in m:
                w.writerow([k, round(m[k], 2)])

    st = P.streaks(trades)
    summary = {
        "dataset": f"combo/{tag}",
        "window": {"start": str(days[0].d), "end": str(days[-1].d)},
        "rules": {
            "phase1_target_pct": 100 * P.P1_TARGET,
            "phase2_target_pct": 100 * P.P2_TARGET,
            "phase2_basis": "phase 1 ending balance (reset variant saved separately)",
            "daily_dd_pct": 100 * P.DAILY_DD,
            "daily_reference": "higher of balance/equity at 00:00 UTC",
            "max_dd_pct": 100 * P.MAX_DD,
            "max_dd_type": "trailing, offset fixed at 10% of initial balance",
            "max_dd_offset_$": P.MAX_DD_AMOUNT,
        },
        "trading_days": len(days),
        "trades": n_trades,
        "avg_trades_per_day": n_trades / len(days),
        "longest_losing_streak_trades": st,
        "historical": hist_rows,
        "monte_carlo": mc_rows,
        "historical_eod_trail": hist_eod,
        "monte_carlo_eod_trail": mc_eod,
        "historical_phase2_reset": reset_rows,
    }
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=float)
    print("longest losing streak (trades):", st)
    print(f"saved -> {out_dir}")


if __name__ == "__main__":
    main()
