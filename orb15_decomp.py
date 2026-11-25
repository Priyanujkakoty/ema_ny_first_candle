"""Decompose which change kills the edge:

  range bar width  : first 5 M1 bars (5 min) vs first 15m bar
  entry clock      : first M1 close beyond the range vs first 15m close

Four cells, same stop (opposite side of range), same 12:00 ET cutoff,
16:00 ET flat, 15m EMA200 bias, no take-profit.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import backtest as b  # noqa: E402
from orb15_trail import (  # noqa: E402
    PAIRS, SESSIONS, TF_MS, BUFFER_PIPS, CUTOFF_MIN, FLAT_MIN,
    build_bars, load_m1, simulate, stats, line,
)

SINCE = "2024-11-18"
UNTIL = "2026-11-17"


def bias_at(bars: dict, ms: int) -> int:
    p = bars["pos"].get(int(ms // TF_MS))
    return 0 if p is None else int(bars["sign_prev"][p])


def cands_range15_entry15(pair, df, bars, session_min):
    from orb15_trail import entry_candidates
    return entry_candidates(pair, df, bars, session_min)


def cands_range15_entry1m(pair, df, bars, session_min):
    pip = PAIRS[pair]["pip"]
    ts = df["timestamp"].to_numpy(np.int64)
    c = df["close"].to_numpy()
    et = pd.DatetimeIndex(pd.to_datetime(bars["start_ms"], unit="ms", utc=True)).tz_convert('America/New_York')
    mins = et.hour * 60 + et.minute
    dates = et.date
    nb = len(bars["ids"])
    first_of_day = {}
    for i in range(nb):
        if mins[i] >= session_min:
            first_of_day.setdefault(dates[i], i)

    out = []
    for day, p0 in sorted(first_of_day.items()):
        if mins[p0] != session_min:
            continue
        rhi, rlo = float(bars["h"][p0]), float(bars["l"][p0])
        local = pd.Timestamp(day).tz_localize("America/New_York")
        cutoff_ms = int((local + pd.Timedelta(minutes=CUTOFF_MIN)).tz_convert("UTC").timestamp() * 1000)
        deadline_ms = int((local + pd.Timedelta(minutes=FLAT_MIN)).tz_convert("UTC").timestamp() * 1000)
        start = int(bars["end_ms"][p0])
        j0 = int(np.searchsorted(ts, start, side="left"))
        for j in range(j0, len(df)):
            if ts[j] >= cutoff_ms:
                break
            if c[j] > rhi + BUFFER_PIPS * pip:
                d = 1
            elif c[j] < rlo - BUFFER_PIPS * pip:
                d = -1
            else:
                continue
            if bias_at(bars, int(ts[j])) != d:
                continue
            out.append(dict(pair=pair, day=day, dir=d, j=int(j), entry=float(c[j]),
                            stop=float(rlo if d > 0 else rhi), bar=0,
                            deadline_ms=deadline_ms, range_pips=(rhi - rlo) / pip))
            break
    return out


def cands_range5_entry1m(pair, df, bars, session_min):
    pip = PAIRS[pair]["pip"]
    ts = df["timestamp"].to_numpy(np.int64)
    h = df["high"].to_numpy(); l = df["low"].to_numpy(); c = df["close"].to_numpy()
    idx = b.et_index(df)
    minutes = idx.hour * 60 + idx.minute
    dates = idx.date
    day_first = {}
    for i in range(len(df)):
        if minutes[i] >= session_min:
            day_first.setdefault(dates[i], i)

    out = []
    for day, first in sorted(day_first.items()):
        if minutes[first] != session_min:
            continue
        ridx = [first + k for k in range(5) if first + k < len(df)]
        if len(ridx) < 5 or any(minutes[ix] != session_min + off for off, ix in enumerate(ridx)):
            continue
        rhi, rlo = float(h[ridx].max()), float(l[ridx].min())
        local = pd.Timestamp(day).tz_localize("America/New_York")
        cutoff_ms = int((local + pd.Timedelta(minutes=CUTOFF_MIN)).tz_convert("UTC").timestamp() * 1000)
        deadline_ms = int((local + pd.Timedelta(minutes=FLAT_MIN)).tz_convert("UTC").timestamp() * 1000)
        for j in range(ridx[-1] + 1, len(df)):
            if ts[j] >= cutoff_ms:
                break
            if c[j] > rhi + BUFFER_PIPS * pip:
                d = 1
            elif c[j] < rlo - BUFFER_PIPS * pip:
                d = -1
            else:
                continue
            if bias_at(bars, int(ts[j])) != d:
                continue
            out.append(dict(pair=pair, day=day, dir=d, j=int(j), entry=float(c[j]),
                            stop=float(rlo if d > 0 else rhi), bar=0,
                            deadline_ms=deadline_ms, range_pips=(rhi - rlo) / pip))
            break
    return out


def cands_range5_entry15(pair, df, bars, session_min):
    """5-min range, but the breakout must be confirmed by a 15m close."""
    pip = PAIRS[pair]["pip"]
    ts = df["timestamp"].to_numpy(np.int64)
    c = df["close"].to_numpy()
    h = df["high"].to_numpy(); l = df["low"].to_numpy()
    idx = b.et_index(df)
    minutes = idx.hour * 60 + idx.minute
    dates = idx.date
    nb = len(bars["ids"])
    etb = pd.DatetimeIndex(pd.to_datetime(bars["start_ms"], unit="ms", utc=True)).tz_convert("America/New_York")
    minsb = etb.hour * 60 + etb.minute
    datesb = etb.date

    day_first = {}
    for i in range(len(df)):
        if minutes[i] >= session_min:
            day_first.setdefault(dates[i], i)
    bar_first = {}
    for i in range(nb):
        if minsb[i] >= session_min:
            bar_first.setdefault(datesb[i], i)

    out = []
    for day, first in sorted(day_first.items()):
        if minutes[first] != session_min:
            continue
        ridx = [first + k for k in range(5) if first + k < len(df)]
        if len(ridx) < 5 or any(minutes[ix] != session_min + off for off, ix in enumerate(ridx)):
            continue
        rhi, rlo = float(h[ridx].max()), float(l[ridx].min())
        p0 = bar_first.get(day)
        if p0 is None:
            continue
        local = pd.Timestamp(day).tz_localize("America/New_York")
        cutoff_ms = int((local + pd.Timedelta(minutes=CUTOFF_MIN)).tz_convert("UTC").timestamp() * 1000)
        deadline_ms = int((local + pd.Timedelta(minutes=FLAT_MIN)).tz_convert("UTC").timestamp() * 1000)
        for p in range(p0, nb):
            if int(bars["start_ms"][p]) < int(ts[ridx[-1]]):
                continue
            if int(bars["start_ms"][p]) >= cutoff_ms:
                break
            if bars["c"][p] > rhi + BUFFER_PIPS * pip:
                d = 1
            elif bars["c"][p] < rlo - BUFFER_PIPS * pip:
                d = -1
            else:
                continue
            if bars["sign_prev"][p] != d:
                continue
            j = int(np.searchsorted(ts, int(bars["end_ms"][p]), side="left")) - 1
            if j < 1 or j >= len(df) - 1:
                continue
            out.append(dict(pair=pair, day=day, dir=d, j=j, entry=float(c[j]),
                            stop=float(rlo if d > 0 else rhi), bar=p,
                            deadline_ms=deadline_ms, range_pips=(rhi - rlo) / pip))
            break
    return out


CELLS = {
    "range15_entry15": cands_range15_entry15,
    "range15_entry1m": cands_range15_entry1m,
    "range5_entry15": cands_range5_entry15,
    "range5_entry1m": cands_range5_entry1m,
}
VARIANTS = ("none", "atr1.0", "r0.5")


def main() -> None:
    since_ms = int(pd.Timestamp(SINCE, tz="UTC").timestamp() * 1000)
    until_ms = int(pd.Timestamp(UNTIL, tz="UTC").timestamp() * 1000)
    for pair in ("EURUSD", "GBPUSD"):
        df = load_m1(pair, since_ms, until_ms)
        bars = build_bars(df)
        print(f"\n{pair}  {SINCE} -> {UNTIL}")
        for name, sess in SESSIONS.items():
            print(f"  {name}")
            for cell, fn in CELLS.items():
                cands = fn(pair, df, bars, sess)
                for v in VARIANTS:
                    tr = simulate(pair, df, bars, cands, v)
                    print("    " + line(stats(tr, v), f"{cell:17} {v:7}"))


if __name__ == "__main__":
    main()
