# Intraday breakout portfolio — EURUSD / GBPUSD / AUDJPY

Three intraday breakout edges on M1 FX data, tested from 2016 to 2026 and simulated
against the AquaFunded **2-Step Pro** evaluation rules.

The original strategy is a New York opening-range breakout. Two more families were
added after a screen of eight families on five pairs and a split-sample validation:
a London opening-range breakout and a previous-day high/low breakout.

## The three families

All three share the same execution rules: entry on a 1-minute close, stop from market
structure, no fixed take-profit, flat at 16:00 ET, per-pair round-trip cost.

| Family | Entry | Stop | Bias |
|---|---|---|---|
| `ny_orb` | 08:00 ET 5-bar range breakout ±1.0 pip, before 12:00 ET | opposite side of the range | 15m EMA200 |
| `london_orb` | 03:00 ET 5-bar range breakout ±1.0 pip, before 12:00 ET | opposite side of the range | 15m EMA200 |
| `prev_level` | previous ET-day high/low breakout during the London session, ±1.0 pip | opposite side of the prior day's range | 15m EMA200 |

Costs, round trip: EURUSD 0.8 pip, GBPUSD 1.0, AUDJPY 1.4.

## Results, 2016-01-04 → 2026-11-03

| Family | Trades | Avg R | Total R | Max DD | Calmar | t | Positive years |
|---|---|---|---|---|---|---|---|
| `ny_orb` | 7,959 | +0.335 | +2,665.4 | −52.9R | 50.4 | 9.28 | 11/11 |
| `london_orb` | 8,225 | +0.637 | +5,239.5 | −52.9R | 99.1 | 16.83 | 11/11 |
| `prev_level` | 5,741 | +0.172 | +990.3 | −8.9R | 110.9 | 19.51 | 11/11 |
| **Portfolio** | **21,925** | **+0.406** | **+8,895.1** | **−76.1R** | **116.8** | **20.81** | **11/11** |

7.79 trades/day, max 9 concurrent. Longest losing streak 27 trades / 14 days.
Every calendar year is positive (648–995R).

Daily-R correlation between families: ny–london 0.18, ny–prev 0.25, london–prev 0.44.
Pair correlation: EURUSD–GBPUSD 0.33, EURUSD–AUDJPY 0.07, GBPUSD–AUDJPY 0.07.

## Prop evaluation (AquaFunded 2-Step Pro)

Rules: Phase 1 +10%, Phase 2 +5%, daily drawdown 5% of the higher of balance/equity at
00:00 UTC, max drawdown 10% **trailing** (floor = peak − $500 on a $5,000 account), no
time limit, no minimum trading days. See `results/prop/rules_verified.json`.

Monte Carlo, 20,000 runs, whole trading days resampled:

| Risk/trade | Historical pass | MC pass | Max-DD breach | Median calendar days |
|---|---|---|---|---|
| 0.050% | 100.0% | 100.0% | 0.0% | 132 |
| 0.075% | 100.0% | 100.0% | 0.03% | 87 |
| **0.100%** | **100.0%** | **99.6%** | **0.39%** | **68** |
| **0.125%** | **98.3%** | **98.1%** | **1.87%** | **55** |
| **0.150%** | **96.4%** | **95.1%** | **4.94%** | **46** |
| 0.250% | 71.5% | 70.7% | 29.3% | 23 |
| 0.500% | 24.9% | 24.3% | 75.7% | 7 |

The trailing max drawdown is the only binding rule; the daily limit never triggers.

**Recommended: 0.10% per trade** (99.6% MC, ~68 days). **0.125%** is the fastest
defensible setting — 76.1R x 0.125% = 9.5%, just inside the 10% limit — at 98.1% MC and
~55 days. **0.15%** is the hard ceiling.

Compared with the NY-ORB-only portfolio, at the same 0.10% risk the combined book passes
in 68 days instead of 182 with a higher pass probability. At the same 95% MC pass
probability it is 4.0x faster (33 vs 132 trading days).

