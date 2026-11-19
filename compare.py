"""Side-by-side comparison: NY-ORB-only vs the combined 3-strategy portfolio."""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "results")

NY = os.path.join(BASE, "multi", "prop", "summary.json")
COMBO = os.path.join(BASE, "combo", "prop", "summary.json")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def table(name, s):
    print(f"\n=== {name} ===")
    print(f"{'risk':>8} {'hist pass':>10} {'MC pass':>8} {'maxDD br':>9} "
          f"{'med days':>9} {'DD p95':>7} {'worst':>7}")
    hist = {round(r["risk_pct"], 6): r for r in s["historical"]}
    for mc in s["monte_carlo"]:
        r = round(mc["risk_pct"], 6)
        h = hist.get(r)
        if h is None:
            continue
        print(f"{100*r:7.3f}% {h['pass_rate_resolved']:9.1f}% {mc['pass_prob']:7.1f}% "
              f"{mc['maxdd_breach_prob']:8.1f}% {h['median_days_to_pass']:9.0f} "
              f"{mc['dd_p95']:6.1f}% {mc['dd_worst']:6.1f}%")


def main():
    ny = load(NY)
    cb = load(COMBO)
    print(f"NY-only  : {ny['trading_days']} days, {ny['trades']} trades, "
          f"{ny['avg_trades_per_day']:.2f}/day")
    print(f"Combined : {cb['trading_days']} days, {cb['trades']} trades, "
          f"{cb['avg_trades_per_day']:.2f}/day")
    table("NY ORB only", ny)
    table("Combined 3 strategies", cb)

    # time-to-pass comparison at equal Monte Carlo pass probability
    print("\n=== fastest config that keeps MC pass >= 95% ===")
    for name, s in (("NY ORB only", ny), ("Combined", cb)):
        ok = [m for m in s["monte_carlo"] if m["pass_prob"] >= 95.0]
        if ok:
            best = min(ok, key=lambda m: m["median_trading_days_to_pass"])
            print(f"{name:<12} risk={100*best['risk_pct']:.3f}%  MC={best['pass_prob']:.1f}%  "
                  f"median trading days={best['median_trading_days_to_pass']:.0f}  "
                  f"dd p95={best['dd_p95']:.1f}%")
        else:
            best = max(s["monte_carlo"], key=lambda m: m["pass_prob"])
            print(f"{name:<12} no config >=95%; best {100*best['risk_pct']:.3f}% -> "
                  f"{best['pass_prob']:.1f}%")


if __name__ == "__main__":
    main()
