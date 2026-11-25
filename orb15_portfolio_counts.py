import sys

sys.path.insert(0, r"C:\Users\Administrator\Desktop\ORB")
import numpy as np
import pandas as pd

import backtest as b
from orb15_trail import SESSIONS, build_bars, entry_candidates, load_m1, simulate

lo = int(pd.Timestamp("2024-11-18", tz="UTC").timestamp() * 1000)
hi = int(pd.Timestamp("2026-11-17", tz="UTC").timestamp() * 1000)

for v in ("none", "atr1.0"):
    allt, days = [], set()
    for pair in ("EURUSD", "GBPUSD"):
        df = load_m1(pair, lo, hi)
        bars = build_bars(df)
        trend = b.build_trend(df, b.et_index(df))
        for name, sess in SESSIONS.items():
            tr = simulate(pair, df, bars, entry_candidates(pair, df, bars, sess, trend), v)
            allt.extend(tr)
            days |= {t["date"] for t in tr}
    r = np.array([t["R"] for t in allt])
    p = np.array([t["pips"] for t in allt])
    print(
        f"{v:7} n={len(allt)} days={len(days)} perday={len(allt)/len(days):.2f} "
        f"win={(r>0).mean()*100:.1f}% EV_R={r.mean():+.3f} EV_pips={p.mean():+.2f} "
        f"avgWin={r[r>0].mean():+.2f}R avgLoss={r[r<=0].mean():+.2f}R"
    )
