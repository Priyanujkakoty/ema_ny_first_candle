"""A/B: same repo engine, only the 15m EMA200 bias changes.

A) repo default  : resample(closed="right") -> bar used at time t contains the
                   M1 row stamped t (closes 1 minute later). Slight lookahead.
B) clean         : bars [t-15, t), available at t. No lookahead.

Both run lab.session_orb unchanged (5xM1 range, M1 entry, range stop,
bias filter, 12:00 cutoff, 16:00 flat), same 2-year window.
"""
import sys

sys.path.insert(0, r"C:\Users\Administrator\Desktop\ORB")
import numpy as np
import pandas as pd

import backtest as b
import lab

SINCE = pd.Timestamp("2024-11-18", tz="UTC")
UNTIL = pd.Timestamp("2026-11-17", tz="UTC")
LO, HI = int(SINCE.timestamp() * 1000), int(UNTIL.timestamp() * 1000)


def clean_trend(df, idx_et, tf_min=15, period=200):
    s = pd.Series(df["close"].to_numpy(), index=idx_et)
    bars = s.resample(f"{tf_min}min", label="right", closed="left").last().dropna()
    ema = bars.ewm(span=period, adjust=False).mean()
    sign = np.where(bars.to_numpy() > ema.to_numpy(), 1, -1)
    end_ms = bars.index.tz_convert("UTC").asi8 // 10**6
    ts_ms = idx_et.tz_convert("UTC").asi8 // 10**6
    pos = np.searchsorted(end_ms, ts_ms, side="right") - 1
    out = np.zeros(len(df), dtype=int)
    ok = pos >= period
    out[ok] = sign[pos[ok]]
    return out


def run(tag):
    rows = []
    for pair in ("EURUSD", "GBPUSD"):
        for name, sess in (("ny_orb", 480), ("london_orb", 180)):
            tr = lab.session_orb(pair, sess, 5, 720, 960, 1.0, True, "range", name)
            tr = [t for t in tr if LO <= t["entry_ms"] <= HI]
            s = b.summarize(tr, f"{pair} {name}")
            rows.append((pair, name, s))
            print(f"{tag} {pair} {name:11} n={s['trades']:4d} avgR={s['avg_R']:+.3f} "
                  f"totR={s['total_R']:+7.1f} DD={s['max_dd_R']:7.1f} t={s['t_stat']:+5.2f} "
                  f"win={s['win_rate']:4.1f}%", flush=True)
    allt = sum((s["total_R"] for _, _, s in rows), 0.0)
    print(f"{tag} TOTAL totR={allt:+.1f}\n", flush=True)


for tag, fn in (("A_repo", None), ("B_clean", clean_trend)):
    lab._cache.clear()
    orig = b.build_trend
    if fn is not None:
        b.build_trend = fn
    run(tag)
    b.build_trend = orig
