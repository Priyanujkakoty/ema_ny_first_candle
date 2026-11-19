"""Strategy lab: generic intraday engines on M1 FX data.

Every strategy returns trades with the same schema as orb.py so the existing
summaries and the prop simulator can consume them.

Design rules:
  - entries are decided on a bar CLOSE, fills at that close (no lookahead)
  - stops are checked intrabar, gap fills at the open
  - every strategy is flat by a fixed ET time, no overnight exposure
  - costs are per-pair round-trip pips
"""
from __future__ import annotations

import os
import sys
from collections import Counter

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import backtest as b

ROOT = r"E:\FOREX INTEL"
PIP = b.PIP

PAIRS = {
    "EURUSD": dict(pip=0.0001, cost=0.8, files=[os.path.join(ROOT, "market_data", "EURUSD", "1m", "yearly", f"eurusd_1m_{y}.csv") for y in range(2011, 2027)], jpy=False),
    "GBPUSD": dict(pip=0.0001, cost=1.0, files=[os.path.join(ROOT, "market_data", "m1_16y", "gbpusd-m1-bid-2010-01-01-2026-11-17T20-57.csv")], jpy=False),
    "USDJPY": dict(pip=0.01, cost=0.7, files=[os.path.join(ROOT, "market_data", "m1_16y", "usdjpy-m1-bid-2010-01-01-2026-11-17T20-11.csv")], jpy=True),
    "AUDJPY": dict(pip=0.01, cost=1.4, files=[os.path.join(ROOT, "market_data", "m1_16y", "audjpy-m1-bid-2010-01-01-2026-11-17T20-11.csv")], jpy=True),
    "GBPJPY": dict(pip=0.01, cost=1.6, files=[os.path.join(ROOT, "market_data", "m1_16y", "gbpjpy-m1-bid-2010-01-01-2026-11-17T20-11.csv")], jpy=True),
}

_cache: dict[str, tuple] = {}


def load(pair: str, start: str = "2010-06-01") -> tuple:
    """Returns (df, idx_et, trend15). Cached per pair."""
    if pair in _cache:
        return _cache[pair]
    cfg = PAIRS[pair]
    since = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    frames = []
    for path in cfg["files"]:
        for chunk in pd.read_csv(path, usecols=["timestamp", "open", "high", "low", "close"], chunksize=1_000_000):
            chunk = chunk[chunk["timestamp"] >= since]
            if len(chunk):
                frames.append(chunk)
    df = pd.concat(frames, ignore_index=True).drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    df = b.add_indicators(df)
    idx = b.et_index(df)
    trend = b.build_trend(df, idx, tf_min=15)
    _cache[pair] = (df, idx, trend)
    return _cache[pair]


# ---------------------------------------------------------------- executor

def execute(df, idx_et, entries: list[dict], pair: str,
            with_path: bool = False) -> list[dict]:
    cfg = PAIRS[pair]
    pip = cfg["pip"]
    o = df["open"].to_numpy(); h = df["high"].to_numpy()
    l = df["low"].to_numpy(); c = df["close"].to_numpy()
    ts = df["timestamp"].to_numpy(); n = len(df)
    dates = idx_et.date

    out = []
    for e in entries:
        i, d, stop, deadline_ms = e["i"], e["d"], e["stop"], e["deadline_ms"]
        if i + 1 >= n or not np.isfinite(stop):
            continue
        entry = float(c[i])
        stop_dist = abs(entry - stop)
        if stop_dist <= 0:
            continue
        exit_price = None; reason = "flat"; k_exit = i
        for k in range(i + 1, n):
            if ts[k] >= deadline_ms:
                exit_price = float(c[k - 1]); reason = "flat"; k_exit = k - 1
                break
            if d > 0:
                if l[k] <= stop:
                    exit_price = float(min(o[k], stop)); reason = "stop"; k_exit = k; break
            else:
                if h[k] >= stop:
                    exit_price = float(max(o[k], stop)); reason = "stop"; k_exit = k; break
        if exit_price is None:
            exit_price = float(c[min(k_exit, n - 1)])
        gross = d * (exit_price - entry) / pip
        pips = gross - cfg["cost"]
        r_mult = pips / (stop_dist / pip)
        rec = {
            "date": str(dates[i]),
            "pair": pair,
            "strategy": e["tag"],
            "dir": "long" if d > 0 else "short",
            "entry_ms": int(ts[i]),
            "entry_time": str(idx_et[i]),
            "entry": round(entry, 5),
            "stop": round(float(stop), 5),
            "stop_pips": round(stop_dist / pip, 1),
            "exit_ms": int(ts[k_exit]),
            "exit_time": str(idx_et[k_exit]),
            "exit": round(exit_price, 5),
            "gross_pips": round(gross, 1),
            "pips": round(pips, 1),
            "R": round(r_mult, 3),
            "reason": reason,
            "hold_min": int((ts[k_exit] - ts[i]) / 60000),
        }
        if with_path:
            path = []
            for k in range(i + 1, min(k_exit, n - 1) + 1):
                if d > 0:
                    lo_r = (l[k] - entry) / stop_dist
                    hi_r = (h[k] - entry) / stop_dist
                else:
                    lo_r = (entry - h[k]) / stop_dist
                    hi_r = (entry - l[k]) / stop_dist
                path.append((
                    int(ts[k]),
                    min(0.0, max(float(lo_r), -1.0)),
                    max(0.0, float(hi_r)),
                    float(r_mult) if k == k_exit else float(d * (c[k] - entry) / stop_dist),
                ))
            if not path:
                path = [(int(ts[k_exit]), 0.0, 0.0, float(r_mult))]
            rec["_path"] = path
        out.append(rec)
    return out


