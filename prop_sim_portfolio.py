"""Prop-firm evaluation simulator for the 3-pair NY range-breakout portfolio.

Rules used — AquaFunded 2-Step Pro, from the official model page
https://help.aquafunded.com/en/articles/15281229-2-step-pro (read 2026-11-20):

  Phase 1 target 10%, Phase 2 target 5% (measured from the Phase 2 starting balance).
  Daily drawdown 5% of the higher of balance/equity at 00:00 UTC (previous day's close).
  Max total loss 10% TRAILING: floor = highest balance/equity - 10% of initial balance
  ($500 on a $5,000 account). Trails up with new equity highs, never down.
  Floating P&L counts toward both limits. No time limit. No minimum trading days in
  evaluation. Consistency rule (50%) applies to the funded stage only. No max lot.
  Leverage 1:100 evaluation.

Portfolio: EURUSD + GBPUSD + AUDJPY, max 3 trades/day (one per pair).
Intraday equity uses each trade's minute-level excursion, summed across open trades.
Risk per trade = risk% x current balance. Position size uses each trade's real pip
value (JPY pairs converted with the USDJPY rate at entry).
"""
from __future__ import annotations

import csv
import json
import os
import random
import sys
from dataclasses import dataclass
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

DATA = os.path.join(HERE, "results", "multi")
OUT = os.path.join(HERE, "results", "multi", "prop")

START_BALANCE = 5000.0
P1_TARGET = 0.10
P2_TARGET = 0.05
DAILY_DD = 0.05
MAX_DD = 0.10
MAX_DD_AMOUNT = START_BALANCE * MAX_DD      # trailing offset: $500
LEVERAGE = 100.0
MARGIN_CAP = 0.80
CONTRACT = 100_000.0
PHASE2_RESET = False                        # False = Phase 2 starts from Phase 1 close

RISK_LEVELS = (0.0010, 0.0015, 0.0020, 0.0025, 0.0050, 0.0075, 0.0100)
REPORT_LEVELS = (0.0025, 0.0050, 0.0075, 0.0100)


@dataclass
class Day:
    d: date
    trades: int
    adv_min_r: float
    fav_max_r: float
    net_max_r: float
    net_min_r: float
    R: float


def load_days(path: str | None = None) -> list[Day]:
    path = path or os.path.join(DATA, "days.csv")
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(Day(
                d=date.fromisoformat(r["date"]),
                trades=int(r["trades"]),
                adv_min_r=float(r["adv_min_r"]),
                fav_max_r=float(r["fav_max_r"]),
                net_max_r=float(r.get("net_max_r", r["fav_max_r"])),
                net_min_r=float(r.get("net_min_r", r["adv_min_r"])),
                R=float(r["R"]),
            ))
    rows.sort(key=lambda x: x.d)
    return rows


