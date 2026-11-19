"""NY open range breakout (ORB) on EURUSD M1.

Range : high/low of the first five 1-minute candles (08:00-08:04 ET).
Entry : first 1m CLOSE beyond the range after 08:05 ET, before cutoff.
Bias  : optional 15m EMA200 filter (last completed bar, no lookahead).
Stop  : opposite side of the range, or 1.5 x ATR(14).
Exit  : fixed R target, 16:00 ET flat, or EMA20 close-cross.
Cost  : 0.8 pip round trip. One trade per day.
"""
from __future__ import annotations

import os
import sys
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as b

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
RANGE_BARS = 5
PIP = b.PIP


def run_orb(
    df: pd.DataFrame,
    idx_et: pd.DatetimeIndex,
    trend: np.ndarray,
    stop_mode: str,
    exit_mode: str,
    target_R: float = 2.0,
    use_bias: bool = True,
    cutoff_min: int = 12 * 60,
    flat_min: int = 16 * 60,
    cost_pips: float = b.COST_PIPS,
    min_range_pips: float = 0.0,
    max_range_pips: float = 1e9,
    buffer_pips: float = 0.0,
    be_at_R: float | None = None,
    skip_weekdays: set[int] | None = None,
    pip: float = PIP,
) -> list[dict]:
    o = df["open"].to_numpy(); h = df["high"].to_numpy()
    l = df["low"].to_numpy(); c = df["close"].to_numpy()
    ema = df["ema20"].to_numpy(); atr = df["atr14"].to_numpy()
    ts = df["timestamp"].to_numpy(); n = len(df)

    minutes = idx_et.hour * 60 + idx_et.minute
    dates = idx_et.date
    day_starts: dict = {}
    for i in range(n):
        if minutes[i] >= b.SESSION_START_MIN:
            day_starts.setdefault(dates[i], i)

    trades: list[dict] = []
    for day, first in day_starts.items():
        # range = first 5 session bars
        if minutes[first] != b.SESSION_START_MIN:
            continue
        ridx = [first + k for k in range(RANGE_BARS) if first + k < n]
        if len(ridx) < RANGE_BARS or any(
            minutes[ix] != b.SESSION_START_MIN + off for off, ix in enumerate(ridx)
        ):
            continue
        rhi = float(h[ridx].max()); rlo = float(l[ridx].min())

        if skip_weekdays and day.weekday() in skip_weekdays:
            continue
        range_pips = (rhi - rlo) / pip
        if range_pips < min_range_pips or range_pips > max_range_pips:
            continue

        deadline_ms = int(
            (pd.Timestamp(day).tz_localize(b.NY) + pd.Timedelta(minutes=flat_min))
            .tz_convert("UTC").timestamp() * 1000
        )
        cutoff_ms = int(
            (pd.Timestamp(day).tz_localize(b.NY) + pd.Timedelta(minutes=cutoff_min))
            .tz_convert("UTC").timestamp() * 1000
        )

        trade = None
        for j in range(ridx[-1] + 1, n):
            if ts[j] >= cutoff_ms:
                break
            if c[j] > rhi + buffer_pips * pip:
                d = 1
            elif c[j] < rlo - buffer_pips * pip:
                d = -1
            else:
                continue
            if use_bias and trend[j] != d:
                continue

            entry = float(c[j])
            if stop_mode == "range":
                stop = rlo if d > 0 else rhi
            elif stop_mode == "atr":
                stop = entry - d * 1.5 * float(atr[j])
            else:
                raise ValueError(stop_mode)
            stop_dist = abs(entry - stop)
            if stop_dist <= 0:
                continue
            initial_stop = stop
            target = entry + d * target_R * stop_dist if exit_mode == "target" else None

            exit_price = None; reason = "flat"; k_exit = j
            for k in range(j + 1, n):
                if ts[k] >= deadline_ms:
                    exit_price = float(c[k - 1]); reason = "flat"; k_exit = k - 1
                    break
                if d > 0:
                    if l[k] <= stop:
                        exit_price = float(min(o[k], stop)); reason = "stop"; k_exit = k; break
                    if be_at_R is not None and h[k] >= entry + be_at_R * stop_dist:
                        stop = max(stop, entry)
                    if target is not None and h[k] >= target:
                        exit_price = float(max(o[k], target)); reason = "target"; k_exit = k; break
                    if exit_mode == "ema" and c[k] < ema[k]:
                        exit_price = float(c[k]); reason = "ema"; k_exit = k; break
                else:
                    if h[k] >= stop:
                        exit_price = float(max(o[k], stop)); reason = "stop"; k_exit = k; break
                    if be_at_R is not None and l[k] <= entry - be_at_R * stop_dist:
                        stop = min(stop, entry)
                    if target is not None and l[k] <= target:
                        exit_price = float(min(o[k], target)); reason = "target"; k_exit = k; break
                    if exit_mode == "ema" and c[k] > ema[k]:
                        exit_price = float(c[k]); reason = "ema"; k_exit = k; break
            if exit_price is None:
                exit_price = float(c[min(k_exit, n - 1)])

            gross = d * (exit_price - entry) / pip
            pips = gross - cost_pips
            trade = {
                "date": str(day),
                "dir": "long" if d > 0 else "short",
                "entry_ms": int(ts[j]),
                "entry_time": str(idx_et[j]),
                "entry": round(entry, 5),
                "stop": round(initial_stop, 5),
                "range_pips": round((rhi - rlo) / pip, 1),
                "stop_pips": round(stop_dist / pip, 1),
                "exit_ms": int(ts[k_exit]),
                "exit_time": str(idx_et[k_exit]),
                "exit": round(exit_price, 5),
                "gross_pips": round(gross, 1),
                "pips": round(pips, 1),
                "R": round(pips / (stop_dist / pip), 3),
                "reason": reason,
                "hold_min": int((ts[k_exit] - ts[j]) / 60000),
            }
            break
        if trade:
            trades.append(trade)
    return trades


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    df = b.load_m1(b.DEFAULT_FILES)
    df = b.add_indicators(df)
    idx_et = b.et_index(df)
    trend = b.build_trend(df, idx_et)

    last_ms = int(df["timestamp"].iloc[-1])
    start_ms = last_ms - b.WINDOW_DAYS * 86400_000

    variants = []
    for bias in (False, True):
        for stop_mode in ("range", "atr"):
            for exit_mode, target_R in (("target", 1.0), ("target", 2.0), ("target", 3.0), ("flat", 2.0), ("ema", 2.0)):
                label = (
                    f"{'bias ' if bias else 'no bias '}"
                    f"{stop_mode} stop / "
                    f"{exit_mode if exit_mode != 'target' else f'{target_R:g}R'}"
                )
                variants.append((label, dict(use_bias=bias, stop_mode=stop_mode,
                                             exit_mode=exit_mode, target_R=target_R)))

    results = []
    trades_by_label: dict[str, list[dict]] = {}
    for label, kw in variants:
        trades = [t for t in run_orb(df, idx_et, trend, **kw) if t["entry_ms"] >= start_ms]
        trades_by_label[label] = trades
        s = b.summarize(trades, label)
        s["total_pips"] = round(sum(t["pips"] for t in trades), 1)
        s["median_range_pips"] = (
            float(np.median([t["range_pips"] for t in trades])) if trades else 0.0
        )
        results.append(s)
        b.print_summary(s)
        print(f"{'':40} pips={s['total_pips']:+7.1f}  median_range={s['median_range_pips']:.1f}p")

    cands = [s for s in results if s["trades"] >= 30]
    best = max(cands, key=lambda s: (s["total_R"], s["profit_factor"]))
    print(f"\nbest (n>=30): {best['label']}  totR={best['total_R']:+.1f}  pips={best['total_pips']:+.1f}")

    if best:
        trades = trades_by_label[best["label"]]
        if trades:
            import csv
            path = os.path.join(OUT_DIR, "orb_trades_best.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(trades[0].keys()))
                w.writeheader(); w.writerows(trades)
            print(f"trades -> {path}")

    import json
    path = os.path.join(OUT_DIR, "orb_variants.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=float)
    print(f"summary -> {path}")


if __name__ == "__main__":
    main()
