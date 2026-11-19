"""Multi-pair NY range breakout: EURUSD + GBPUSD + AUDUSD, max 3 trades/day.

Strategy is unchanged from the validated buffer-1.0 configuration:
  range  : 08:00-08:04 ET high/low
  entry  : first 1m close beyond range +/- 1.0 pip, must agree with 15m EMA200 bias
  stop   : opposite side of the range
  exit   : 16:00 ET time exit
  costs  : per-pair round-trip spread assumption (see PAIRS)

Max 3 trades/day = one trade per pair per day, three pairs. The cap is enforced
explicitly in case a future pair list grows.
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import backtest as b
import orb

ROOT = r"E:\FOREX INTEL"
OUT = os.path.join(HERE, "results", "multi")

WINDOW_START = "2021-11-05"
WINDOW_END = "2026-11-03"
LOAD_FROM = "2021-09-01"          # warmup for EMA200 on 15m
MAX_TRADES_PER_DAY = 3

PAIRS = {
    "EURUSD": {
        "files": [
            os.path.join(ROOT, "market_data", "EURUSD", "1m", "yearly", f"eurusd_1m_{y}.csv")
            for y in range(2021, 2027)
        ],
        "cost_pips": 0.8,
        "pip": 0.0001,
        "pip_value": 10.0,
    },
    "GBPUSD": {
        "files": [
            os.path.join(ROOT, "market_data", "m1_16y",
                         "gbpusd-m1-bid-2010-01-01-2026-11-17T20-57.csv")
        ],
        "cost_pips": 1.0,
        "pip": 0.0001,
        "pip_value": 10.0,
    },
    # AUDUSD M1 is not in the local dataset. AUDJPY is the closest available
    # pair (same base currency) and keeps the AUD leg the user asked for.
    "AUDJPY": {
        "files": [
            os.path.join(ROOT, "market_data", "m1_16y",
                         "audjpy-m1-bid-2010-01-01-2026-11-17T20-11.csv")
        ],
        "cost_pips": 1.4,
        "pip": 0.01,
        "pip_value": None,        # 1000 JPY per lot / USDJPY, filled per trade
    },
}

USDJPY_FILE = os.path.join(
    ROOT, "market_data", "m1_16y", "usdjpy-m1-bid-2010-01-01-2026-11-17T20-11.csv"
)


# ---------------------------------------------------------------- data

def load_m1(paths: list[str], since_ms: int | None = None) -> pd.DataFrame:
    frames = []
    for path in paths:
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        for chunk in pd.read_csv(
            path,
            usecols=["timestamp", "open", "high", "low", "close"],
            chunksize=1_000_000,
        ):
            if since_ms is not None:
                chunk = chunk[chunk["timestamp"] >= since_ms]
            if len(chunk):
                frames.append(chunk)
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    return df


def load_pair(name: str) -> tuple[pd.DataFrame, pd.DatetimeIndex, np.ndarray]:
    cfg = PAIRS[name]
    since = int(pd.Timestamp(LOAD_FROM, tz="UTC").timestamp() * 1000)
    df = load_m1(cfg["files"], since_ms=since)
    df = b.add_indicators(df)
    idx = b.et_index(df)
    trend = b.build_trend(df, idx, tf_min=15)
    return df, idx, trend


def pair_trades(name: str, df: pd.DataFrame, idx: pd.DatetimeIndex,
                trend: np.ndarray, usdjpy: tuple[np.ndarray, np.ndarray] | None = None) -> list[dict]:
    cfg = PAIRS[name]
    trades = orb.run_orb(
        df, idx, trend,
        use_bias=True, stop_mode="range", exit_mode="flat",
        buffer_pips=1.0, cost_pips=cfg["cost_pips"], pip=cfg["pip"],
    )
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    ts = df["timestamp"].to_numpy()

    for t in trades:
        i = int(np.searchsorted(ts, t["entry_ms"]))
        j = int(np.searchsorted(ts, t["exit_ms"]))
        d = 1 if t["dir"] == "long" else -1
        stop_dist = t["stop_pips"] * cfg["pip"]
        hi = h[i + 1:j + 1].max() if j > i else h[i]
        lo = l[i + 1:j + 1].min() if j > i else l[i]
        mfe = (d * (hi - t["entry"]) / stop_dist) if d > 0 else (d * (t["entry"] - lo) / stop_dist)
        mae = (d * (lo - t["entry"]) / stop_dist) if d > 0 else (d * (t["entry"] - hi) / stop_dist)
        t["mfe_r"] = max(0.0, float(mfe))
        # floating loss cannot exceed the stop; gap fills stay worse than -1
        t["mae_r"] = min(0.0, max(float(mae), -1.0), float(t["R"]))
        t["pair"] = name
        t["pip_value"] = cfg["pip_value"]
        if t["pip_value"] is None:
            if usdjpy is None:
                raise ValueError("USDJPY map required for JPY pairs")
            uts, ucl = usdjpy
            k = int(np.searchsorted(uts, t["entry_ms"], side="right")) - 1
            usd_jpy = float(ucl[max(k, 0)])
            # 1 pip = 0.01 JPY x 100,000 units = 1000 JPY per lot
            t["pip_value"] = 1000.0 / usd_jpy
    return trades


def minute_path(name: str, df: pd.DataFrame, t: dict) -> list[tuple[int, float, float, float]]:
    """Per-minute (timestamp, adverse R, favourable R, mark-to-market R)."""
    cfg = PAIRS[name]
    ts = df["timestamp"].to_numpy()
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    c = df["close"].to_numpy()
    i = int(np.searchsorted(ts, t["entry_ms"]))
    j = int(np.searchsorted(ts, t["exit_ms"]))
    d = 1 if t["dir"] == "long" else -1
    stop_dist = t["stop_pips"] * cfg["pip"]
    out = []
    for k in range(i + 1, min(j + 1, len(ts))):
        lo_r = d * ((l[k] if d > 0 else h[k]) - t["entry"]) / stop_dist
        hi_r = d * ((h[k] if d > 0 else l[k]) - t["entry"]) / stop_dist
        net_r = float(t["R"]) if k >= j else d * (c[k] - t["entry"]) / stop_dist
        out.append((int(ts[k]), min(0.0, max(float(lo_r), -1.0)), max(0.0, float(hi_r)),
                    float(net_r)))
    return out


def day_envelopes(trades: list[dict]) -> list[dict]:
    """Per-day equity envelope in R: worst floating low, best mark-to-market high."""
    adv: dict[int, float] = {}
    fav: dict[int, float] = {}
    net: dict[int, float] = {}
    by_day: dict[str, list[dict]] = {}
    for t in trades:
        by_day.setdefault(t["date"], []).append(t)
        for ms, a, f, n in t["_path"]:
            adv[ms] = adv.get(ms, 0.0) + a
            fav[ms] = fav.get(ms, 0.0) + f
            net[ms] = net.get(ms, 0.0) + n
    rows = []
    for d in sorted(by_day):
        mss = [ms for t in by_day[d] for ms, _, _, _ in t["_path"]]
        if not mss:
            continue
        rows.append({
            "date": d,
            "trades": len(by_day[d]),
            "adv_min_r": min(adv[ms] for ms in mss),
            "fav_max_r": max(fav[ms] for ms in mss),
            "net_max_r": max(net[ms] for ms in mss),
            "net_min_r": min(net[ms] for ms in mss),
            "R": round(sum(t["R"] for t in by_day[d]), 4),
            "risk_R": round(sum(abs(t["R"]) for t in by_day[d] if t["R"] < 0), 4),
        })
    return rows


# ---------------------------------------------------------------- stats

def daily_r(trades: list[dict]) -> dict[str, float]:
    out: dict[str, float] = {}
    for t in trades:
        out[t["date"]] = out.get(t["date"], 0.0) + t["R"]
    return dict(sorted(out.items()))


def equity_dd_r(daily: dict[str, float]) -> float:
    eq = peak = worst = 0.0
    for d in sorted(daily):
        eq += daily[d]
        peak = max(peak, eq)
        worst = min(worst, eq - peak)
    return worst


def streak(daily: dict[str, float]) -> int:
    best = cur = 0
    for d in sorted(daily):
        if daily[d] <= 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def pair_summary(name: str, trades: list[dict]) -> dict:
    s = b.summarize(trades, name)
    s["pair"] = name
    s["total_pips"] = round(sum(t["pips"] for t in trades), 1)
    s["cost_pips"] = PAIRS[name]["cost_pips"]
    d = daily_r(trades)
    s["trading_days"] = len(d)
    s["daily_avg_R"] = float(np.mean(list(d.values()))) if d else 0.0
    s["max_dd_daily_R"] = equity_dd_r(d)
    s["daily_loss_streak"] = streak(d)
    s["date_first"] = trades[0]["date"] if trades else None
    s["date_last"] = trades[-1]["date"] if trades else None
    return s


def yearly(trades: list[dict]) -> dict[str, dict]:
    by: dict[str, list[dict]] = {}
    for t in trades:
        by.setdefault(t["date"][:4], []).append(t)
    return {y: b.summarize(v, y) for y, v in sorted(by.items())}


# ---------------------------------------------------------------- main

def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    start_ms = int(pd.Timestamp(WINDOW_START, tz="UTC").timestamp() * 1000)
    end_ms = int(pd.Timestamp(WINDOW_END, tz="UTC").timestamp() * 1000) + 86_400_000

    all_trades: list[dict] = []
    per_pair: dict[str, dict] = {}
    per_pair_yearly: dict[str, dict] = {}

    since = int(pd.Timestamp(LOAD_FROM, tz="UTC").timestamp() * 1000)
    udf = load_m1([USDJPY_FILE], since_ms=since)
    usdjpy = (udf["timestamp"].to_numpy(), udf["close"].to_numpy())
    print(f"USDJPY bars for pip value: {len(udf):,}")

    for name in PAIRS:
        df, idx, trend = load_pair(name)
        trades = pair_trades(name, df, idx, trend, usdjpy=usdjpy)
        trades = [t for t in trades if start_ms <= t["entry_ms"] <= end_ms]
        trades.sort(key=lambda t: t["entry_ms"])

        # minute-level adverse path for the concurrency check
        paths = {id(t): minute_path(name, df, t) for t in trades}
        for t in trades:
            t["_path"] = paths[id(t)]

        all_trades.extend(trades)
        per_pair[name] = pair_summary(name, trades)
        per_pair_yearly[name] = yearly(trades)

        with open(os.path.join(OUT, f"days_{name}.csv"), "w", newline="", encoding="utf-8") as f:
            rows = day_envelopes(trades)
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)

        b.print_summary(per_pair[name])
        s = per_pair[name]
        print(f"{'':26} pips={s['total_pips']:+8.1f}  days={s['trading_days']:>4}  "
              f"maxDD(daily)={s['max_dd_daily_R']:6.1f}R  dailyStreak={s['daily_loss_streak']:>2}")
        print()

    # ---- enforce max 3 trades/day (one per pair) and build portfolio
    by_day: dict[str, list[dict]] = {}
    for t in sorted(all_trades, key=lambda t: t["entry_ms"]):
        by_day.setdefault(t["date"], []).append(t)

    capped: dict[str, list[dict]] = {}
    dropped = 0
    for d, ts in by_day.items():
        ts = sorted(ts, key=lambda t: t["entry_ms"])
        if len(ts) > MAX_TRADES_PER_DAY:
            dropped += len(ts) - MAX_TRADES_PER_DAY
            ts = ts[:MAX_TRADES_PER_DAY]
        capped[d] = ts

    portfolio = [t for d in sorted(capped) for t in capped[d]]
    port_daily = daily_r(portfolio)

    # pairwise daily-R correlation on the union of trading days
    days = sorted(set().union(*[set(daily_r([t for t in portfolio if t["pair"] == p])) for p in PAIRS]))
    mat = {}
    for p in PAIRS:
        dp = daily_r([t for t in portfolio if t["pair"] == p])
        mat[p] = [dp.get(d, 0.0) for d in days]
    corr = {}
    for i, p1 in enumerate(PAIRS):
        for p2 in list(PAIRS)[i + 1:]:
            a = np.array(mat[p1]); bb = np.array(mat[p2])
            both = (a != 0) | (bb != 0)
            corr[f"{p1}-{p2}"] = float(np.corrcoef(a[both], bb[both])[0, 1]) if both.sum() > 2 else 0.0

    # concurrency: count overlapping trades and worst simultaneous floating loss
    # per-minute sum of adverse / favourable R across all open trades
    adv: dict[int, float] = {}
    fav: dict[int, float] = {}
    net: dict[int, float] = {}
    cnt: dict[int, int] = {}
    for t in portfolio:
        for ms, a, f, n in t["_path"]:
            adv[ms] = adv.get(ms, 0.0) + a
            fav[ms] = fav.get(ms, 0.0) + f
            net[ms] = net.get(ms, 0.0) + n
            cnt[ms] = cnt.get(ms, 0) + 1

    max_concurrent = max(cnt.values()) if cnt else 0
    worst_float_r = min(adv.values()) if adv else 0.0

    # per-day envelope, in R, used by the prop simulator
    day_rows = day_envelopes(portfolio)

    for t in portfolio:
        t.pop("_path", None)

    port_summary = b.summarize(portfolio, "PORTFOLIO")
    port_summary.update({
        "pair": "PORTFOLIO",
        "trading_days": len(port_daily),
        "trades_per_day": len(portfolio) / len(port_daily) if port_daily else 0.0,
        "daily_avg_R": float(np.mean(list(port_daily.values()))) if port_daily else 0.0,
        "daily_sd_R": float(np.std(list(port_daily.values()), ddof=1)) if len(port_daily) > 1 else 0.0,
        "max_dd_daily_R": equity_dd_r(port_daily),
        "daily_loss_streak": streak(port_daily),
        "positive_days_pct": 100.0 * sum(1 for v in port_daily.values() if v > 0) / len(port_daily) if port_daily else 0.0,
        "max_concurrent_trades": max_concurrent,
        "worst_simultaneous_float_R": worst_float_r,
        "dropped_over_cap": dropped,
    })
    b.print_summary(port_summary)
    print(f"{'':26} days={port_summary['trading_days']}  trades/day={port_summary['trades_per_day']:.2f}  "
          f"dailyAvg={port_summary['daily_avg_R']:+.3f}R  maxDD(daily)={port_summary['max_dd_daily_R']:.1f}R  "
          f"maxConcurrent={max_concurrent}  worstFloat={worst_float_r:.2f}R")
    print("daily-R correlation:", {k: round(v, 3) for k, v in corr.items()})

    # ---- save
    fields = ["date", "pair", "dir", "entry_ms", "entry_time", "entry", "stop", "range_pips",
              "stop_pips", "exit_ms", "exit_time", "exit", "gross_pips", "pips", "R",
              "reason", "hold_min", "mfe_r", "mae_r", "pip_value"]
    with open(os.path.join(OUT, "trades_portfolio.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(portfolio)
    with open(os.path.join(OUT, "daily_R.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["date", "R", "trades"])
        for d in sorted(port_daily):
            w.writerow([d, round(port_daily[d], 4), len(capped[d])])
    with open(os.path.join(OUT, "days.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(day_rows[0].keys()))
        w.writeheader(); w.writerows(day_rows)

    out = {
        "window": {"start": WINDOW_START, "end": WINDOW_END},
        "pairs": per_pair,
        "portfolio": port_summary,
        "yearly": per_pair_yearly,
        "daily_r_correlation": corr,
        "max_concurrent_trades": max_concurrent,
        "worst_simultaneous_float_R": worst_float_r,
        "dropped_over_cap": dropped,
        "cost_pips": {p: PAIRS[p]["cost_pips"] for p in PAIRS},
    }
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=float)
    print(f"saved -> {OUT}")


if __name__ == "__main__":
    main()
