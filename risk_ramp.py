"""Can the challenge be finished faster without breaking a rule?

Speed is fixed by the arithmetic:

    calendar days = 0.155 x 1.405 x DD_R / (0.10 x R_per_day)

where 0.155 is the total target (10% + 5% of the Phase 1 close), 1.405 is calendar
days per trading day (weekends), DD_R is the drawdown in R that the trailing floor
allows, and R_per_day is the book's edge. Since risk is capped at 10% / DD_R, the only
free lever is raising R_per_day without raising DD_R.

This script measures two candidate levers:

  1. A risk ramp: risk varies with progress toward the phase target instead of being
     flat. Early progress sits in the 1:1 barrier zone (need +10%, buffer 10%), late
     progress sits in a 10:1 zone (need +1%, buffer 9%). If failure risk is
     concentrated early, a low-early / high-late schedule can dominate a flat one.

  2. A higher flat risk, for reference on the same frontier.

Both are compared at equal Monte Carlo pass probability, which is the only fair test.
"""
from __future__ import annotations

import csv
import os
import sys
from dataclasses import dataclass

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prop_sim_portfolio as P

BASE = os.path.join(HERE, "results", "combo")
START = P.START_BALANCE
P1 = P.P1_TARGET
P2 = P.P2_TARGET


# ---------------------------------------------------------------- schedules

def risk_at(base: float, mode: str, k: float, p: float) -> float:
    """Risk per trade as a fraction of balance, given progress p in [0, 1]."""
    p = min(max(p, 0.0), 1.0)
    if mode == "flat":
        return base
    if mode == "lin":
        return base * (1.0 + k * p)
    if mode == "hyp":
        return base / max(0.25, 1.0 - k * p)
    raise ValueError(mode)


# ---------------------------------------------------------------- engine

@dataclass
class Res:
    status: str = "censored"
    days: int = 0
    n: int = 0
    max_dd: float = 0.0


def run(days: list[P.Day], start: int, base: float, mode: str = "flat",
        k: float = 0.0, trail_intraday: bool = True) -> Res:
    r = Res()
    balance = START
    peak = START
    ref = START
    target = START * (1 + P1)
    phase_start_balance = START
    phase = 1

    for i in range(start, len(days)):
        d = days[i]
        r.n += 1
        span = max(target - phase_start_balance, 1e-9)
        p = (balance - phase_start_balance) / span
        risk = risk_at(base, mode, k, p)
        rm = balance * risk

        low = balance + d.adv_min_r * rm
        high = balance + d.net_max_r * rm
        r.max_dd = max(r.max_dd, peak - low)

        if low < ref * (1 - P.DAILY_DD):
            r.status = "failed"; return r
        if low < peak - P.MAX_DD_AMOUNT:
            r.status = "failed"; return r

        balance += d.R * rm
        peak = max(peak, high, balance) if trail_intraday else max(peak, balance)
        if balance < peak - P.MAX_DD_AMOUNT:
            r.status = "failed"; return r

        if balance >= target:
            if phase == 1:
                phase = 2
                ref = balance
                phase_start_balance = balance
                target = balance * (1 + P2)
            else:
                r.status = "passed"
                return r
        else:
            ref = balance

    r.status = "censored"
    return r


CAL = 1.405


def historical(days, base, mode, k):
    res = [run(days, s, base, mode, k) for s in range(len(days))]
    done = [x for x in res if x.status != "censored"]
    passed = [x for x in done if x.status == "passed"]
    days_ = np.array([x.n * CAL for x in passed]) if passed else np.array([np.nan])
    return (len(done), len(passed), 100 * len(passed) / max(len(done), 1),
            float(np.median(days_)), float(np.percentile(days_, 90)))


def monte_carlo(days, base, mode, k, runs=4000, seed=11):
    rng = np.random.default_rng(seed)
    n = len(days)
    passed = failed = 0
    dpass = []
    for _ in range(runs):
        idx = rng.integers(0, n, n)
        path = [days[i] for i in idx]
        x = run(path, 0, base, mode, k)
        if x.status == "passed":
            passed += 1; dpass.append(x.n * CAL)
        elif x.status == "failed":
            failed += 1
    tot = passed + failed
    return 100 * passed / max(tot, 1), float(np.median(dpass)) if dpass else np.nan


# ---------------------------------------------------------------- main

def main() -> None:
    tag = sys.argv[1] if len(sys.argv) > 1 else "core"
    d = BASE if tag == "core" else os.path.join(BASE, tag)
    days = P.load_days(os.path.join(d, "days.csv"))
    mean_r = np.mean([x.R for x in days])
    cal = (days[-1].d - days[0].d).days / len(days)

    print(f"dataset combo/{tag}: {len(days)} days, {days[0].d} -> {days[-1].d}")
    print(f"R/day {mean_r:+.3f}   calendar/trading {cal:.3f}")
    print(f"\nspeed identity: calendar days = {100*(P1 + P2*(1+P1)):.1f}% x {cal:.2f}"
          f" x DD_R / (10% x R/day)")

    schedules = [
        ("flat 0.100%", 0.00100, "flat", 0.0),
        ("flat 0.1045%", 0.001045, "flat", 0.0),
        ("flat 0.125%", 0.00125, "flat", 0.0),
        ("flat 0.150%", 0.00150, "flat", 0.0),
        ("ramp 0.080% k=3", 0.00080, "lin", 3.0),
        ("ramp 0.100% k=2", 0.00100, "lin", 2.0),
        ("ramp 0.100% k=3", 0.00100, "lin", 3.0),
        ("ramp 0.125% k=2", 0.00125, "lin", 2.0),
        ("hyper 0.060% k=.85", 0.00060, "hyp", 0.85),
        ("hyper 0.075% k=.85", 0.00075, "hyp", 0.85),
        ("hyper 0.080% k=.90", 0.00080, "hyp", 0.90),
    ]

    print(f"\n{'schedule':<22}{'hist pass':>10}{'med d':>8}{'p90 d':>8}"
          f"{'MC pass':>9}{'MC med d':>10}")
    rows = []
    for label, base, mode, k in schedules:
        nd, np_, hp, md, p90 = historical(days, base, mode, k)
        mp, mmd = monte_carlo(days, base, mode, k)
        rows.append((label, hp, md, p90, mp, mmd))
        print(f"{label:<22}{hp:9.1f}%{md:8.0f}{p90:8.0f}{mp:8.1f}%{mmd:10.0f}")

    # frontier: what is the fastest schedule at each MC pass level?
    print("\nfastest schedule at or above each Monte Carlo pass level:")
    for level in (100.0, 99.5, 99.0, 98.0, 95.0):
        ok = [r for r in rows if r[4] >= level]
        if not ok:
            continue
        best = min(ok, key=lambda r: r[5])
        print(f"  {level:5.1f}%  {best[0]:<22} MC median {best[5]:.0f} calendar days")


if __name__ == "__main__":
    main()
