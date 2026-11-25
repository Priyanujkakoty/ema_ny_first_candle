import sys

sys.path.insert(0, r"C:\Users\Administrator\Desktop\ORB")
import numpy as np
import pandas as pd

import backtest as b
from orb15_trail import SESSIONS, build_bars, entry_candidates, load_m1, simulate

lo = int(pd.Timestamp("2024-11-18", tz="UTC").timestamp() * 1000)
hi = int(pd.Timestamp("2026-11-17", tz="UTC").timestamp() * 1000)

for pair in ("EURUSD", "GBPUSD"):
    df = load_m1(pair, lo, hi)
    bars = build_bars(df)
    trend = b.build_trend(df, b.et_index(df))
    for name, sess in SESSIONS.items():
        c = entry_candidates(pair, df, bars, sess, trend)
        for v in ("none", "atr1.0"):
            tr = simulate(pair, df, bars, c, v)
            days = len({t["date"] for t in tr})
            r = np.array([t["R"] for t in tr])
            p = np.array([t["pips"] for t in tr])
            stop = np.mean([t["stop_pips"] for t in tr])
            print(
                f"{pair} {name:11} {v:7} n={len(tr):4d} days={days:4d} "
                f"perday={len(tr)/days:.2f} win={(r>0).mean()*100:4.1f}% "
                f"EV_R={r.mean():+.3f} EV_pips={p.mean():+.2f} avgStop={stop:.1f}p"
            )
