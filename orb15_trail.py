"""15-minute opening-range breakout with a 1.5R trail.

Variant of the NY / London ORB in this repo, tested on M1 data but run on the
15m clock:

  range   single 15m bar at session open (08:00 ET NY, 03:00 ET London)
  entry   first 15m CLOSE beyond range high/low +- 1.0 pip, before 12:00 ET
  bias    15m EMA200, last COMPLETED bar (same convention as backtest.py)
  stop    opposite side of the range
  trail   inactive until price reaches +1.5R, then stop follows the 15m bars
  exit    trailed stop, or 16:00 ET flat. No fixed take-profit.

Stop fills are resolved on M1 (conservative: stop checked before trail update).
Trail decisions are made only on completed 15m bars.

Usage:
  python orb15_trail.py                      # last 2 years, EURUSD + GBPUSD
  python orb15_trail.py --since 2024-11-18 --until 2026-11-17
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from collections import Counter

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import backtest as b  # noqa: E402

ROOT = r"E:\FOREX INTEL"
NY = "America/New_York"
TF_MS = 15 * 60_000
BUFFER_PIPS = 1.0
CUTOFF_MIN = 12 * 60
FLAT_MIN = 16 * 60
ACTIVATE_R = 1.5

PAIRS = {
    "EURUSD": dict(pip=0.0001, cost=0.8),
    "GBPUSD": dict(pip=0.0001, cost=1.0),
}
SESSIONS = {"ny_orb": 8 * 60, "london_orb": 3 * 60}


def files_for(pair: str, years: range) -> list[str]:
    if pair == "EURUSD":
        return [
            os.path.join(ROOT, "market_data", "EURUSD", "1m", "yearly", f"eurusd_1m_{y}.csv")
            for y in years
        ]
    return [
        os.path.join(ROOT, "market_data", "m1_16y",
                     "gbpusd-m1-bid-2010-01-01-2026-11-17T20-57.csv")
    ]


def load_m1(pair: str, since_ms: int, until_ms: int) -> pd.DataFrame:
    frames = []
    for path in files_for(pair, range(2023, 2027)):
        for chunk in pd.read_csv(
            path, usecols=["timestamp", "open", "high", "low", "close"], chunksize=1_000_000
        ):
            chunk = chunk[(chunk["timestamp"] >= since_ms) & (chunk["timestamp"] <= until_ms)]
            if len(chunk):
                frames.append(chunk)
    df = (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates("timestamp")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    return df


def build_bars(df: pd.DataFrame) -> dict:
    """Aggregate M1 into UTC-aligned 15m bars (started-at label)."""
    bid = df["timestamp"].to_numpy(np.int64) // TF_MS
    g = pd.DataFrame(
        {
            "bid": bid,
            "o": df["open"].to_numpy(),
            "h": df["high"].to_numpy(),
            "l": df["low"].to_numpy(),
            "c": df["close"].to_numpy(),
        }
    )
    agg = g.groupby("bid", sort=True).agg(
        o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last")
    )
    ids = agg.index.to_numpy(np.int64)
    start_ms = ids * TF_MS
    close_s = pd.Series(agg["c"].to_numpy())
    ema = close_s.ewm(span=200, adjust=False).mean().to_numpy()
    sign = np.where(agg["c"].to_numpy() > ema, 1, -1)
    sign_prev = np.concatenate([[0], sign[:-1]])

    prev_c = close_s.shift(1)
    tr = pd.concat(
        [
            agg["h"] - agg["l"],
            (agg["h"] - prev_c).abs(),
            (agg["l"] - prev_c).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1.0 / 14, adjust=False).mean().to_numpy()

    return dict(
        ids=ids,
        start_ms=start_ms,
        end_ms=start_ms + TF_MS,
        o=agg["o"].to_numpy(),
        h=agg["h"].to_numpy(),
        l=agg["l"].to_numpy(),
        c=agg["c"].to_numpy(),
        ema=ema,
        sign_prev=sign_prev,
        atr=atr,
        pos={int(k): i for i, k in enumerate(ids)},
    )


def entry_candidates(pair: str, df: pd.DataFrame, bars: dict, session_min: int,
                     trend: np.ndarray | None = None) -> list[dict]:
    """One breakout entry per ET day per session, evaluated on 15m closes."""
    pip = PAIRS[pair]["pip"]
    ts = df["timestamp"].to_numpy(np.int64)
    c = df["close"].to_numpy()
    et = pd.DatetimeIndex(pd.to_datetime(bars["start_ms"], unit="ms", utc=True)).tz_convert(NY)
    mins = et.hour * 60 + et.minute
    dates = et.date
    nb = len(bars["ids"])

    first_of_day: dict = {}
    for i in range(nb):
        if mins[i] >= session_min:
            first_of_day.setdefault(dates[i], i)

    out = []
    for day, p0 in sorted(first_of_day.items()):
        if mins[p0] != session_min:
            continue
        rhi = float(bars["h"][p0])
        rlo = float(bars["l"][p0])
        local = pd.Timestamp(day).tz_localize(NY)
        cutoff_ms = int((local + pd.Timedelta(minutes=CUTOFF_MIN)).tz_convert("UTC").timestamp() * 1000)
        deadline_ms = int((local + pd.Timedelta(minutes=FLAT_MIN)).tz_convert("UTC").timestamp() * 1000)
        for p in range(p0 + 1, nb):
            start = int(bars["start_ms"][p])
            if start >= cutoff_ms:
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
            if trend is not None and trend[j] != d:
                continue
            out.append(
                dict(
                    pair=pair,
                    day=day,
                    dir=d,
                    j=int(j),
                    entry=float(c[j]),
                    stop=float(rlo if d > 0 else rhi),
                    bar=p,
                    deadline_ms=deadline_ms,
                    range_pips=(rhi - rlo) / pip,
                )
            )
            break
    return out


def trail_candidate(variant: str, bars: dict, p: int, d: int, entry: float, risk: float) -> float:
    if variant == "be":
        return entry
    if variant == "bar":
        return float(bars["l"][p] if d > 0 else bars["h"][p])
    if variant.startswith("atr"):
        k = float(variant[3:])
        return float(bars["h"][p] - k * bars["atr"][p]) if d > 0 else float(bars["l"][p] + k * bars["atr"][p])
    if variant.startswith("close"):
        f = float(variant[5:])
        return float(bars["c"][p] - f * risk) if d > 0 else float(bars["c"][p] + f * risk)
    if variant.startswith("r"):
        f = float(variant[1:])
        return float(bars["h"][p] - f * risk) if d > 0 else float(bars["l"][p] + f * risk)
    raise ValueError(variant)


def simulate(pair: str, df: pd.DataFrame, bars: dict, cands: list[dict],
             variant: str, target_R: float | None = None) -> list[dict]:
    cfg = PAIRS[pair]
    pip = cfg["pip"]
    o = df["open"].to_numpy(); h = df["high"].to_numpy()
    l = df["low"].to_numpy(); c = df["close"].to_numpy()
    ts = df["timestamp"].to_numpy(np.int64)
    n = len(df)
    trailing = variant != "none"

    trades = []
    for e in cands:
        j = e["j"]; d = e["dir"]; entry = e["entry"]
        stop = e["stop"]
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        target = entry + d * target_R * risk if target_R else None
        active = False
        k_exit = j
        exit_price = None
        reason = "flat"

        for k in range(j + 1, n):
            if ts[k] >= e["deadline_ms"]:
                exit_price = float(c[k - 1]); reason = "flat"; k_exit = k - 1
                break
            if d > 0:
                if l[k] <= stop:
                    exit_price = float(min(o[k], stop)); reason = "stop"; k_exit = k; break
                if target is not None and h[k] >= target:
                    exit_price = float(max(o[k], target)); reason = "target"; k_exit = k; break
            else:
                if h[k] >= stop:
                    exit_price = float(max(o[k], stop)); reason = "stop"; k_exit = k; break
                if target is not None and l[k] <= target:
                    exit_price = float(min(o[k], target)); reason = "target"; k_exit = k; break

            if trailing and ts[k] // TF_MS != ts[k - 1] // TF_MS:
                p = bars["pos"].get(int(ts[k] // TF_MS) - 1)
                if p is not None:
                    if not active:
                        reach = (bars["h"][p] - entry) if d > 0 else (entry - bars["l"][p])
                        active = reach >= ACTIVATE_R * risk
                    if active:
                        cand = trail_candidate(variant, bars, p, d, entry, risk)
                        stop = max(stop, cand, entry) if d > 0 else min(stop, cand, entry)

        if exit_price is None:
            exit_price = float(c[min(k_exit, n - 1)])
        gross = d * (exit_price - entry) / pip
        pips = gross - cfg["cost"]
        trades.append(
            dict(
                pair=pair,
                session=e["day"],
                date=str(e["day"]),
                dir="long" if d > 0 else "short",
                entry_ms=int(ts[j]),
                entry_time=str(pd.Timestamp(ts[j], unit="ms", tz="UTC").tz_convert(NY)),
                stop_pips=round(risk / pip, 1),
                range_pips=round(e["range_pips"], 1),
                exit_ms=int(ts[k_exit]),
                pips=round(pips, 1),
                R=round(pips / (risk / pip), 3),
                reason=reason,
                hold_min=int((ts[k_exit] - ts[j]) / 60000),
                hit_trail=bool(active),
            )
        )
    return trades


def stats(trades: list[dict], label: str) -> dict:
    s = b.summarize(trades, label)
    s["trailed"] = sum(1 for t in trades if t["hit_trail"])
    s["avg_stop_pips"] = float(np.mean([t["stop_pips"] for t in trades])) if trades else 0.0
    s["avg_range_pips"] = float(np.mean([t["range_pips"] for t in trades])) if trades else 0.0
    return s


def line(s: dict, tag: str) -> str:
    if not s["trades"]:
        return f"{tag:34} n=0"
    return (
        f"{tag:34} n={s['trades']:5d} win={s['win_rate']:5.1f}% "
        f"avgR={s['avg_R']:+.3f} totR={s['total_R']:+8.1f} DD={s['max_dd_R']:7.1f} "
        f"t={s['t_stat']:+6.2f} stop/flat={s['stop_exits']:4d}/{s['flat_exits']:4d} "
        f"tgt={s['target_exits']:3d} trail={s['trailed']:4d} rng={s['avg_range_pips']:4.1f}p"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2024-11-18")
    ap.add_argument("--until", default="2026-11-17")
    ap.add_argument("--pairs", default="EURUSD,GBPUSD")
    ap.add_argument("--variants", default="none,be,bar,atr1.0,atr1.5,atr2.0,close0.5,close1.0,r0.5,r1.0")
    ap.add_argument("--bias", default="clean", choices=("clean", "repo"))
    args = ap.parse_args()

    since_ms = int(pd.Timestamp(args.since, tz="UTC").timestamp() * 1000)
    until_ms = int(pd.Timestamp(args.until, tz="UTC").timestamp() * 1000)
    pairs = [p.strip().upper() for p in args.pairs.split(",") if p.strip()]

    variants = [v.strip() for v in args.variants.split(",") if v.strip()]

    all_trades: dict[tuple, list[dict]] = {}
    print(f"window {args.since} -> {args.until} UTC  | 15m range bar, "
          f"entry<12:00 ET, flat 16:00 ET, trail arm {ACTIVATE_R}R")
    for pair in pairs:
        df = load_m1(pair, since_ms, until_ms)
        bars = build_bars(df)
        print(f"\n{pair}: {len(df):,} M1 bars  {df['timestamp'].iloc[0]} -> {df['timestamp'].iloc[-1]}")
        for name, sess in SESSIONS.items():
            trend = b.build_trend(df, b.et_index(df)) if args.bias == "repo" else None
            cands = entry_candidates(pair, df, bars, sess, trend)
            print(f"  {name}: {len(cands)} entry candidates")
            for v in variants:
                tr = simulate(pair, df, bars, cands, v)
                all_trades[(pair, name, v)] = tr
                print("   " + line(stats(tr, v), f"{name} {v}"))
            tr = simulate(pair, df, bars, cands, "none", target_R=ACTIVATE_R)
            all_trades[(pair, name, "tp1.5")] = tr
            print("   " + line(stats(tr, "tp1.5"), f"{name} tp1.5"))

    print("\n=== portfolio: EURUSD + GBPUSD, NY + London, same variant ===")
    for v in variants + ["tp1.5"]:
        tr = []
        for pair in pairs:
            for name in SESSIONS:
                tr.extend(all_trades[(pair, name, v)])
        tr.sort(key=lambda t: t["exit_ms"])
        print(line(stats(tr, v), v))

    print("\n=== per pair/session, best trail variant by total R ===")
    for pair in pairs:
        for name in SESSIONS:
            rows = [(v, stats(all_trades[(pair, name, v)], v)) for v in variants]
            rows = [r for r in rows if r[1]["trades"]]
            best = max(rows, key=lambda r: r[1]["total_R"])
            print(f"{pair:8} {name:12} best={best[0]:8} " + line(best[1], best[0])[35:])


if __name__ == "__main__":
    main()
