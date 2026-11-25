import sys

sys.path.insert(0, r"C:\Users\Administrator\Desktop\ORB")
import numpy as np
import pandas as pd

import backtest as b
from orb15_trail import SESSIONS, build_bars, entry_candidates, load_m1, simulate

lo = int(pd.Timestamp("2024-11-18", tz="UTC").timestamp() * 1000)
hi = int(pd.Timestamp("2026-11-17", tz="UTC").timestamp() * 1000)


def streaks(trades):
    r = [t["R"] for t in sorted(trades, key=lambda t: t["exit_ms"])]
    runs, cur = [], 0
    for x in r:
        if x <= 0:
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    return runs


for v in ("none", "atr1.0"):
    allt = []
    for pair in ("EURUSD", "GBPUSD"):
        df = load_m1(pair, lo, hi)
        bars = build_bars(df)
        trend = b.build_trend(df, b.et_index(df))
        for name, sess in SESSIONS.items():
            allt.extend(simulate(pair, df, bars, entry_candidates(pair, df, bars, sess, trend), v))
    s = streaks(allt)
    print(
        f"{v:7} losing_streaks={len(s)} mean={np.mean(s):.2f} median={np.median(s):.0f} "
        f"max={max(s)} losses={sum(1 for t in allt if t['R'] <= 0)}"
    )
