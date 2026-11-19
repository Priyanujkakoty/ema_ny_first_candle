"""Prop-firm evaluation simulator for the buffer-1.0 NY range-breakout strategy.

Rules used (AquaFunded 2-Step Pro, verified 2026-11-20 on aquafunded.com/forex-rules
and help.aquafunded.com):
  - Phase 1 target 8% of initial balance, Phase 2 target 5% (fresh start).
  - Daily drawdown 4% of the previous day's highest balance/equity, reset 00:00 UTC,
    floating P&L included.
  - Max drawdown 8% of initial balance, fixed, floating P&L included. No trailing.
  - No time limit, no consistency rule on 2-Step evaluation, no max lot size.
  - Margin usage must stay below 80% of available margin; leverage 1:100 evaluation.
  - 2-Step Pro evaluation has no minimum trading days (funded stage needs 3).

Strategy is unchanged: bias ORB, range stop, 16:00 ET exit, buffer 1.0 pip,
0.8 pip round-trip cost already embedded in each trade's R.
"""
from __future__ import annotations

import csv
import json
import os
import random
import sys
from dataclasses import dataclass, field

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as b
import orb

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "prop")
FILES = [
    rf"E:\FOREX INTEL\market_data\EURUSD\1m\yearly\eurusd_1m_{y}.csv"
    for y in range(2021, 2027)
]

START_BALANCE = 5000.0
P1_TARGET = 0.08
P2_TARGET = 0.05
DAILY_DD = 0.04
MAX_DD = 0.08
MAX_DD_FLOOR = START_BALANCE * (1 - MAX_DD)
PIP_VALUE_PER_LOT = 10.0
CONTRACT = 100_000.0
LEVERAGE = 100.0
MARGIN_CAP = 0.80
RISK_LEVELS = (0.0025, 0.005, 0.0075, 0.01)
YEARS = 5


# ---------------------------------------------------------------- trades

def load_trades() -> list[dict]:
    df = b.load_m1(FILES)
    df = b.add_indicators(df)
    idx = b.et_index(df)
    trend = b.build_trend(df, idx, tf_min=15)
    last = int(df["timestamp"].iloc[-1])
    trades = [
        t
        for t in orb.run_orb(
            df, idx, trend,
            use_bias=True, stop_mode="range", exit_mode="flat", buffer_pips=1.0,
        )
        if t["entry_ms"] >= last - YEARS * 365 * 86400_000
    ]
    trades.sort(key=lambda t: t["entry_ms"])

    h = df["high"].to_numpy(); l = df["low"].to_numpy()
    ts = df["timestamp"].to_numpy()
    for t in trades:
        i = int(np.searchsorted(ts, t["entry_ms"]))
        j = int(np.searchsorted(ts, t["exit_ms"]))
        d = 1 if t["dir"] == "long" else -1
        stop_dist = t["stop_pips"] * b.PIP
        hi = h[i + 1:j + 1].max() if j > i else h[i]
        lo = l[i + 1:j + 1].min() if j > i else l[i]
        mfe = (d * (hi - t["entry"]) / stop_dist) if d > 0 else (d * (t["entry"] - lo) / stop_dist)
        mae = (d * (lo - t["entry"]) / stop_dist) if d > 0 else (d * (t["entry"] - hi) / stop_dist)
        t["mfe_r"] = max(0.0, float(mfe))
        # floating loss cannot exceed the stop (bad data ticks aside); gap fills stay
        t["mae_r"] = min(0.0, max(float(mae), -1.0), float(t["R"]))
    return trades


# ---------------------------------------------------------------- engine

@dataclass
class SimResult:
    status: str = "censored"          # passed / failed / censored
    fail_reason: str | None = None
    phase: int = 1
    trades_used: int = 0
    days: int = 0
    max_daily_dd: float = 0.0         # in dollars
    max_total_dd: float = 0.0         # in dollars
    end_balance: float = START_BALANCE
    phase1_trades: int = 0
    phase2_trades: int = 0
    margin_violations: int = 0


