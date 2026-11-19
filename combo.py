"""Combined multi-strategy portfolio: NY ORB + London ORB + prev-day level.

All three families passed the screen (screen.py) and the split-sample / cost /
parameter stress test (validate.py). This script runs them together, builds the
minute-level equity envelope across every open position, and writes the daily
envelope that the prop simulator consumes.

Families (entry/stop/exit logic untouched):
  ny_orb     08:00 ET 5-bar range breakout, EMA200 bias, range stop, 16:00 ET flat
  london_orb 03:00 ET 5-bar range breakout, EMA200 bias, range stop, 16:00 ET flat
  prev_level previous ET day high/low breakout during the London session, other-side stop

Usage:
  python combo.py            # core 3 pairs
  python combo.py wide       # + USDJPY, GBPJPY
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lab
import backtest as b

OUT = os.path.join(HERE, "results", "combo")

WINDOW_START = "2016-01-01"
WINDOW_END = "2026-11-03"

CORE = ["EURUSD", "GBPUSD", "AUDJPY"]
WIDE = ["EURUSD", "GBPUSD", "USDJPY", "AUDJPY", "GBPJPY"]

STRATS = {
    "ny_orb": lambda p: lab.session_orb(p, 8 * 60, 5, 12 * 60, 16 * 60, 1.0, True, "range", "ny_orb", with_path=True),
    "london_orb": lambda p: lab.session_orb(p, 3 * 60, 5, 12 * 60, 16 * 60, 1.0, True, "range", "london_orb", with_path=True),
    "prev_level": lambda p: lab.level_break(p, "prev_day", 3 * 60, 12 * 60, 16 * 60, 1.0, True, "other_side", 1.0, "prev_level", with_path=True),
}

USDJPY_FILE = os.path.join(
    r"E:\FOREX INTEL", "market_data", "m1_16y",
    "usdjpy-m1-bid-2010-01-01-2026-11-17T20-11.csv",
)


def usdjpy_close() -> tuple[np.ndarray, np.ndarray]:
    ts, cl = [], []
    for chunk in pd.read_csv(USDJPY_FILE, usecols=["timestamp", "close"], chunksize=1_000_000):
        ts.append(chunk["timestamp"].to_numpy())
        cl.append(chunk["close"].to_numpy())
    return np.concatenate(ts), np.concatenate(cl)


def collect(pairs: list[str], start: str = WINDOW_START) -> list[dict]:
    trades: list[dict] = []
    for pair in pairs:
        lab._cache.clear()
        print(f"loading {pair} ...", flush=True)
        for name, fn in STRATS.items():
            tr = fn(pair)
            tr = [t for t in tr if start <= t["date"] <= WINDOW_END]
            for t in tr:
                t["strategy"] = name
            trades.extend(tr)
            s = lab.stats(tr, name)
            print(f"  {name:<11} n={s['trades']:>5} avgR={s['avg_R']:+.3f} "
                  f"totR={s['total_R']:+8.1f} DD={s['max_dd_R']:7.1f} t={s['t']:+5.2f}", flush=True)
        lab._cache.clear()
    trades.sort(key=lambda t: (t["entry_ms"], t["pair"], t["strategy"]))
    return trades


def pip_values(trades: list[dict]) -> None:
    uts, ucl = usdjpy_close()
    for t in trades:
        if t["pair"].endswith("JPY"):
            k = int(np.searchsorted(uts, t["entry_ms"], side="right")) - 1
            t["pip_value"] = 1000.0 / float(ucl[max(k, 0)])
        else:
            t["pip_value"] = 10.0


def envelopes(trades: list[dict]) -> list[dict]:
    """Per-day minute envelope in R, summed across every open position."""
    grid: dict[str, np.ndarray] = {}
    day_R: dict[str, float] = defaultdict(float)
    day_n: dict[str, int] = defaultdict(int)
    for t in trades:
        d = t["date"]
        arr = grid.get(d)
        if arr is None:
            arr = np.zeros((1440, 4), dtype=np.float64)
            grid[d] = arr
        day_R[d] += t["R"]
        day_n[d] += 1
        for ms, a, f, n in t["_path"]:
            m = (ms // 60000) % 1440
            arr[m, 0] += a
            arr[m, 1] += f
            arr[m, 2] += n
            arr[m, 3] += 1

    rows = []
    for d in sorted(grid):
        arr = grid[d]
        mask = arr[:, 3] > 0
        if not mask.any():
            continue
        rows.append({
            "date": d,
            "trades": day_n[d],
            "adv_min_r": round(float(arr[mask, 0].min()), 4),
            "fav_max_r": round(float(arr[mask, 1].max()), 4),
            "net_max_r": round(float(arr[mask, 2].max()), 4),
            "net_min_r": round(float(arr[mask, 2].min()), 4),
            "R": round(day_R[d], 4),
        })
    return rows


def daily_r(trades: list[dict], key=lambda t: "ALL") -> dict[str, float]:
    out: dict[str, float] = {}
    for t in trades:
        k = key(t)
        out[k] = out.get(k, 0.0) + t["R"]
    return out


def by_day(trades: list[dict], key=lambda t: "ALL") -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for t in trades:
        out.setdefault(key(t), {})
    for t in trades:
        d = out[key(t)]
        d[t["date"]] = d.get(t["date"], 0.0) + t["R"]
    return out


def corr(a: dict[str, float], b: dict[str, float]) -> float:
    days = sorted(set(a) | set(b))
    x = np.array([a.get(d, 0.0) for d in days])
    y = np.array([b.get(d, 0.0) for d in days])
    if x.std() == 0 or y.std() == 0:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "core"
    start = sys.argv[2] if len(sys.argv) > 2 else WINDOW_START
    if arg == "core":
        tag, pairs = "core", CORE
    elif arg == "wide":
        tag, pairs = "wide", WIDE
    else:
        pairs = [p.strip().upper() for p in arg.split(",") if p.strip()]
        tag = "_".join(p.lower() for p in pairs)
    if start != WINDOW_START:
        tag = f"{tag}_{start[:4]}"
    out_dir = OUT if tag == "core" else os.path.join(OUT, tag)
    os.makedirs(out_dir, exist_ok=True)

    print(f"pairs: {pairs}")
    trades = collect(pairs, start)
    pip_values(trades)

    # ---- portfolio level stats
    port_daily: dict[str, float] = {}
    for t in trades:
        port_daily[t["date"]] = port_daily.get(t["date"], 0.0) + t["R"]
    eq = peak = worst = 0.0
    for d in sorted(port_daily):
        eq += port_daily[d]
        peak = max(peak, eq)
        worst = min(worst, eq - peak)

    n = len(trades)
    r = np.array([t["R"] for t in trades])
    sd = r.std(ddof=1)
    print(f"\n=== portfolio: n={n}  days={len(port_daily)}  avgR={r.mean():+.3f}  "
          f"totR={r.sum():+.1f}  maxDD={worst:.1f}R  t={r.mean()/(sd/np.sqrt(n)):+.2f}")

    # per strategy / pair
    combo_keys = [(s, p) for s in STRATS for p in pairs]
    per = {}
    for s, p in combo_keys:
        tr = [t for t in trades if t["strategy"] == s and t["pair"] == p]
        if not tr:
            continue
        st = lab.stats(tr, f"{s}:{p}")
        per[f"{s}:{p}"] = {k: st[k] for k in
                           ("trades", "avg_R", "total_R", "max_dd_R", "calmar", "t",
                            "positive_years", "n_years")}
        print(f"  {s:<11}{p:<7} n={st['trades']:>5} avgR={st['avg_R']:+.3f} "
              f"totR={st['total_R']:+8.1f} DD={st['max_dd_R']:7.1f} t={st['t']:+5.2f} "
              f"yr={st['positive_years']}/{st['n_years']}")

    # strategy-level
    strat_daily = by_day(trades, key=lambda t: t["strategy"])
    strat_stats = {}
    for s in STRATS:
        tr = [t for t in trades if t["strategy"] == s]
        st = lab.stats(tr, s)
        strat_stats[s] = {k: st[k] for k in
                          ("trades", "avg_R", "total_R", "max_dd_R", "calmar", "t",
                           "positive_years", "n_years")}
    print("\n--- by strategy ---")
    for s, st in strat_stats.items():
        print(f"  {s:<11} n={st['trades']:>5} totR={st['total_R']:+8.1f} "
              f"DD={st['max_dd_R']:7.1f} calmar={st['calmar']:6.2f} t={st['t']:+5.2f}")

    names = list(STRATS)
    corr_mat = {}
    for i, a in enumerate(names):
        for bb in names[i + 1:]:
            corr_mat[f"{a}-{bb}"] = corr(strat_daily[a], strat_daily[bb])
    print("strategy daily-R correlation:", {k: round(v, 3) for k, v in corr_mat.items()})

    # pair-level correlation (all strategies pooled per pair)
    pair_daily = by_day(trades, key=lambda t: t["pair"])
    pair_corr = {}
    for i, a in enumerate(pairs):
        for bb in pairs[i + 1:]:
            pair_corr[f"{a}-{bb}"] = corr(pair_daily[a], pair_daily[bb])
    print("pair daily-R correlation:", {k: round(v, 3) for k, v in pair_corr.items()})

    # concurrency
    cnt: dict[int, int] = {}
    adv: dict[int, float] = {}
    for t in trades:
        for ms, a, _f, _n in t["_path"]:
            cnt[ms] = cnt.get(ms, 0) + 1
            adv[ms] = adv.get(ms, 0.0) + a
    max_conc = max(cnt.values()) if cnt else 0
    worst_float = min(adv.values()) if adv else 0.0
    trades_per_day = defaultdict(int)
    for t in trades:
        trades_per_day[t["date"]] += 1
    tpd = sorted(trades_per_day.values())
    print(f"max concurrent={max_conc}  worst simultaneous float={worst_float:.2f}R  "
          f"trades/day median={np.median(tpd):.0f} max={max(tpd)}")

    rows = envelopes(trades)
    print(f"day envelope: {len(rows)} days, worst adv={min(r['adv_min_r'] for r in rows):.2f}R")

    # ---- save
    fields = ["date", "pair", "strategy", "dir", "entry_ms", "entry_time", "entry", "stop",
              "stop_pips", "exit_ms", "exit_time", "exit", "gross_pips", "pips", "R",
              "reason", "hold_min", "pip_value"]
    with open(os.path.join(out_dir, "trades_combo.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(trades)
    with open(os.path.join(out_dir, "days.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    with open(os.path.join(out_dir, "daily_R.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["date", "R", "trades"])
        for d in sorted(port_daily):
            w.writerow([d, round(port_daily[d], 4), trades_per_day[d]])

    summary = {
        "tag": tag,
        "pairs": pairs,
        "window": {"start": start, "end": WINDOW_END},
        "portfolio": {
            "trades": n,
            "trading_days": len(port_daily),
            "trades_per_day": n / len(port_daily),
            "avg_R": float(r.mean()),
            "total_R": float(r.sum()),
            "max_dd_R": float(worst),
            "calmar": float(r.sum() / abs(worst)) if worst else None,
            "t": float(r.mean() / (sd / np.sqrt(n))),
            "daily_sd_R": float(np.std(list(port_daily.values()), ddof=1)),
            "max_concurrent": max_conc,
            "worst_simultaneous_float_R": worst_float,
            "trades_per_day_median": float(np.median(tpd)),
            "trades_per_day_max": int(max(tpd)),
        },
        "strategies": strat_stats,
        "per_pair_strategy": per,
        "strategy_correlation": corr_mat,
        "pair_correlation": pair_corr,
        "yearly": {s: lab.stats([t for t in trades if t["date"][:4] == s], s)["total_R"]
                   for s in sorted({t["date"][:4] for t in trades})},
    }
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=float)
    print(f"saved -> {out_dir}")


if __name__ == "__main__":
    main()