def load_trades() -> list[dict]:
    with open(os.path.join(DATA, "trades_portfolio.csv"), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------- engine

@dataclass
class SimResult:
    status: str = "censored"
    fail_reason: str | None = None
    phase: int = 1
    days_used: int = 0
    trades_used: int = 0
    max_daily_dd: float = 0.0
    max_total_dd: float = 0.0
    end_balance: float = START_BALANCE
    start: date | None = None
    end: date | None = None


def simulate(days: list[Day], start_idx: int, risk: float,
             phase2_reset: bool = PHASE2_RESET,
             trail_intraday: bool = True) -> SimResult:
    res = SimResult(start=days[start_idx].d)
    phase = 1
    balance = START_BALANCE
    peak = START_BALANCE                    # highest balance/equity
    ref = START_BALANCE                     # 00:00 UTC reference for the daily limit
    target = START_BALANCE * (1 + P1_TARGET)
    phase_start = start_idx

    for i in range(start_idx, len(days)):
        day = days[i]
        rm = balance * risk
        low = balance + day.adv_min_r * rm
        high = balance + day.net_max_r * rm
        res.days_used = (day.d - days[start_idx].d).days
        res.trades_used += day.trades

        res.max_daily_dd = max(res.max_daily_dd, ref - low)
        res.max_total_dd = max(res.max_total_dd, peak - low)

        if low < ref * (1 - DAILY_DD):
            res.status = "failed"; res.fail_reason = "daily_dd"; res.end_balance = low
            res.end = day.d
            return res
        if low < peak - MAX_DD_AMOUNT:
            res.status = "failed"; res.fail_reason = "max_dd"; res.end_balance = low
            res.end = day.d
            return res

        balance += day.R * rm
        peak = max(peak, high, balance) if trail_intraday else max(peak, balance)
        res.max_total_dd = max(res.max_total_dd, peak - balance)

        if balance < peak - MAX_DD_AMOUNT:
            res.status = "failed"; res.fail_reason = "max_dd"; res.end_balance = balance
            res.end = day.d
            return res

        if balance >= target:
            if phase == 1:
                phase = 2
                res.phase = 2
                if phase2_reset:
                    balance = START_BALANCE
                    peak = START_BALANCE
                ref = balance
                target = balance * (1 + P2_TARGET)
                phase_start = i + 1
            else:
                res.status = "passed"; res.end_balance = balance; res.end = day.d
                res.days_used = (day.d - days[start_idx].d).days
                return res
        else:
            ref = balance

    res.end_balance = balance
    res.end = days[-1].d
    return res


def summarize(results: list[SimResult], risk: float) -> dict:
    resolved = [r for r in results if r.status != "censored"]
    passed = [r for r in resolved if r.status == "passed"]
    fails = [r for r in resolved if r.status == "failed"]
    reasons: dict[str, int] = {}
    for r in fails:
        reasons[r.fail_reason] = reasons.get(r.fail_reason, 0) + 1

    days = [r.days_used for r in passed]
    p1_res = [r for r in resolved if r.phase == 2 or r.status == "passed"]
    p1_rate = 100 * len(p1_res) / len(resolved) if resolved else 0.0
    p2_rate = 100 * len(passed) / len(p1_res) if p1_res else 0.0

    return {
        "risk_pct": risk,
        "starts": len(results),
        "resolved": len(resolved),
        "censored": len(results) - len(resolved),
        "passed": len(passed),
        "failed": len(fails),
        "pass_rate_resolved": 100 * len(passed) / len(resolved) if resolved else 0.0,
        "pass_rate_all": 100 * len(passed) / len(results) if results else 0.0,
        "fail_daily_dd": reasons.get("daily_dd", 0),
        "fail_max_dd": reasons.get("max_dd", 0),
        "phase1_rate": p1_rate,
        "phase2_rate": p2_rate,
        "avg_days_to_pass": float(np.mean(days)) if days else 0.0,
        "median_days_to_pass": float(np.median(days)) if days else 0.0,
        "p90_days_to_pass": float(np.percentile(days, 90)) if days else 0.0,
        "max_daily_dd_$": max((r.max_daily_dd for r in results), default=0.0),
        "max_total_dd_$": max((r.max_total_dd for r in results), default=0.0),
        "max_total_dd_pct": 100 * max((r.max_total_dd for r in results), default=0.0) / START_BALANCE,
        "median_total_dd_$": float(np.median([r.max_total_dd for r in resolved])) if resolved else 0.0,
    }


# ---------------------------------------------------------------- monte carlo

def monte_carlo(days: list[Day], risk: float, n: int = 20_000, seed: int = 11,
                phase2_reset: bool = PHASE2_RESET,
                trail_intraday: bool = True) -> dict:
    rng = random.Random(seed)
    nd = len(days)
    passed = daily = maxdd = censored = 0
    days_to_pass = []
    dd_pcts = []
    for _ in range(n):
        phase = 1
        balance = START_BALANCE
        peak = START_BALANCE
        ref = START_BALANCE
        target = START_BALANCE * (1 + P1_TARGET)
        worst = 0.0
        outcome = None
        for k in range(800):
            day = days[rng.randrange(nd)]
            rm = balance * risk
            low = balance + day.adv_min_r * rm
            high = balance + day.net_max_r * rm
            worst = max(worst, peak - low)
            if low < ref * (1 - DAILY_DD):
                outcome = "daily"; break
            if low < peak - MAX_DD_AMOUNT:
                outcome = "maxdd"; break
            balance += day.R * rm
            peak = max(peak, high, balance) if trail_intraday else max(peak, balance)
            worst = max(worst, peak - balance)
            if balance < peak - MAX_DD_AMOUNT:
                outcome = "maxdd"; break
            if balance >= target:
                if phase == 1:
                    phase = 2
                    if phase2_reset:
                        balance = START_BALANCE
                        peak = START_BALANCE
                    ref = balance
                    target = balance * (1 + P2_TARGET)
                else:
                    outcome = "passed"; break
            else:
                ref = balance
        if outcome == "passed":
            passed += 1; days_to_pass.append(k + 1)
        elif outcome == "daily":
            daily += 1
        elif outcome == "maxdd":
            maxdd += 1
        else:
            censored += 1
        dd_pcts.append(100 * worst / START_BALANCE)
    return {
        "risk_pct": risk,
        "runs": n,
        "pass_prob": 100 * passed / n,
        "daily_breach_prob": 100 * daily / n,
        "maxdd_breach_prob": 100 * maxdd / n,
        "censored_prob": 100 * censored / n,
        "median_trading_days_to_pass": float(np.median(days_to_pass)) if days_to_pass else 0.0,
        "dd_p50": float(np.percentile(dd_pcts, 50)),
        "dd_p95": float(np.percentile(dd_pcts, 95)),
        "dd_p99": float(np.percentile(dd_pcts, 99)),
        "dd_worst": float(np.max(dd_pcts)),
    }


# ---------------------------------------------------------------- streaks / monthly

def streaks(trades: list[dict]) -> int:
    tr = sorted(trades, key=lambda t: int(t["exit_ms"]))
    best = cur = 0
    for t in tr:
        if float(t["R"]) <= 0:
            cur += 1; best = max(best, cur)
        else:
            cur = 0
    return best


def monthly(days: list[Day], risk: float) -> dict[str, float]:
    out: dict[str, float] = {}
    for d in days:
        m = d.d.isoformat()[:7]
        out[m] = out.get(m, 0.0) + d.R * START_BALANCE * risk
    return dict(sorted(out.items()))


def margin_check(trades: list[dict], risk: float) -> dict:
    """Worst single-position margin usage at the tested risk level."""
    worst = 0.0
    worst_t = None
    for t in trades:
        stop_pips = float(t["stop_pips"])
        pip_value = float(t["pip_value"])
        risk_money = START_BALANCE * risk
        lots = risk_money / (stop_pips * pip_value)
        margin = lots * CONTRACT / LEVERAGE
        pct = 100 * margin / START_BALANCE
        if pct > worst:
            worst, worst_t = pct, t
    return {
        "risk_pct": risk,
        "max_margin_usage_pct": worst,
        "pair": worst_t["pair"] if worst_t else None,
        "stop_pips": float(worst_t["stop_pips"]) if worst_t else None,
    }


def main() -> None:
    stem = sys.argv[1] if len(sys.argv) > 1 else "days"
    out_dir = OUT if stem == "days" else os.path.join(OUT, stem)
    os.makedirs(out_dir, exist_ok=True)
    days = load_days(os.path.join(DATA, f"{stem}.csv"))
    trades = load_trades()
    if stem != "days":
        pair = stem.replace("days_", "")
        trades = [t for t in trades if t["pair"] == pair]
    n_trades = sum(d.trades for d in days)
    print(f"dataset: {stem}  days: {len(days)}  {days[0].d} -> {days[-1].d}")
    print(f"trades: {n_trades}  avg/day={n_trades/len(days):.2f}  "
          f"max/day={max(d.trades for d in days)}")

    hist_rows = []
    mc_rows = []
    for risk in RISK_LEVELS:
        results = [simulate(days, s, risk, trail_intraday=True) for s in range(len(days))]
        row = summarize(results, risk)
        hist_rows.append(row)
        mark = "*" if risk in REPORT_LEVELS else " "
        print(f"{mark}risk {risk*100:.2f}%: resolved={row['resolved']:>4} pass={row['passed']:>4} "
              f"({row['pass_rate_resolved']:5.1f}%) p1={row['phase1_rate']:5.1f}% p2={row['phase2_rate']:5.1f}% "
              f"med_days={row['median_days_to_pass']:5.0f} maxDaily=${row['max_daily_dd_$']:5.0f} "
              f"maxDD=${row['max_total_dd_$']:5.0f} "
              f"fails={row['failed']} daily={row['fail_daily_dd']} max={row['fail_max_dd']}")

        mc = monte_carlo(days, risk, trail_intraday=True)
        mc_rows.append(mc)
        print(f"MC {risk*100:.2f}%: pass={mc['pass_prob']:5.1f}% daily={mc['daily_breach_prob']:4.1f}% "
              f"maxdd={mc['maxdd_breach_prob']:5.1f}% dd p95={mc['dd_p95']:5.1f}% "
              f"p99={mc['dd_p99']:5.1f}% worst={mc['dd_worst']:5.1f}%")

    # sensitivity: trailing drawdown updated on closed balance only
    hist_eod = []
    mc_eod = []
    for risk in RISK_LEVELS:
        results = [simulate(days, s, risk, trail_intraday=False) for s in range(len(days))]
        row = summarize(results, risk)
        hist_eod.append(row)
        mc = monte_carlo(days, risk, trail_intraday=False)
        mc_eod.append(mc)
        print(f"EOD-trail {risk*100:.2f}%: hist pass={row['pass_rate_resolved']:5.1f}% "
              f"MC pass={mc['pass_prob']:5.1f}% maxdd={mc['maxdd_breach_prob']:5.1f}%")

    # Phase 2 reset sensitivity (Phase 2 restarts at $5,000)
    reset_rows = []
    for risk in REPORT_LEVELS:
        results = [simulate(days, s, risk, phase2_reset=True) for s in range(len(days))]
        row = summarize(results, risk)
        row["variant"] = "phase2_reset"
        reset_rows.append(row)
        print(f"P2-reset {risk*100:.2f}%: pass={row['pass_rate_resolved']:5.1f}% "
              f"med_days={row['median_days_to_pass']:5.0f}")

    with open(os.path.join(out_dir, "historical.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(hist_rows[0].keys()))
        w.writeheader(); w.writerows(hist_rows)
    with open(os.path.join(out_dir, "monte_carlo.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(mc_rows[0].keys()))
        w.writeheader(); w.writerows(mc_rows)
    with open(os.path.join(out_dir, "historical_phase2_reset.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(reset_rows[0].keys()))
        w.writeheader(); w.writerows(reset_rows)
    with open(os.path.join(out_dir, "historical_eod_trail.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(hist_eod[0].keys()))
        w.writeheader(); w.writerows(hist_eod)
    with open(os.path.join(out_dir, "monte_carlo_eod_trail.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(mc_eod[0].keys()))
        w.writeheader(); w.writerows(mc_eod)

    for risk in (0.0010, 0.0015, 0.0025, 0.0050):
        m = monthly(days, risk)
        tag = f"{risk*100:.2f}".replace(".", "")
        with open(os.path.join(out_dir, f"monthly_{tag}pct.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["month", "usd_static"])
            for k in m:
                w.writerow([k, round(m[k], 2)])

    margins = [margin_check(trades, r) for r in REPORT_LEVELS]
    for m in margins:
        print(f"margin @ {m['risk_pct']*100:.2f}%: max usage {m['max_margin_usage_pct']:.1f}% "
              f"({m['pair']}, {m['stop_pips']} pips)")

    st = streaks(trades)
    summary = {
        "window": {"start": str(days[0].d), "end": str(days[-1].d)},
        "rules": {
            "phase1_target_pct": 100 * P1_TARGET,
            "phase2_target_pct": 100 * P2_TARGET,
            "phase2_basis": "phase 1 ending balance (reset variant saved separately)",
            "daily_dd_pct": 100 * DAILY_DD,
            "daily_reference": "higher of balance/equity at 00:00 UTC",
            "max_dd_pct": 100 * MAX_DD,
            "max_dd_type": "trailing, offset fixed at 10% of initial balance",
            "max_dd_offset_$": MAX_DD_AMOUNT,
        },
        "trading_days": len(days),
        "trades": n_trades,
        "avg_trades_per_day": n_trades / len(days),
        "longest_losing_streak_trades": st,
        "historical": hist_rows,
        "monte_carlo": mc_rows,
        "historical_phase2_reset": reset_rows,
        "historical_eod_trail": hist_eod,
        "monte_carlo_eod_trail": mc_eod,
        "margin": margins,
    }
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=float)
    print("longest losing streak (trades):", st)
    print(f"saved -> {OUT}")


if __name__ == "__main__":
    main()