def deadline(day, minutes_et: int) -> int:
    return int((pd.Timestamp(day).tz_localize(b.NY) + pd.Timedelta(minutes=minutes_et))
               .tz_convert("UTC").timestamp() * 1000)


# ---------------------------------------------------------------- engines

def session_orb(pair, session_start_min=8 * 60, range_bars=5, cutoff_min=12 * 60,
                flat_min=16 * 60, buffer_pips=1.0, use_bias=True, stop_mode="range",
                tag="orb", with_path=False) -> list[dict]:
    """Breakout of the first N bars of a session."""
    df, idx, trend = load(pair)
    o = df["open"].to_numpy(); h = df["high"].to_numpy()
    l = df["low"].to_numpy(); c = df["close"].to_numpy()
    ts = df["timestamp"].to_numpy(); n = len(df)
    atr = df["atr14"].to_numpy()
    minutes = idx.hour * 60 + idx.minute
    dates = idx.date
    cfg = PAIRS[pair]
    pip = cfg["pip"]

    day_first: dict = {}
    for i in range(n):
        if minutes[i] >= session_start_min:
            day_first.setdefault(dates[i], i)

    entries = []
    for day, first in day_first.items():
        if minutes[first] != session_start_min:
            continue
        ridx = [first + k for k in range(range_bars) if first + k < n]
        if len(ridx) < range_bars or any(minutes[ix] != session_start_min + off for off, ix in enumerate(ridx)):
            continue
        rhi = float(h[ridx].max()); rlo = float(l[ridx].min())
        dl = deadline(day, flat_min); co = deadline(day, cutoff_min)
        for j in range(ridx[-1] + 1, n):
            if ts[j] >= co:
                break
            if c[j] > rhi + buffer_pips * pip:
                d = 1
            elif c[j] < rlo - buffer_pips * pip:
                d = -1
            else:
                continue
            if use_bias and trend[j] != d:
                continue
            if stop_mode == "range":
                stop = rlo if d > 0 else rhi
            else:
                stop = float(c[j]) - d * 1.5 * float(atr[j])
            entries.append(dict(i=j, d=d, stop=stop, deadline_ms=dl, tag=tag))
            break
    return execute(df, idx, entries, pair, with_path=with_path)


def level_break(pair, level="prev_day", session_start_min=3 * 60, cutoff_min=12 * 60,
                flat_min=16 * 60, buffer_pips=1.0, use_bias=True,
                stop_mode="other_side", atr_mult=1.0, tag="level", with_path=False) -> list[dict]:
    """Breakout of the previous session's high/low, traded during the next session."""
    df, idx, trend = load(pair)
    h = df["high"].to_numpy(); l = df["low"].to_numpy(); c = df["close"].to_numpy()
    ts = df["timestamp"].to_numpy(); n = len(df)
    atr = df["atr14"].to_numpy()
    minutes = idx.hour * 60 + idx.minute
    dates = idx.date
    cfg = PAIRS[pair]
    pip = cfg["pip"]

    # previous ET day's high/low
    day_hi: dict = {}; day_lo: dict = {}
    for i in range(n):
        d = dates[i]
        day_hi[d] = max(day_hi.get(d, h[i]), h[i])
        day_lo[d] = min(day_lo.get(d, l[i]), l[i])
    days = sorted(day_hi)
    first_idx: dict = {}
    for i in range(n):
        if minutes[i] >= session_start_min:
            first_idx.setdefault(dates[i], i)

    entries = []
    for k, day in enumerate(days):
        if k == 0:
            continue
        prev = days[k - 1]
        if (pd.Timestamp(day) - pd.Timestamp(prev)).days > 3:
            continue
        rhi, rlo = day_hi[prev], day_lo[prev]
        first = first_idx.get(day)
        if first is None or dates[first] != day:
            continue
        dl = deadline(day, flat_min); co = deadline(day, cutoff_min)
        for j in range(first, n):
            if ts[j] >= co:
                break
            if c[j] > rhi + buffer_pips * pip:
                d = 1
            elif c[j] < rlo - buffer_pips * pip:
                d = -1
            else:
                continue
            if use_bias and trend[j] != d:
                continue
            if stop_mode == "other_side":
                stop = rlo if d > 0 else rhi
            else:
                stop = float(c[j]) - d * atr_mult * float(atr[j])
            entries.append(dict(i=j, d=d, stop=stop, deadline_ms=dl, tag=tag))
            break
    return execute(df, idx, entries, pair, with_path=with_path)


