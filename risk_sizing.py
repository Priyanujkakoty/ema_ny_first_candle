"""Position sizing from first principles: what risk per trade is fastest without breaking a rule.

Method
  1. Measure the book: R per day, worst floating day, drawdown in R.
  2. Convert each AquaFunded 2-Step Pro rule into a hard cap on risk per trade.
  3. Because risk is a percentage of the CURRENT balance, the cap is found by
     simulation, not by a static multiplication.
  4. Speed follows from R per day.
"""
from __future__ import annotations

import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prop_sim_portfolio as P

BASE = os.path.join(HERE, "results", "combo")
START = 5_000.0
P1 = 0.10          # phase 1 target
P2 = 0.05          # phase 2 target, measured on the phase 1 close
TOTAL = P1 + P2 * (1 + P1)      # 15.5% of the initial balance


def failures(days, risk: float) -> int:
    return sum(1 for s in range(len(days)) if P.simulate(days, s, risk).status == "failed")


def envelope_dd(days) -> tuple[float, float]:
    """Drawdown in R units with floating P&L, rm = 1 (no compounding)."""
    bal = peak = worst = 0.0
    worst_day = 0.0
    for d in days:
        low = bal + d.adv_min_r
        high = bal + d.net_max_r
        worst = max(worst, peak - low)
        worst_day = min(worst_day, d.adv_min_r)
        bal += d.R
        peak = max(peak, high, bal)
        worst = max(worst, peak - bal)
    return worst, worst_day


def main() -> None:
    tag = sys.argv[1] if len(sys.argv) > 1 else "core"
    data_dir = BASE if tag == "core" else os.path.join(BASE, tag)
    days = P.load_days(os.path.join(data_dir, "days.csv"))
    r = np.array([d.R for d in days])
    mean_r, sd_r = r.mean(), r.std(ddof=1)
    cal_per_trading = (days[-1].d - days[0].d).days / len(days)
    dd_intraday, worst_day = envelope_dd(days)

    eq = peak = worst_close = 0.0
    for x in r:
        eq += x
        peak = max(peak, eq)
        worst_close = min(worst_close, eq - peak)

    print(f"dataset combo/{tag}: {len(days)} days, {days[0].d} -> {days[-1].d}")
    print(f"trades/day            {sum(d.trades for d in days)/len(days):.2f}")
    print(f"R per day             mean {mean_r:+.3f}  sd {sd_r:.3f}  "
          f"worst floating day {worst_day:+.2f}")
    print(f"max drawdown          {worst_close:.1f}R on daily closes, "
          f"{dd_intraday:.1f}R including floating P&L")
    print(f"calendar per trading day {cal_per_trading:.3f}")

    # ---- rule caps, first pass (static, no compounding)
    print("\nrule -> maximum risk per trade (static approximation)")
    static = {
        "daily 5%: 5% / worst floating day": 0.05 / abs(worst_day),
        "trailing 10%: 10% / envelope drawdown": 0.10 / dd_intraday,
        "margin 80%: 80% / 19.8% at 0.10%": 0.80 / 0.198,
    }
    for k, v in sorted(static.items(), key=lambda kv: kv[1]):
        print(f"  {k:<40} {100*v:7.3f}%")

    # ---- exact cap: highest risk with zero historical failures
    lo, hi = 0.0005, 0.0015
    for _ in range(10):
        mid = (lo + hi) / 2
        if failures(days, mid) == 0:
            lo = mid
        else:
            hi = mid
    cap = lo
    print(f"\nexact cap (zero historical failures, compounding risk): {100*cap:.4f}%")

    # ---- speed
    print(f"\nspeed: phase 1 +10%, phase 2 +5% of the phase 1 close = {100*TOTAL:.1f}% total")
    print(f"trading days = {100*TOTAL:.1f}% / ({mean_r:.3f}R/day x risk), "
          f"calendar = x {cal_per_trading:.2f}\n")

    hist = {round(float(x["risk_pct"]), 6): x
            for x in csv.DictReader(open(os.path.join(data_dir, "prop", "historical.csv"),
                                         encoding="utf-8"))}
    mc = {round(float(x["risk_pct"]), 6): x
          for x in csv.DictReader(open(os.path.join(data_dir, "prop", "monte_carlo.csv"),
                                       encoding="utf-8"))}

    print(f"{'risk':>7} {'maxDD $':>8} {'cap used':>9} {'trading d':>10} {'calendar d':>11} "
          f"{'MC pass':>8} {'MC breach':>10} {'exp. days':>10}")
    for risk in (0.0005, 0.00075, 0.0010, 0.0011, 0.00125, 0.0015, 0.0020, 0.0025):
        tdays = TOTAL / (mean_r * risk)
        cdays = tdays * cal_per_trading
        m, h = mc.get(risk), hist.get(risk)
        pass_p = float(m["pass_prob"]) if m else float("nan")
        breach = float(m["maxdd_breach_prob"]) if m else float("nan")
        dd_usd = float(h["max_total_dd_$"]) if h else float("nan")
        exp = cdays / (pass_p / 100) if pass_p == pass_p and pass_p > 0 else float("nan")
        mark = " <cap" if abs(risk - cap) < 0.00004 else ""
        print(f"{100*risk:6.3f}% {dd_usd:8.0f} {100*risk/cap:8.0f}% {tdays:10.0f} "
              f"{cdays:11.0f} {pass_p:7.1f}% {breach:9.2f}% {exp:10.0f}{mark}")

    print(f"\nanswer: {100*cap:.2f}% per trade is the fastest setting that never breaks a")
    print("rule on the 2016-2026 path. Round down to 0.10% for a real account.")
    print("0.075% if you want the Monte Carlo worst case to stay under 10% as well.")


if __name__ == "__main__":
    main()
