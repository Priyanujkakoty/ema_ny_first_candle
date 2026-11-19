"""NY-open first-candle EMA20 momentum test on EURUSD M1.

Rule:
  At the New York open (08:00 America/New_York) take the first 1-minute
  candle of the session.
    long  : close > EMA20 and close > open
    short : close < EMA20 and close < open
  Entry at that candle's close. One trade per day, no re-entry.

  Stop : 1.5 x ATR(14) from entry, checked intrabar (gap fills at open).
  Exit : first 1m close back through EMA20 on the opposite side, or the stop.

Costs: 0.8 pip round-trip deducted from every trade (repo convention).
Window: the last 365 days present in the data.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import Counter
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = r"E:\FOREX INTEL"
DEFAULT_FILES = [
    os.path.join(ROOT, "market_data", "EURUSD", "1m", "yearly", "eurusd_1m_2025.csv"),
    os.path.join(ROOT, "market_data", "EURUSD", "1m", "yearly", "eurusd_1m_2026.csv"),
]
OUT_DIR = os.path.join(ROOT, "strategies", "ema_ny_first_candle", "results")

EMA_PERIOD = 20
ATR_PERIOD = 14
STOP_MULT = 1.5
COST_PIPS = 0.8
PIP = 0.0001
NY = "America/New_York"
SESSION_START_MIN = 8 * 60          # 08:00 ET
SESSION_END_MIN = 9 * 60            # first candle must start before 09:00 ET
WINDOW_DAYS = 365


# ---------------------------------------------------------------- data

def load_m1(paths: list[str]) -> pd.DataFrame:
    frames = []
    for path in paths:
        df = pd.read_csv(path, usecols=["timestamp", "open", "high", "low", "close"])
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    return df


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close"]
    df["ema20"] = close.ewm(span=EMA_PERIOD, adjust=False).mean()

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    # Wilder ATR
    df["atr14"] = tr.ewm(alpha=1.0 / ATR_PERIOD, adjust=False).mean()
    return df


def et_index(df: pd.DataFrame) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(
        pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    ).tz_convert(NY)


def build_trend(
    df: pd.DataFrame, idx_et: pd.DatetimeIndex, tf_min: int = 15, period: int = 200
) -> np.ndarray:
    """Higher-timeframe bias aligned to each M1 bar, no lookahead.

    Uses the last COMPLETED 15m bar (label = bar end). +1 close > EMA200,
    -1 close < EMA200, 0 during warmup.
    """
    s = pd.Series(df["close"].to_numpy(), index=idx_et)
    bars = s.resample(f"{tf_min}min", label="right", closed="right").last().dropna()
    ema = bars.ewm(span=period, adjust=False).mean()
    sign = np.where(bars.to_numpy() > ema.to_numpy(), 1, -1)

    end_ms = bars.index.tz_convert("UTC").asi8 // 10**6
    close_ms = idx_et.tz_convert("UTC").asi8 // 10**6 + 60_000
    pos = np.searchsorted(end_ms, close_ms, side="right") - 1

    out = np.zeros(len(df), dtype=int)
    ok = (pos >= period)
    out[ok] = sign[pos[ok]]
    return out


# ---------------------------------------------------------------- engine

def run_backtest(
    df: pd.DataFrame,
    idx_et: pd.DatetimeIndex,
    stop_mult: float | None,
    flat_hour: int | None = None,
    cost_pips: float = COST_PIPS,
    min_disp_atr: float = 0.0,
    target_R: float | None = None,
    trend: np.ndarray | None = None,
    fade: bool = False,
    session_start_min: int | None = None,
    stop_pips_fixed: float | None = None,
) -> list[dict]:
    o = df["open"].to_numpy()
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    c = df["close"].to_numpy()
    ema = df["ema20"].to_numpy()
    atr = df["atr14"].to_numpy()
    ts = df["timestamp"].to_numpy()
    n = len(df)

    minutes = idx_et.hour * 60 + idx_et.minute
    dates = idx_et.date
    start_min = SESSION_START_MIN if session_start_min is None else session_start_min
    mask = (minutes >= start_min) & (minutes < start_min + 60)
    sig_positions = df.index[mask].to_numpy()
    # first qualifying candle per ET date
    seen: set = set()
    first_sig: list[int] = []
    for i in sig_positions:
        d = dates[i]
        if d in seen:
            continue
        seen.add(d)
        first_sig.append(int(i))

    trades: list[dict] = []
    for i in first_sig:
        if i < EMA_PERIOD or i + 1 >= n:
            continue
        if not np.isfinite(ema[i]) or not np.isfinite(atr[i]) or atr[i] <= 0:
            continue

        direction = 0
        if c[i] > ema[i] and c[i] > o[i]:
            direction = 1
        elif c[i] < ema[i] and c[i] < o[i]:
            direction = -1
        if direction == 0:
            continue

        # filters are evaluated on the original signal, before any fade flip
        disp = (c[i] - ema[i]) / atr[i]
        if direction * disp < min_disp_atr:
            continue
        if trend is not None and trend[i] != direction:
            continue

        if fade:
            direction = -direction

        entry = float(c[i])
        if stop_pips_fixed is not None:
            stop_dist = float(stop_pips_fixed * PIP)
        elif stop_mult is not None:
            stop_dist = float(stop_mult * atr[i])
        else:
            stop_dist = None
        stop = None if stop_dist is None else entry - direction * stop_dist
        target = (
            entry + direction * target_R * stop_dist
            if (target_R is not None and stop_dist is not None)
            else None
        )
        risk_unit = stop_dist if stop_dist else float(1.5 * atr[i])

        deadline_ms = None
        if flat_hour is not None:
            local = pd.Timestamp(dates[i]).tz_localize(NY) + pd.Timedelta(hours=flat_hour)
            deadline_ms = int(local.tz_convert("UTC").timestamp() * 1000)

        exit_price = None
        reason = "data_end"
        j_exit = n - 1

        for j in range(i + 1, n):
            if deadline_ms is not None and ts[j] >= deadline_ms:
                exit_price = float(c[j - 1])
                reason = "flat"
                j_exit = j - 1
                break

            if direction > 0:
                if stop is not None and l[j] <= stop:
                    exit_price = float(min(o[j], stop))
                    reason = "stop"
                    j_exit = j
                    break
                if target is not None and h[j] >= target:
                    exit_price = float(max(o[j], target))
                    reason = "target"
                    j_exit = j
                    break
                if target is None and c[j] < ema[j]:
                    exit_price = float(c[j])
                    reason = "ema"
                    j_exit = j
                    break
            else:
                if stop is not None and h[j] >= stop:
                    exit_price = float(max(o[j], stop))
                    reason = "stop"
                    j_exit = j
                    break
                if target is not None and l[j] <= target:
                    exit_price = float(min(o[j], target))
                    reason = "target"
                    j_exit = j
                    break
                if target is None and c[j] > ema[j]:
                    exit_price = float(c[j])
                    reason = "ema"
                    j_exit = j
                    break
        else:
            exit_price = float(c[n - 1])

        gross_pips = direction * (exit_price - entry) / PIP
        pips = gross_pips - cost_pips
        r_mult = pips / (risk_unit / PIP)

        trades.append(
            {
                "date": str(dates[i]),
                "dir": "long" if direction > 0 else "short",
                "entry_ms": int(ts[i]),
                "entry_time": str(idx_et[i]),
                "entry": round(entry, 5),
                "stop": None if stop is None else round(stop, 5),
                "atr_pips": round(float(atr[i] / PIP), 1),
                "stop_pips": round(float(risk_unit / PIP), 1),
                "exit_ms": int(ts[j_exit]),
                "exit_time": str(idx_et[j_exit]),
                "exit": round(exit_price, 5),
                "gross_pips": round(gross_pips, 1),
                "pips": round(pips, 1),
                "R": round(r_mult, 3),
                "reason": reason,
                "hold_min": int((ts[j_exit] - ts[i]) / 60000),
            }
        )
    return trades


# ---------------------------------------------------------------- stats

def max_drawdown_r(trades: list[dict]) -> float:
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for t in sorted(trades, key=lambda x: x["exit_ms"]):
        equity += t["R"]
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return worst


def longest_loss_streak(trades: list[dict]) -> int:
    best = cur = 0
    for t in sorted(trades, key=lambda x: x["exit_ms"]):
        if t["R"] <= 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def summarize(trades: list[dict], label: str) -> dict:
    n = len(trades)
    if n == 0:
        return {"label": label, "trades": 0}
    r = np.array([t["R"] for t in trades])
    pips = np.array([t["pips"] for t in trades])
    wins = pips[pips > 0]
    losses = pips[pips <= 0]
    pf = wins.sum() / abs(losses.sum()) if losses.sum() != 0 else math.inf
    total_r = r.sum()
    expectancy = r.mean()
    std = r.std(ddof=1) if n > 1 else 0.0
    tstat = expectancy / (std / math.sqrt(n)) if std > 0 else 0.0
    holds = np.array([t["hold_min"] for t in trades])
    reasons = Counter(t["reason"] for t in trades)
    longs = sum(1 for t in trades if t["dir"] == "long")

    return {
        "label": label,
        "trades": n,
        "win_rate": 100.0 * len(wins) / n,
        "avg_R": expectancy,
        "total_R": total_r,
        "avg_win_R": r[r > 0].mean() if (r > 0).any() else 0.0,
        "avg_loss_R": r[r <= 0].mean() if (r <= 0).any() else 0.0,
        "profit_factor": pf,
        "max_dd_R": max_drawdown_r(trades),
        "loss_streak": longest_loss_streak(trades),
        "avg_hold_min": holds.mean(),
        "median_hold_min": float(np.median(holds)),
        "t_stat": tstat,
        "longs": longs,
        "shorts": n - longs,
        "stop_exits": reasons.get("stop", 0),
        "ema_exits": reasons.get("ema", 0),
        "target_exits": reasons.get("target", 0),
        "flat_exits": reasons.get("flat", 0),
        "data_end": reasons.get("data_end", 0),
    }


def print_summary(s: dict) -> None:
    if s["trades"] == 0:
        print(f"{s['label']}: no trades")
        return
    print(
        f"{s['label']:<26} n={s['trades']:>4}  win={s['win_rate']:5.1f}%  "
        f"avgR={s['avg_R']:+6.3f}  totR={s['total_R']:+8.1f}  "
        f"PF={s['profit_factor']:5.2f}  maxDD={s['max_dd_R']:6.1f}R  "
        f"streak={s['loss_streak']:>2}  t={s['t_stat']:+5.2f}"
    )
    print(
        f"{'':26} L/S={s['longs']}/{s['shorts']}  "
        f"exits stop/ema/target/flat/end="
        f"{s['stop_exits']}/{s['ema_exits']}/{s['target_exits']}/{s['flat_exits']}/{s['data_end']}  "
        f"hold avg={s['avg_hold_min']:.0f}m med={s['median_hold_min']:.0f}m"
    )


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", nargs="*", default=DEFAULT_FILES)
    ap.add_argument("--window-days", type=int, default=WINDOW_DAYS)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)

    df = load_m1(args.files)
    df = add_indicators(df)
    idx_et = et_index(df)

    last_ms = int(df["timestamp"].iloc[-1])
    start_ms = last_ms - args.window_days * 86400_000
    window = df["timestamp"] >= start_ms
    first_ts = datetime.fromtimestamp(int(df.loc[window, "timestamp"].iloc[0]) / 1000, tz=timezone.utc)
    last_ts = datetime.fromtimestamp(last_ms / 1000, tz=timezone.utc)
    print(f"data: {len(df):,} M1 bars  |  window {first_ts:%Y-%m-%d} -> {last_ts:%Y-%m-%d} UTC")
    print()

    variants = [
        ("base 1.5xATR + EMA exit", 1.5, None),
        ("1.0xATR", 1.0, None),
        ("2.0xATR", 2.0, None),
        ("3.0xATR", 3.0, None),
        ("no stop, EMA only", None, None),
        ("1.5xATR + flat 17:00 ET", 1.5, 17),
    ]

    results = []
    base_trades: list[dict] = []
    for label, mult, flat in variants:
        trades = run_backtest(df, idx_et, mult, flat)
        trades = [t for t in trades if t["entry_ms"] >= start_ms]
        results.append(summarize(trades, label))
        if label.startswith("base"):
            base_trades = trades

    for s in results:
        print_summary(s)

    # yearly + monthly for the base variant
    if base_trades:
        print("\nbase by year")
        by_year: dict[str, list[dict]] = {}
        for t in base_trades:
            by_year.setdefault(t["date"][:4], []).append(t)
        for year in sorted(by_year):
            s = summarize(by_year[year], year)
            print_summary(s)

        print("\nbase by month")
        by_month: dict[str, list[dict]] = {}
        for t in base_trades:
            by_month.setdefault(t["date"][:7], []).append(t)
        for month in sorted(by_month):
            s = summarize(by_month[month], month)
            print_summary(s)

        trades_path = os.path.join(OUT_DIR, "trades_base.csv")
        with open(trades_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(base_trades[0].keys()))
            writer.writeheader()
            writer.writerows(base_trades)
        print(f"\ntrades -> {trades_path}")

    summary_path = os.path.join(OUT_DIR, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=float)
    print(f"summary -> {summary_path}")


if __name__ == "__main__":
    main()
