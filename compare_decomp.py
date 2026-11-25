import sys

sys.path.insert(0, r"C:\Users\Administrator\Desktop\ORB")
import pandas as pd

import lab
from orb15_decomp import cands_range5_entry1m
from orb15_trail import load_m1, build_bars, simulate

SINCE = pd.Timestamp("2024-11-18", tz="UTC")
UNTIL = pd.Timestamp("2026-11-17", tz="UTC")
lo, hi = int(SINCE.timestamp() * 1000), int(UNTIL.timestamp() * 1000)

base = lab.session_orb("EURUSD", 8 * 60, 5, 12 * 60, 16 * 60, 1.0, True, "range", "ny")
base = [t for t in base if lo <= t["entry_ms"] <= hi]

df = load_m1("EURUSD", lo, hi)
bars = build_bars(df)
cands = cands_range5_entry1m("EURUSD", df, bars, 8 * 60)
mine = simulate("EURUSD", df, bars, cands, "none")

print(f"baseline n={len(base)}  mine n={len(mine)}")
bd = {t["date"]: t for t in base}
md = {t["date"]: t for t in mine}
print("days only baseline:", len(set(bd) - set(md)), " only mine:", len(set(md) - set(bd)))
diff = 0
for d in sorted(set(bd) & set(md)):
    a, c = bd[d], md[d]
    if abs(a["R"] - c["R"]) > 1e-6:
        diff += 1
        if diff <= 8:
            print(f"{d} base dir={a['dir']} R={a['R']:+.2f} pips={a['pips']:+.1f} stop={a['stop_pips']:.1f} "
                  f"| mine dir={c['dir']} R={c['R']:+.2f} pips={c['pips']:+.1f} stop={c['stop_pips']:.1f}")
print("R mismatches on common days:", diff)