Full report: [`results/combo/REPORT.md`](results/combo/REPORT.md).

## Validation

`screen.py` tested eight families on five pairs over 2016–2026 and ranked them by
total R / max R drawdown. `validate.py` then checked the two survivors on 2011–2015 —
a period never used for selection — plus doubled costs and an 18-point parameter grid.

| Family | 2011–2015 avg R (5 pairs) | 2x cost avg R | Grid Calmar min–median–max |
|---|---|---|---|
| `london_orb` | +0.50 to +0.88 | +0.34 to +0.68 | 43.3 – 65.2 – 76.1 |
| `prev_level` | +0.10 to +0.23 | +0.09 to +0.19 | holds |

`momentum_1000` and `reversal_1500` were rejected: their stops used 1x M1 ATR (~1 pip),
so the results were cost and microstructure noise.

## Layout

```
backtest.py               data loader, indicators, EMA20 first-candle baseline
orb.py                    range-breakout engine (bias, stop mode, exit mode, buffer)
lab.py                    generic engines: session_orb, level_break, time_momentum, close_reversal
screen.py                 eight families x five pairs, ranked by return / drawdown
validate.py               split-sample, doubled cost, parameter grid
multi_pair.py             NY-ORB three-pair portfolio, daily envelopes
combo.py                  three-family portfolio, minute-level equity envelope
combo_stats.py            descriptive statistics for the combined book
combo_subsets.py          leave-one-out and subset Calmar
combo_window.py           stats restricted to a date window
combo_margin.py           worst simultaneous margin usage
combo_monthly.py          monthly P&L summary
prop_sim_portfolio.py     AquaFunded 2-Step Pro simulator (NY-ORB portfolio)
prop_sim_combo.py         same simulator on the combined portfolio
prop_sim_orb.py           single-pair version
compare.py                NY-ORB vs combined, side by side
improve.py, robustness.py one-factor grid and multi-window robustness
results/                  trades, summaries, reports, Monte Carlo output
```

## Running

```bash
python screen.py                 # family screen, writes results/lab/screen.json
python validate.py               # split-sample and stress, writes results/lab/validation.json
python combo.py                  # build the combined portfolio (core 3 pairs)
python combo.py EURUSD,GBPUSD    # two-pair variant
python prop_sim_combo.py         # combined prop simulation
python compare.py                # NY-ORB vs combined
python multi_pair.py             # rebuild the original NY-ORB portfolio
python prop_sim_portfolio.py     # original portfolio prop simulation
```

Data paths sit at the top of `lab.py`, `backtest.py` and `multi_pair.py` and point at a
local Dukascopy M1 dump (`timestamp,open,high,low,close`, UTC milliseconds). Adjust them
to your own layout before running.

## Caveats

- The two new families were selected from a screen on 2016–2026. The 2011–2015
  out-of-sample run of the full book gives 10,185 trades, +4,671.0R, −53.7R max
  drawdown, t = 15.07 — so selection bias is reduced but not removed.
- `london_orb` supplies 59% of the total R. Without it the book still earns +3,655.6R
  against a −53.1R drawdown.
- AUDJPY stands in for AUDUSD, which was not available locally. It is the weakest leg
  alone but adds +1,937R for +26.7R of portfolio drawdown.
- Phase 2 is modelled from the Phase 1 ending balance; the model page does not state a
  reset. The reset variant is saved separately.
- Trailing drawdown is modelled on intraday equity highs (conservative). The
  closed-balance variant is 1.4–6 points more forgiving.
- Rolling-start historical results are path-specific. Monte Carlo is the planning number.
- Nine concurrent positions at 0.10–0.15% risk each is 0.9–1.35% of open risk. Execution
  failure on one leg is not modelled.
- 2016–2026 is one broad regime. Every year positive is encouraging, not a guarantee.
