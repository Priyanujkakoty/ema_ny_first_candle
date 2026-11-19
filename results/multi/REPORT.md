# AquaFunded 2-Step Pro — 3-pair portfolio simulation

Strategy: NY range breakout, buffer 1.0 pip, 15m EMA200 bias, range stop, 16:00 ET exit.
Pairs: EURUSD + GBPUSD + AUDJPY, max 3 trades/day (one per pair).
Data: M1, 2021-11-05 → 2026-11-03. 3,662 trades, 1,293 trading days.

## 0. Correction to the earlier EURUSD report

The first report used **8% / 4% / 8% static** rules. Those are the **2-Step Standard**
numbers. The official **2-Step Pro** page (help.aquafunded.com/en/articles/15281229-2-step-pro,
read 2026-11-20) states:

| Rule | Earlier report (wrong) | 2-Step Pro (used now) |
|---|---|---|
| Phase 1 target | 8% | **10%** |
| Phase 2 target | 5% | 5% |
| Daily drawdown | 4% | **5%**, of the higher of balance/equity at 00:00 UTC |
| Max drawdown | 8% static | **10% trailing** |
| Trailing | none | **yes** — floor = highest balance/equity − 10% of initial ($500) |
| Consistency | none | none in evaluation; 50% on funded payouts |

The trailing rule is much stricter than a static floor and it is the only rule that binds.
All numbers below use the Pro rules. `results/prop/rules_verified.json` is updated.

**AUDUSD M1 is not in the local dataset.** Per instruction, no download: AUDJPY is used
instead (same base currency, keeps the AUD leg). It is the weak leg — see §2.

## 1. Strategy per pair (unchanged logic, per-pair costs)

| Pair | Trades | Win | Avg R | Total R | PF | Max DD | Loss streak | t | Pips | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| EURUSD | 1,217 | 28.3% | +0.503 | +611.9 | 1.68 | −23.5R | 13 | 5.11 | +5,075 | 0.8 |
| GBPUSD | 1,230 | 27.5% | +0.511 | +628.1 | 1.59 | −38.9R | 14 | 5.18 | +5,617 | 1.0 |
| AUDJPY | 1,215 | 24.0% | +0.174 | +211.1 | 1.22 | −105.5R | 20 | 1.95 | +1,925 | 1.4 |
| **Portfolio** | **3,662** | **26.6%** | **+0.396** | **+1,451.0** | **1.49** | **−42.3R** | **24** | **7.18** | — | — |

AUDJPY is marginal on its own (t = 1.95, return/DD = 2.0 vs 26.0 for EURUSD) but it is
almost uncorrelated with the other two, so it still helps the portfolio.

Yearly R:

| Pair | 2021* | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| EURUSD | +11.6 | +139.3 | +227.2 | +100.4 | +73.4 | +60.0 |
| GBPUSD | −7.3 | +152.6 | +143.4 | +94.4 | +150.0 | +95.0 |
| AUDJPY | +42.4 | +88.4 | −37.3 | +28.3 | +41.8 | +47.4 |

*2021 is Nov–Dec only.

## 2. Portfolio behaviour

- 2.83 trades/day (3 trades on 1,110 of 1,293 days, 2 on 149, 1 on 34). Cap never hit.
- Daily R: mean **+1.122R**, sd **6.70R**, worst day **−4.00R**, best **+68.0R** (2022-11-10 CPI).
- Positive days: 41%. The edge is a few large trend days, not a high hit rate.
- Max concurrent positions: 3. Worst simultaneous floating loss: **−3.00R**.
- Daily-R correlation: EURUSD–GBPUSD **0.483**, EURUSD–AUDJPY **0.068**, GBPUSD–AUDJPY **0.056**.
- Longest losing streak: **24 trades** (15 losing days).

Return per unit of R drawdown: EURUSD 26.0, GBPUSD 16.1, AUDJPY 2.0, **portfolio 34.3**.
Diversification works: the portfolio earns 2.4x EURUSD's R with only 1.8x its drawdown.

## 3. Historical prop results (rolling start on every trading day)

| Risk/trade | Starts | Resolved | Passed | Failed | Pass (resolved) | P1 | P2 | Median days | Max daily DD | Max total DD |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.10% | 1293 | 1157 | 1157 | 0 | **100.0%** | 100% | 100% | 182 | $17 | $346 |
| 0.15% | 1293 | 1187 | 1114 | 73 | 93.9% | 100% | 93.9% | 118 | $26 | $517 |
| 0.20% | 1293 | 1207 | 1066 | 141 | 88.3% | 97.9% | 90.2% | 86 | $35 | $524 |
| **0.25%** | 1293 | 1246 | 963 | 283 | **77.3%** | 88.7% | 87.1% | 64 | $44 | $531 |
| **0.50%** | 1293 | 1284 | 482 | 802 | **37.5%** | 57.2% | 65.6% | 21 | $88 | $675 |
| **0.75%** | 1293 | 1290 | 217 | 1073 | **16.8%** | 40.8% | 41.3% | 8 | $135 | $896 |
| **1.00%** | 1293 | 1293 | 139 | 1154 | **10.8%** | 32.9% | 32.7% | 5 | $180 | $1,171 |

**Every failure is a trailing max-DD breach. Daily drawdown never binds** — the worst day
at 1.00% risk is $180 (3.6% of a $5,000 start) against a $250 limit. Three concurrent
trades rarely all sit at their stop in the same minute (worst simultaneous floating −3.0R).

Pass rate falls fast with risk because the trailing floor moves up with every equity high.
The strategy's own max drawdown is −42.3R, so any risk above ~0.20% puts the 10% offset
inside the normal drawdown of the system.