def simulate(trades: list[dict], start_idx: int, risk_pct: float) -> SimResult:
    res = SimResult()
    phase = 1
    balance = START_BALANCE
    phase_start = start_idx
    prev_day_high = START_BALANCE
    peak = START_BALANCE
    target = START_BALANCE * (1 + (P1_TARGET if phase == 1 else P2_TARGET))

    for i in range(start_idx, len(trades)):
        t = trades[i]
        risk_money = balance * risk_pct
        lots = risk_money / (t["stop_pips"] * PIP_VALUE_PER_LOT)
        margin = lots * CONTRACT / LEVERAGE
        if margin > MARGIN_CAP * balance:
            res.margin_violations += 1
            res.status = "failed"
            res.fail_reason = "margin"
            res.end_balance = balance
            return res

        low_equity = balance + min(0.0, t["mae_r"]) * risk_money
        day_floor = balance - DAILY_DD * prev_day_high
        daily_dd = balance - low_equity
        res.max_daily_dd = max(res.max_daily_dd, daily_dd)
        res.max_total_dd = max(res.max_total_dd, peak - low_equity)

        if low_equity < day_floor:
            res.status = "failed"; res.fail_reason = "daily_dd"
            res.end_balance = low_equity
            return res
        if low_equity < MAX_DD_FLOOR:
            res.status = "failed"; res.fail_reason = "max_dd"
            res.end_balance = low_equity
            return res

        balance_before = balance
        balance += t["R"] * risk_money
        res.trades_used += 1
        if phase == 1:
            res.phase1_trades += 1
        else:
            res.phase2_trades += 1
        peak = max(peak, balance)
        res.max_total_dd = max(res.max_total_dd, peak - balance)
        day_high = balance_before + t["mfe_r"] * risk_money
        prev_day_high = max(prev_day_high, day_high)

        if balance < MAX_DD_FLOOR:
            res.status = "failed"; res.fail_reason = "max_dd"
            res.end_balance = balance
            return res

        if balance >= target:
            if phase == 1:
                phase = 2
                res.phase = 2
                balance = START_BALANCE
                peak = START_BALANCE
                prev_day_high = START_BALANCE
                target = START_BALANCE * (1 + P2_TARGET)
                res.days = (t["entry_ms"] - trades[phase_start]["entry_ms"]) // 86400_000
                res.phase1_trades = res.trades_used
                phase_start = i + 1
            else:
                res.status = "passed"
                res.end_balance = balance
                res.days = (t["entry_ms"] - trades[start_idx]["entry_ms"]) // 86400_000
                return res

    res.status = "censored"
    res.end_balance = balance
    return res


def summarize_historical(results: list[SimResult], risk_pct: float) -> dict:
    resolved = [r for r in results if r.status != "censored"]
    passed = [r for r in resolved if r.status == "passed"]
    p1 = [r for r in resolved if r.phase1_trades > 0 or r.status == "passed"]
    fails = [r for r in resolved if r.status == "failed"]
    reasons = {}
    for r in fails:
        reasons[r.fail_reason] = reasons.get(r.fail_reason, 0) + 1
    days = [r.days for r in passed if r.days > 0]

    return {
        "risk_pct": risk_pct,
        "starts": len(results),
        "resolved": len(resolved),
        "censored": len(results) - len(resolved),
        "passed": len(passed),
        "failed": len(fails),
        "pass_rate_resolved": 100 * len(passed) / len(resolved) if resolved else 0.0,
        "pass_rate_all": 100 * len(passed) / len(results) if results else 0.0,
        "fail_daily_dd": reasons.get("daily_dd", 0),
        "fail_max_dd": reasons.get("max_dd", 0),
        "fail_margin": reasons.get("margin", 0),
        "avg_days_to_pass": float(np.mean(days)) if days else 0.0,
        "median_days_to_pass": float(np.median(days)) if days else 0.0,
        "max_daily_dd_$": max((r.max_daily_dd for r in results), default=0.0),
        "max_total_dd_$": max((r.max_total_dd for r in results), default=0.0),
        "max_margin_violations": sum(r.margin_violations for r in results),
    }


def phase_stats(results: list[SimResult]) -> dict:
    resolved = [r for r in results if r.status != "censored"]
    p1_pass = [r for r in resolved if r.status == "passed" or r.phase == 2]
    p1 = len(p1_pass) / len(resolved) if resolved else 0.0
    p1_resolved = [r for r in resolved if r.phase == 2 or r.status == "passed"]
    p2 = sum(1 for r in p1_resolved if r.status == "passed") / len(p1_resolved) if p1_resolved else 0.0
    return {"phase1_rate": 100 * p1, "phase2_rate": 100 * p2}


# ---------------------------------------------------------------- monte carlo

