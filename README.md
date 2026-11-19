# NY Range Breakout — EURUSD / GBPUSD / AUDJPY

Intraday breakout of the New York opening range, tested on M1 data from 2021-11-05 to
2026-11-03, and simulated against AquaFunded 2-Step Pro evaluation rules.

## Strategy

| Element | Rule |
|---|---|
| Range | high/low of 08:00–08:04 ET (first five 1-minute bars) |
| Entry | first 1m close beyond the range ± 1.0 pip, before 12:00 ET |
| Bias | 15m EMA200, last completed bar (no lookahead); trade only in its direction |
| Stop | opposite side of the range |
| Target | none — no fixed take-profit |
| Exit | 16:00 ET time exit, or stop |
| Cost | round trip: EURUSD 0.8 pip, GBPUSD 1.0, AUDJPY 1.4 |
| Cap | one trade per pair per day, three pairs, max 3 trades/day |

Position size comes from the actual stop distance and the pair's pip value; risk is a fixed
percentage of the current balance.

## Results

Per pair, 5 years, 0.8/1.0/1.4 pip round-trip cost:

| Pair | Trades | Win | Avg R | Total R | PF | Max DD | t |
|---|---|---|---|---|---|---|---|
| EURUSD | 1,217 | 28.3% | +0.503 | +611.9 | 1.68 | −23.5R | 5.11 |
| GBPUSD | 1,230 | 27.5% | +0.511 | +628.1 | 1.59 | −38.9R | 5.18 |
| AUDJPY | 1,215 | 24.0% | +0.174 | +211.1 | 1.22 | −105.5R | 1.95 |
| Portfolio | 3,662 | 26.6% | +0.396 | +1,451.0 | 1.49 | −42.3R | 7.18 |

Daily-R correlation: EURUSD–GBPUSD 0.48, EURUSD–AUDJPY 0.07, GBPUSD–AUDJPY 0.06.
Return per unit of R drawdown: 26.0 / 16.1 / 2.0 / **34.3** for the portfolio.

## Prop evaluation (AquaFunded 2-Step Pro)

Official rules used: Phase 1 10%, Phase 2 5%, daily drawdown 5% of the higher of
balance/equity at 00:00 UTC, max drawdown 10% **trailing** (floor = peak − $500 on a
$5,000 account). See `results/prop/rules_verified.json`.

Monte Carlo, 20,000 runs, day-block resampling:

| Risk/trade | Historical pass | MC pass | Max-DD breach | Median days |
|---|---|---|---|---|
| 0.10% | 100.0% | 98.9% | 1.1% | 182 |
| 0.15% | 93.9% | 91.4% | 8.6% | 118 |
| 0.25% | 77.3% | 68.1% | 31.9% | 64 |
| 0.50% | 37.5% | 32.0% | 68.0% | 21 |
| 1.00% | 10.8% | 11.4% | 88.6% | 5 |

The trailing max drawdown is the only binding rule; the daily limit never triggers.
Recommended: **0.10% per trade**, 0.15% as the aggressive ceiling.

Full report: [`results/multi/REPORT.md`](results/multi/REPORT.md).

## Layout

```
backtest.py               data loader, indicators, EMA20 first-candle baseline
orb.py                    range-breakout engine (bias, stop mode, exit mode, buffer)
multi_pair.py             runs the three pairs, builds the portfolio, saves daily envelopes
prop_sim_portfolio.py     AquaFunded 2-Step Pro simulator, historical + Monte Carlo
prop_sim_orb.py           single-pair version of the simulator
improve.py, robustness.py one-factor grid and multi-window robustness
results/                  trades, summaries, reports, Monte Carlo output
```

## Running

```bash
python multi_pair.py            # rebuild trades and daily envelopes
python prop_sim_portfolio.py    # portfolio evaluation
python prop_sim_portfolio.py days_EURUSD   # single pair
```

Data paths sit at the top of `backtest.py` and `multi_pair.py` and point at a local
Dukascopy M1 dump (`timestamp,open,high,low,close`, UTC milliseconds). Adjust them to your
own layout before running.

## Caveats

- In-sample, five years, one market regime; 2022 trend days carry a large share of the profit.
- AUDJPY stands in for AUDUSD, which was not available locally. It is the weakest leg.
- Phase 2 is modelled from the Phase 1 ending balance; the model page does not state a reset.
- Trailing drawdown is modelled on intraday equity highs. The closed-balance variant is
  saved as `results/multi/prop/monte_carlo_eod_trail.csv` and is 8–20 points more forgiving.
- Bad data ticks are capped at the stop for floating-loss calculations; a live stop can slip.