Phase 2 starting fresh at $5,000 instead of carrying Phase 1 profit (variant):

| Risk | Pass (resolved) | Median days |
|---|---|---|
| 0.25% | 84.2% | 66 |
| 0.50% | 40.7% | 21 |
| 0.75% | 22.3% | 9 |
| 1.00% | 13.2% | 5 |

## 4. Monte Carlo (20,000 runs, day-block resampling)

Day blocks are resampled, not single trades, so intraday correlation and the 1–3 trades/day
structure are preserved.

| Risk | Pass both | Daily breach | Max-DD breach | DD p95 | DD p99 | Worst DD | Median trading days |
|---|---|---|---|---|---|---|---|
| 0.10% | **98.9%** | 0.0% | 1.1% | 8.0% | 10.0% | 10.3% | 132 |
| 0.15% | 91.4% | 0.0% | 8.6% | 10.1% | 10.2% | 10.5% | 85 |
| 0.20% | 80.1% | 0.0% | 19.9% | 10.2% | 10.4% | 10.6% | 59 |
| 0.25% | 68.1% | 0.0% | 31.9% | 10.3% | 10.5% | 10.8% | 43 |
| 0.50% | 32.0% | 0.0% | 68.0% | 10.9% | 11.6% | 14.2% | 14 |
| 0.75% | 18.5% | 0.0% | 81.5% | 11.8% | 15.8% | 21.9% | 7 |
| 1.00% | 11.4% | 0.0% | 88.6% | 13.6% | 19.6% | 31.7% | 4 |

Sensitivity — if the firm trails the floor on **closed balance only** instead of intraday
equity highs, pass rates improve but the ranking does not change:

| Risk | MC pass (intraday trail) | MC pass (EOD trail) |
|---|---|---|
| 0.25% | 68.1% | 79.2% |
| 0.50% | 32.0% | 52.4% |
| 0.75% | 18.5% | 40.1% |
| 1.00% | 11.4% | 32.9% |

Per-pair comparison at 0.25% / 0.50% (MC pass): EURUSD 93.4% / 61.9%, GBPUSD 92.6% / 61.0%,
AUDJPY 48.6% / 27.9%, portfolio 68.1% / 32.0%. The portfolio needs **less** risk per trade
than a single pair to reach the same pass probability, because its R drawdown is spread over
2.4x the R of profit.

## 5. Monthly P&L at 0.15% risk (static $7.50/R, not compounding)

61 months, 46 positive (75%), total **+$10,883**, best +$757, worst −$221.

| Month | P&L | Month | P&L |
|---|---|---|---|
| 2025-12 | −$221 | 2026-06 | +$575 |
| 2026-01 | +$384 | 2026-07 | +$267 |
| 2026-02 | +$64 | 2026-08 | +$132 |
| 2026-03 | +$180 | 2026-09 | −$185 |
| 2026-04 | +$146 | 2026-10 | −$2 |
| 2026-05 | +$9 | 2026-11 | −$52 (partial) |

Full series: `prop/monthly_015pct.csv` (also 010, 025, 050).

## 6. Recommendation

**None of the four requested levels is sustainable on 2-Step Pro.** 0.25% has a 32% Monte
Carlo chance of a trailing-DD breach; 0.50% has 68%; 0.75% and 1.00% are coin flips to lose.

**Use 0.10% per trade ($5 on $5,000).** 100% historical, 98.9% Monte Carlo, 1.1% max-DD
breach, median ~182 calendar days to pass both phases. There is no time limit, so the slow
pace costs nothing.

**0.15% ($7.50) is the aggressive ceiling:** 93.9% historical, 91.4% Monte Carlo, median
~118 days. Accept it only if an ~9% chance of failure is acceptable.

**0.25% ($12.50) is the hard ceiling** for a single attempt: 77.3% historical, 68.1% MC.
Above 0.25% the trailing 10% offset sits inside the strategy's normal −42R drawdown.

The binding constraint is the trailing max drawdown, not the daily limit. Daily drawdown
never triggers at any tested risk level.

## 7. Caveats

- AUDJPY substitutes for AUDUSD; its standalone edge is weak (t = 1.95) and 2023 was negative.
- Costs: EURUSD 0.8 pip, GBPUSD 1.0, AUDJPY 1.4 round trip. Wider NY-open spreads reduce EV.
- Phase 2 is modelled from the Phase 1 ending balance. The model page does not state a reset;
  the reset variant is saved separately.
- Trailing floor is modelled on intraday equity highs (conservative). The closed-balance
  variant is also saved; it raises pass rates by ~8–20 points at 0.25–1.00%.
- Rolling-start historical results are path-specific. Monte Carlo is the planning number.
- Bad data ticks are capped at the stop for floating loss; a live stop can slip.
- In-sample, 5 years, one regime. The 2022 trend year carries a large share of the profit.

## 8. Files

`results/multi/`
- `summary.json` — per-pair and portfolio stats, correlations, yearly
- `trades_portfolio.csv` — 3,662 trades with MFE/MAE
- `days.csv`, `days_<PAIR>.csv` — daily equity envelopes in R
- `prop/historical.csv`, `prop/monte_carlo.csv` — portfolio, intraday trailing
- `prop/historical_eod_trail.csv`, `prop/monte_carlo_eod_trail.csv` — closed-balance trailing
- `prop/historical_phase2_reset.csv` — Phase 2 restart variant
- `prop/monthly_*.csv` — monthly P&L

Scripts: `multi_pair.py`, `prop_sim_portfolio.py`.