def monte_carlo(trades: list[dict], risk_pct: float, n: int = 20_000, seed: int = 7) -> dict:
    rng = random.Random(seed)
    ntr = len(trades)
    passed = daily = maxdd = margin = censored = 0
    days = []
    dd_pcts = []
    for _ in range(n):
        phase = 1
        balance = START_BALANCE
        prev_high = START_BALANCE
        peak = START_BALANCE
        target = START_BALANCE * (1 + (P1_TARGET if phase == 1 else P2_TARGET))
        worst_dd = 0.0
        outcome = None
        for k in range(400):
            t = trades[rng.randrange(ntr)]
            risk_money = balance * risk_pct
            lots = risk_money / (t["stop_pips"] * PIP_VALUE_PER_LOT)
            if lots * CONTRACT / LEVERAGE > MARGIN_CAP * balance:
                outcome = "margin"; break
            low = balance + min(0.0, t["mae_r"]) * risk_money
            worst_dd = max(worst_dd, peak - low)
            if low < balance - DAILY_DD * prev_high:
                outcome = "daily"; break
            if low < MAX_DD_FLOOR:
                outcome = "maxdd"; break
            balance += t["R"] * risk_money
            peak = max(peak, balance)
            worst_dd = max(worst_dd, peak - balance)
            prev_high = max(prev_high, balance + t["mfe_r"] * risk_money)
            if balance < MAX_DD_FLOOR:
                outcome = "maxdd"; break
            if balance >= target:
                if phase == 1:
                    phase = 2
                    balance = START_BALANCE
                    peak = START_BALANCE
                    prev_high = START_BALANCE
                    target = START_BALANCE * (1 + P2_TARGET)
                else:
                    outcome = "passed"; break
        if outcome == "passed":
            passed += 1; days.append(k + 1)
        elif outcome == "daily":
            daily += 1
        elif outcome == "maxdd":
            maxdd += 1
        elif outcome == "margin":
            margin += 1
        else:
            censored += 1
        dd_pcts.append(100 * worst_dd / START_BALANCE)
    return {
        "risk_pct": risk_pct,
        "runs": n,
        "pass_prob": 100 * passed / n,
        "daily_breach_prob": 100 * daily / n,
        "maxdd_breach_prob": 100 * maxdd / n,
        "margin_breach_prob": 100 * margin / n,
        "censored_prob": 100 * censored / n,
        "median_trades_to_pass": float(np.median(days)) if days else 0.0,
        "dd_p50": float(np.percentile(dd_pcts, 50)),
        "dd_p95": float(np.percentile(dd_pcts, 95)),
        "dd_p99": float(np.percentile(dd_pcts, 99)),
        "dd_worst": float(np.max(dd_pcts)),
    }


# ---------------------------------------------------------------- main

def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    trades = load_trades()
    print(f"trades: {len(trades)}  {trades[0]['date']} -> {trades[-1]['date']}")

    hist_rows = []
    for risk in RISK_LEVELS:
        results = [simulate(trades, s, risk) for s in range(len(trades))]
        row = summarize_historical(results, risk)
        row.update(phase_stats(results))
        hist_rows.append(row)
        print(
            f"risk {risk*100:.2f}%: starts={row['starts']} resolved={row['resolved']} "
            f"pass={row['passed']} ({row['pass_rate_resolved']:.1f}%) "
            f"p1={row['phase1_rate']:.1f}% p2={row['phase2_rate']:.1f}% "
            f"med_days={row['median_days_to_pass']:.0f} "
            f"dailyDD=${row['max_daily_dd_$']:.0f} totalDD=${row['max_total_dd_$']:.0f} "
            f"fails={row['failed']} (daily {row['fail_daily_dd']}, max {row['fail_max_dd']})"
        )

    mc_rows = []
    for risk in RISK_LEVELS:
        row = monte_carlo(trades, risk)
        mc_rows.append(row)
        print(
            f"MC {risk*100:.2f}%: pass={row['pass_prob']:.1f}% daily={row['daily_breach_prob']:.1f}% "
            f"maxdd={row['maxdd_breach_prob']:.1f}% dd p95={row['dd_p95']:.1f}% "
            f"p99={row['dd_p99']:.1f}% worst={row['dd_worst']:.1f}%"
        )

    with open(os.path.join(OUT, "historical.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(hist_rows[0].keys()))
        w.writeheader(); w.writerows(hist_rows)
    with open(os.path.join(OUT, "monte_carlo.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(mc_rows[0].keys()))
        w.writeheader(); w.writerows(mc_rows)
    with open(os.path.join(OUT, "trades_with_excursions.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(trades[0].keys()))
        w.writeheader(); w.writerows(trades)

    # monthly returns at 0.5% risk on a static $5k
    months: dict[str, float] = {}
    for t in trades:
        months[t["date"][:7]] = months.get(t["date"][:7], 0.0) + t["R"] * START_BALANCE * 0.005
    with open(os.path.join(OUT, "monthly_05pct.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["month", "usd"])
        for m in sorted(months):
            w.writerow([m, round(months[m], 2)])
    print("monthly at 0.5%:", {m: round(v) for m, v in sorted(months.items())[-12:]})
    print(f"saved -> {OUT}")


if __name__ == "__main__":
    main()