def time_momentum(pair, entry_min=10 * 60, lookback_min=120, stop_atr=1.0,
                  flat_min=16 * 60, min_move_atr=0.0, use_bias=True,
                  tag="momentum") -> list[dict]:
    """At a fixed ET time, trade in the direction of the last N minutes."""
    df, idx, trend = load(pair)
    c = df["close"].to_numpy(); atr = df["atr14"].to_numpy()
    ts = df["timestamp"].to_numpy(); n = len(df)
    minutes = idx.hour * 60 + idx.minute
    dates = idx.date

    # index of the entry bar per day
    pos: dict = {}
    for i in range(n):
        if minutes[i] == entry_min:
            pos.setdefault(dates[i], i)

    entries = []
    for day, i in pos.items():
        j = i - lookback_min
        if j < 0 or dates[j] != day:
            continue
        move = c[i] - c[j]
        if abs(move) < min_move_atr * atr[i]:
            continue
        d = 1 if move > 0 else -1
        if use_bias and trend[i] != d:
            continue
        stop = float(c[i]) - d * stop_atr * float(atr[i])
        entries.append(dict(i=i, d=d, stop=stop, deadline_ms=deadline(day, flat_min), tag=tag))
    return execute(df, idx, entries, pair)


def close_reversal(pair, entry_min=15 * 60, lookback_min=120, stop_atr=1.0,
                   flat_min=16 * 60, min_move_atr=0.5, tag="reversal") -> list[dict]:
    """Fade the late-session move, exit at the close."""
    df, idx, trend = load(pair)
    c = df["close"].to_numpy(); atr = df["atr14"].to_numpy()
    ts = df["timestamp"].to_numpy(); n = len(df)
    minutes = idx.hour * 60 + idx.minute
    dates = idx.date
    pos: dict = {}
    for i in range(n):
        if minutes[i] == entry_min:
            pos.setdefault(dates[i], i)

    entries = []
    for day, i in pos.items():
        j = i - lookback_min
        if j < 0 or dates[j] != day:
            continue
        move = c[i] - c[j]
        if abs(move) < min_move_atr * atr[i]:
            continue
        d = -1 if move > 0 else 1
        stop = float(c[i]) - d * stop_atr * float(atr[i])
        entries.append(dict(i=i, d=d, stop=stop, deadline_ms=deadline(day, flat_min), tag=tag))
    return execute(df, idx, entries, pair)


# ---------------------------------------------------------------- metrics

def stats(trades: list[dict], label: str = "") -> dict:
    n = len(trades)
    if n == 0:
        return {"label": label, "trades": 0}
    r = np.array([t["R"] for t in trades])
    pips = np.array([t["pips"] for t in trades])
    eq = np.cumsum(r)
    peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
    dd = float((eq - peak).min()) if n else 0.0
    sd = r.std(ddof=1) if n > 1 else 0.0
    wins = pips[pips > 0]; losses = pips[pips <= 0]
    by_year: dict[str, float] = {}
    for t in trades:
        by_year[t["date"][:4]] = by_year.get(t["date"][:4], 0.0) + t["R"]
    return {
        "label": label,
        "trades": n,
        "win_rate": 100.0 * len(wins) / n,
        "avg_R": float(r.mean()),
        "total_R": float(r.sum()),
        "pf": float(wins.sum() / abs(losses.sum())) if losses.sum() else float("inf"),
        "max_dd_R": dd,
        "calmar": float(r.sum() / abs(dd)) if dd else float("inf"),
        "t": float(r.mean() / (sd / np.sqrt(n))) if sd else 0.0,
        "years": by_year,
        "positive_years": sum(1 for v in by_year.values() if v > 0),
        "n_years": len(by_year),
    }


def daily_r(trades: list[dict]) -> dict[str, float]:
    out: dict[str, float] = {}
    for t in trades:
        out[t["date"]] = out.get(t["date"], 0.0) + t["R"]
    return out


def corr(a: dict[str, float], b: dict[str, float]) -> float:
    days = sorted(set(a) | set(b))
    x = np.array([a.get(d, 0.0) for d in days])
    y = np.array([b.get(d, 0.0) for d in days])
    if x.std() == 0 or y.std() == 0:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])
