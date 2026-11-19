"""Deadline analysis: what does a 20-calendar-day pass actually cost?

The book needs +15.5% of the starting balance (10% Phase 1, then 5% of the Phase 1
close). At 1.405 calendar days per trading day, 20 calendar days is 14.2 trading days,
so the required return rate is 15.5% / 14.2 = 1.09% per trading day. With 3.159 R per
day that needs 0.345% risk per trade — 3.3x the 0.1045% cap the trailing drawdown
allows.

This script measures, for each risk level, the probability of actually passing inside
20 / 30 / 45 / 60 calendar days, on both the historical rolling starts and a Monte
Carlo resample. That probability is the real answer to "can I do it in 20 days".
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
START = P.START_BALANCE
P1 = P.P1_TARGET
P2 = P.P2_TARGET
TOTAL = P1 + P2 * (1 + P1)
CAL = 1.405
TARGET_DAYS = 20


def walk(adv, nmax, rr, risk, start: int = 0):
    """Return (status, trading_days). status 1=passed, 0=failed, -1=censored."""
    balance = START
    peak = START
    ref = START
    target = START * (1 + P1)
    phase = 1
    n = len(rr)
    for i in range(start, n):
        rm = balance * risk
        low = balance + adv[i] * rm
        high = balance + nmax[i] * rm
        if low < ref * (1 - P.DAILY_DD):
            return 0, i - start
        if low < peak - P.MAX_DD_AMOUNT:
            return 0, i - start
        balance += rr[i] * rm
        if high > peak:
            peak = high
        if balance > peak:
            peak = balance
        if balance < peak - P.MAX_DD_AMOUNT:
            return 0, i - start
        if balance >= target:
            if phase == 1:
                phase = 2
                ref = balance
                target = balance * (1 + P2)
            else:
                return 1, i - start + 1
        else:
            ref = balance
    return -1, n - start


def main() -> None:
    tag = sys.argv[1] if len(sys.argv) > 1 else "core"
    d = BASE if tag == "core" else os.path.join(BASE, tag)
    days = P.load_days(os.path.join(d, "days.csv"))
    adv = np.array([x.adv_min_r for x in days])
    nmax = np.array([x.net_max_r for x in days])
    rr = np.array([x.R for x in days])
    mean_r = rr.mean()

    print(f"dataset combo/{tag}: {len(days)} days, {days[0].d} -> {days[-1].d}")
    print(f"R/day {mean_r:+.3f}  calendar/trading {CAL:.3f}")
    print(f"target {100*TOTAL:.1f}% of start;  {TARGET_DAYS} calendar days = "
          f"{TARGET_DAYS/CAL:.1f} trading days -> needs "
          f"{100*TOTAL/(TARGET_DAYS/CAL):.2f}% per trading day")
    need = TOTAL / (TARGET_DAYS / CAL) / mean_r
    print(f"risk required for a 20-day median: {100*need:.3f}% per trade "
          f"({need/0.001045:.1f}x the 0.1045% trailing cap)\n")

    levels = (0.0010, 0.0015, 0.0020, 0.0025, 0.0030, 0.0035, 0.0040, 0.0050, 0.0075)
    rng = np.random.default_rng(3)
    n = len(days)
    mc_runs = int(sys.argv[2]) if len(sys.argv) > 2 else 1500

    print(f"{'risk':>7}{'pass':>8}{'med d':>7}{'fail d':>7}{'E[dur]':>8}"
          f"{'att.':>6}{'E[days]':>9}{'P<=20':>8}{'P<=30':>8}{'MC pass':>9}{'MC P<=20':>9}")
    for risk in levels:
        hist = [walk(adv, nmax, rr, risk, s) for s in range(n)]
        hp_done = [(st, k) for st, k in hist if st != -1]
        hp_pass = [k * CAL for st, k in hp_done if st == 1]
        hp_fail = [k * CAL for st, k in hp_done if st == 0]
        p = len(hp_pass) / max(len(hp_done), 1)
        h_med = np.median(hp_pass) if hp_pass else np.nan
        f_med = np.median(hp_fail) if hp_fail else np.nan
        e_dur = (np.mean(hp_pass) * p + np.mean(hp_fail) * (1 - p)) if hp_fail else np.mean(hp_pass)
        e_pass = e_dur / p if p > 0 else np.nan
        h_p20 = 100 * sum(1 for x in hp_pass if x <= TARGET_DAYS) / max(len(hp_done), 1)
        h_p30 = 100 * sum(1 for x in hp_pass if x <= 30) / max(len(hp_done), 1)

        mc_pass = []
        mc_fail = 0
        for _ in range(mc_runs):
            idx = rng.integers(0, n, n)
            st, k = walk(adv[idx], nmax[idx], rr[idx], risk)
            if st == 1:
                mc_pass.append(k * CAL)
            elif st == 0:
                mc_fail += 1
        tot = len(mc_pass) + mc_fail
        m_pass = 100 * len(mc_pass) / max(tot, 1)
        m_p20 = 100 * sum(1 for x in mc_pass if x <= TARGET_DAYS) / max(tot, 1)

        print(f"{100*risk:6.2f}%{100*p:7.1f}%{h_med:7.0f}{f_med:7.0f}{e_dur:8.0f}"
              f"{1/p:6.1f}{e_pass:9.0f}{h_p20:7.1f}%{h_p30:7.1f}%"
              f"{m_pass:8.1f}%{m_p20:8.1f}%")

    print(f"\nP<=N is the chance the whole challenge (both phases) finishes inside N")
    print(f"calendar days, measured over every historical start, so it already")
    print(f"includes the starts that fail.")


if __name__ == "__main__":
    main()
