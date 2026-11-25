"""Diagnostic: repo's original 5xM1-bar ORB over the same 2-year window,
so the 15m variant can be compared against its own baseline."""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lab  # noqa: E402
import backtest as b  # noqa: E402

SINCE = pd.Timestamp("2024-11-18", tz="UTC")
UNTIL = pd.Timestamp("2026-11-17", tz="UTC")

for pair in ("EURUSD", "GBPUSD"):
    for name, sess in (("ny_orb", 8 * 60), ("london_orb", 3 * 60)):
        trades = lab.session_orb(pair, sess, 5, 12 * 60, 16 * 60, 1.0, True, "range", name)
        df = pd.DataFrame(trades)
        df["entry_ms"] = df["entry_ms"].astype("int64")
        m = (df["entry_ms"] >= int(SINCE.timestamp() * 1000)) & (
            df["entry_ms"] <= int(UNTIL.timestamp() * 1000)
        )
        sub = df[m]
        s = b.summarize(sub.to_dict("records"), f"{pair} {name}")
        print(f"{pair} {name:11} 2y n={s['trades']:4d} avgR={s['avg_R']:+.3f} "
              f"totR={s['total_R']:+7.1f} DD={s['max_dd_R']:7.1f} t={s['t_stat']:+5.2f} "
              f"win={s['win_rate']:4.1f}%")
