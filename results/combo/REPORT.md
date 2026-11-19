# AquaFunded 2-Step Pro — combined 3-strategy portfolio

Three intraday breakout edges on EURUSD, GBPUSD and AUDJPY, run together under one
risk budget, simulated against the AquaFunded **2-Step Pro** rules
(10% / 5% targets, 5% daily, **10% trailing** max drawdown).

The point of the combination is speed: the trailing drawdown is the only binding rule,
so what shortens a challenge is **R of profit per R of drawdown**, not trade count.

| Portfolio | Window | Trades | Total R | Max DD | Return / DD | Median days to pass |
|---|---|---|---|---|---|---|
| NY ORB only (previous report) | 2021-11 → 2026-11 | 3,662 | +1,451.0 | −42.3R | 34.3 | 182 @ 0.10% |
| **Combined, same window** | 2021-11 → 2026-11 | 10,094 | **+4,263.2** | **−44.5R** | **95.8** | **68 @ 0.10%** |
| Combined, full test | 2016-01 → 2026-11 | 21,925 | +8,895.1 | −76.1R | 116.8 | — |

In the same five years the combined portfolio earns **2.9x the R for 1.05x the drawdown**.
That is the whole result: the pass rate stays the same or improves and the challenge
finishes roughly three times sooner.

## 1. The three families

All three keep the original design rules: entry on a 1-minute close, stop from the
structure (never a fixed take-profit), flat at 16:00 ET, per-pair round-trip cost.

| Family | Entry | Stop | Bias | Trades | Avg R | Total R | Max DD | Calmar | t | Positive years |
|---|---|---|---|---|---|---|---|---|---|---|
| `ny_orb` | 08:00 ET 5-bar range breakout ±1.0 pip, before 12:00 ET | opposite side of range | 15m EMA200 | 7,959 | +0.335 | +2,665.4 | −52.9R | 50.4 | 9.28 | 11/11 |
| `london_orb` | 03:00 ET 5-bar range breakout ±1.0 pip, before 12:00 ET | opposite side of range | 15m EMA200 | 8,225 | +0.637 | +5,239.5 | −52.9R | 99.1 | 16.83 | 11/11 |
| `prev_level` | previous ET-day high/low breakout during London, ±1.0 pip | opposite side of prior day's range | 15m EMA200 | 5,741 | +0.172 | +990.3 | −8.9R | 110.9 | 19.51 | 11/11 |

`london_orb` is the workhorse (+5,239R). `prev_level` is the ballast: only +990R but a
−8.9R drawdown. `ny_orb` is the original strategy, unchanged.

Per pair and strategy:

| Family | Pair | Trades | Total R | Max DD | t |
|---|---|---|---|---|---|
| ny_orb | EURUSD | 2,651 | +1,091.6 | −36.5R | 6.42 |
| ny_orb | GBPUSD | 2,678 | +1,225.4 | −38.9R | 7.19 |
| ny_orb | AUDJPY | 2,630 | +348.4 | −105.5R | 2.23 |
| london_orb | EURUSD | 2,747 | +1,728.8 | −25.3R | 9.88 |
| london_orb | GBPUSD | 2,752 | +2,116.9 | −30.1R | 11.04 |
| london_orb | AUDJPY | 2,726 | +1,393.8 | −38.9R | 8.13 |
| prev_level | EURUSD | 1,978 | +376.8 | −7.2R | 11.81 |
| prev_level | GBPUSD | 2,010 | +419.3 | −8.2R | 12.58 |
| prev_level | AUDJPY | 1,753 | +194.2 | −4.3R | 9.27 |

## 2. Why the combination helps

Daily-R correlation between families:

| | ny_orb | london_orb | prev_level |
|---|---|---|---|
| ny_orb | — | 0.176 | 0.252 |
| london_orb | | — | 0.444 |

Pair correlation: EURUSD–GBPUSD 0.329, EURUSD–AUDJPY 0.074, GBPUSD–AUDJPY 0.073.

The two London-session families share the session (0.44) but trade different levels.
`ny_orb` is nearly independent of both (0.18 / 0.25). Pooling them adds R roughly
linearly and drawdown much less than linearly:

| Subset | Trades | Total R | Max DD | Return / DD |
|---|---|---|---|---|
| london_orb | 8,225 | +5,239.5 | −50.3R | 104.2 |
| ny_orb | 7,959 | +2,665.4 | −50.6R | 52.7 |
| prev_level | 5,741 | +990.3 | −8.0R | 123.0 |
| london_orb + ny_orb | 16,184 | +7,904.9 | −74.0R | 106.9 |
| london_orb + prev_level | 13,966 | +6,229.8 | −55.0R | 113.3 |
| ny_orb + prev_level | 13,700 | +3,655.6 | −53.1R | 68.8 |
| **all three** | **21,925** | **+8,895.1** | **−76.1R** | **116.8** |

## 3. Portfolio behaviour, 2016-01-04 → 2026-11-03

- 2,816 trading days, 21,925 trades, **7.79 trades/day**, max 9 (3 strategies x 3 pairs).
- Daily R: mean **+3.159R**, sd 10.404R, worst day **−9.95R**, best +94.57R.
- Positive days 52.5%. Max concurrent positions 9. Worst simultaneous floating loss **−5.04R**.
- Longest losing streak: **27 trades / 14 days**.
- Max drawdown on daily closes: **−76.1R**. Calmar (total R / max DD R): **116.8**.
- t-statistic 20.81.

Yearly:

| Year | Trades | Total R | Avg R | Max DD (R) |
|---|---|---|---|---|
| 2016 | 2,027 | +728.7 | +0.360 | −37.8 |
| 2017 | 1,990 | +648.1 | +0.326 | −39.5 |
| 2018 | 2,051 | +799.7 | +0.390 | −44.1 |
| 2019 | 1,975 | +979.2 | +0.496 | −30.5 |
| 2020 | 2,059 | +776.0 | +0.377 | −68.2 |
| 2021 | 2,045 | +820.3 | +0.401 | −27.1 |
| 2022 | 2,032 | +994.8 | +0.490 | −25.5 |
| 2023 | 2,059 | +860.4 | +0.418 | −36.9 |
| 2024 | 2,013 | +761.9 | +0.379 | −44.5 |
| 2025 | 2,009 | +840.9 | +0.419 | −37.9 |
| 2026* | 1,665 | +685.1 | +0.411 | −36.9 |

*through 2026-11-03. Every year positive, 648–995R. No year carries the result.

### Out-of-sample check, 2011–2015

The family selection used 2016–2026 only. Running the same three families on the
earlier period, which was never used for selection:

| Period | Trades | Total R | Avg R | Max DD | Calmar | t |
|---|---|---|---|---|---|---|
| 2011–2015 (out of sample) | 10,185 | +4,671.0 | +0.459 | −53.7R | 86.9 | 15.07 |
| 2016–2026 (selection) | 21,925 | +8,895.1 | +0.406 | −76.1R | 116.8 | 20.81 |

Every family is positive in the earlier period too (`london_orb` +0.711, `ny_orb`
+0.402, `prev_level` +0.179 average R). The full 2011–2026 run is 32,110 trades,
+13,566.2R, −76.1R max drawdown, t = 25.69. The edge is not a 2016–2026 artifact.

Monthly P&L at 0.15% risk (static $7.50/R, not compounding): **131 months, 123 positive
(93.9%)**, total +$66,714, mean +$509, best +$1,318, worst −$264.

## 4. Prop results — AquaFunded 2-Step Pro

Rules: Phase 1 +10%, Phase 2 +5% (from the Phase 1 closing balance), daily drawdown 5%
of the higher of balance/equity at 00:00 UTC, max drawdown **10% trailing** with the
floor fixed at peak − $500 on a $5,000 account. Floating P&L counts. No time limit.

Historical — a challenge started on every trading day (2,816 starts):

| Risk/trade | Resolved | Passed | Failed | Pass (resolved) | P1 | P2 | Avg days | Median days | P90 days | Max daily DD | Max total DD |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.050% | 2,709 | 2,709 | 0 | **100.0%** | 100% | 100% | 135 | 132 | 193 | $15 | $243 |
| 0.075% | 2,719 | 2,719 | 0 | **100.0%** | 100% | 100% | 92 | 87 | 142 | $22 | $363 |
| **0.100%** | 2,741 | 2,741 | 0 | **100.0%** | 100% | 100% | 72 | **68** | 117 | $29 | $486 |
| **0.125%** | 2,748 | 2,701 | 47 | **98.3%** | 99.3% | 99.0% | 59 | **55** | 98 | $36 | $522 |
| **0.150%** | 2,754 | 2,655 | 99 | **96.4%** | 97.9% | 98.5% | 50 | **46** | 85 | $44 | $530 |
| 0.200% | 2,772 | 2,404 | 368 | 86.7% | 93.4% | 92.9% | 35 | 32 | 57 | $57 | $556 |
| **0.250%** | 2,803 | 2,004 | 799 | **71.5%** | 84.0% | 85.1% | 25 | 23 | 41 | $73 | $670 |
| **0.500%** | 2,815 | 700 | 2,115 | **24.9%** | 49.5% | 50.2% | 8 | 7 | 14 | $148 | $1,288 |

Every failure is a trailing max-DD breach. **The daily limit never binds** — the worst
day at 0.50% risk is $148 against a $250 limit, because the worst simultaneous floating
loss across all nine positions is only −5.04R.

"Max total DD" is the worst single excursion across all starts, including intraday
overshoot past the floor on the failing paths, so it can exceed $500.

Monte Carlo — 20,000 runs, whole trading days resampled (intraday correlation and the
1–9 trades/day structure preserved):

| Risk | Pass both | Daily breach | Max-DD breach | DD p50 | DD p95 | DD p99 | Worst DD | Median trading days |
|---|---|---|---|---|---|---|---|---|
| 0.050% | **100.0%** | 0.0% | 0.0% | 2.4% | 3.9% | 4.9% | 7.8% | 94 |
| 0.075% | **100.0%** | 0.0% | 0.03% | 3.3% | 5.5% | 6.9% | 10.3% | 64 |
| **0.100%** | **99.6%** | 0.0% | 0.39% | 4.1% | 7.1% | 8.9% | 10.6% | **49** |
| **0.125%** | **98.1%** | 0.0% | 1.87% | 4.9% | 8.5% | 10.1% | 10.7% | **40** |
| **0.150%** | **95.1%** | 0.0% | 4.94% | 5.5% | 10.0% | 10.3% | 11.2% | **33** |
| 0.200% | 84.3% | 0.0% | 15.7% | 6.8% | 10.4% | 10.9% | 12.3% | 24 |
| 0.250% | 70.7% | 0.0% | 29.3% | 8.1% | 10.7% | 11.4% | 15.6% | 18 |
| 0.500% | 24.3% | 0.0% | 75.7% | 10.4% | 12.9% | 16.8% | 33.1% | 6 |

Sensitivity — if the firm trails the floor on **closed balance only**:

| Risk | MC pass (intraday trail) | MC pass (EOD trail) |
|---|---|---|
| 0.125% | 98.1% | 99.5% |
| 0.150% | 95.1% | 98.6% |
| 0.200% | 84.3% | 95.3% |
| 0.250% | 70.7% | 90.4% |
| 0.500% | 24.3% | 65.4% |

Phase 2 restarting at $5,000 instead of carrying Phase 1 profit:

| Risk | Pass (resolved) | Median days |
|---|---|---|
| 0.050% | 100.0% | 132 |
| 0.100% | 100.0% | 68 |
| 0.150% | 97.1% | 46 |
| 0.250% | 77.5% | 24 |

Worst simultaneous margin usage: 24.7% of the account at 0.125% risk, 29.7% at 0.15%
(limit is 80%). Margin never binds.

## 5. Speed against the NY-ORB-only portfolio

| Portfolio | Risk | MC pass | Median calendar days | Median trading days (MC) |
|---|---|---|---|---|
| NY ORB only | 0.10% | 98.9% | 182 | 132 |
| NY ORB only | 0.15% | 91.4% | 118 | 85 |
| NY ORB only | 0.25% | 68.1% | 64 | 43 |
| **Combined** | **0.10%** | **99.6%** | **68** | **49** |
| **Combined** | **0.125%** | **98.1%** | **55** | **40** |
| **Combined** | **0.15%** | **95.1%** | **46** | **33** |
| Combined | 0.25% | 70.7% | 23 | 18 |

At the *same* risk of 0.10% the combined portfolio passes in 68 days instead of 182
(2.7x faster) and with a higher Monte Carlo pass probability (99.6% vs 98.9%).
At 0.125% it passes in 55 days with 98.1% — a higher pass probability than the old
portfolio had at 0.10%, at less than a third of the time.
Measured at the same **95% Monte Carlo pass probability**, the old portfolio needs 132
trading days and the combined one needs 33 — **4.0x faster**.

Lower-volatility alternative — the same three families on **EURUSD + GBPUSD only**
(6,958.8R, −49.4R DD, calmar 140.8, 5.27 trades/day):

| Risk | Historical pass | MC pass | Median days |
|---|---|---|---|
| 0.125% | 99.7% | 99.4% | 69 |
| 0.150% | 99.2% | 98.0% | 56 |
| 0.250% | 79.2% | 80.4% | 32 |

It sits on the same speed/reliability frontier as the 3-pair version. Use it if you
prefer six positions a day instead of nine; use the 3-pair version for more absolute R.

## 6. Recommendation

**Use 0.10% per trade ($5 on $5,000).** 100% historical, **99.6% Monte Carlo**, 0.39%
max-DD breach probability, median **68 calendar days**, and a 99th-percentile drawdown
of 8.9% that still leaves a point of buffer under the 10% limit. That is 2.7x faster
than the NY-only portfolio at the same risk, with a better pass probability.

**0.125% ($6.25) is the speed option, and it is the mathematical ceiling.** The
portfolio's worst historical drawdown is 76.1R; 76.1 x 0.125% = 9.5% of the account,
just inside the 10% limit. Any higher and the historical path itself breaches. At
0.125%: 98.1% Monte Carlo, median 55 days, 1.9% breach probability. Take it if two
weeks matter more than 1.5 points of failure risk.

**0.15% ($7.50) is the hard ceiling:** 95.1% Monte Carlo, median 46 days. Above it the
trailing $500 offset starts to sit inside the normal drawdown of the book (MC breach
29% at 0.25%, 76% at 0.50%).

Do not run 0.25% or 0.50% on a single attempt. They are only useful if the plan is
"many cheap attempts", and even then 0.10% has a better expected outcome.

## 7. Caveats

- The three families were **selected from a screen of 8 families x 5 pairs** on
  2016–2026. That is a selection bias. `validate.py` re-ran the two new families on
  2011–2015, a period never used for selection, and both held on all five pairs
  (London ORB avg R +0.50 to +0.88, prev-day level +0.10 to +0.23, every pair positive).
  They also survive 2x costs and an 18-point parameter grid with no cliff.
- `london_orb` supplies 59% of the total R. If it degrades, the book still has
  ny_orb + prev_level = +3,655.6R / −53.1R DD (calmar 68.8).
- AUDJPY is a substitute for AUDUSD, which is not in the local dataset. It is the
  weakest leg on its own but adds +1,937R for +26.7R of portfolio drawdown.
- Costs: EURUSD 0.8 pip, GBPUSD 1.0, AUDJPY 1.4 round trip. The London open (03:00 ET)
  is a liquid session, but live spreads there are wider than the assumption.
- Phase 2 is modelled from the Phase 1 ending balance; the reset variant is saved.
- Trailing drawdown is modelled on intraday equity highs (conservative). The
  closed-balance variant raises pass rates by 1.4–6 points.
- Rolling-start historical results are path-specific. Monte Carlo is the planning number.
- Nine concurrent positions at 0.10–0.15% risk each is 0.9–1.35% of open risk. That is
  within the rules but it is a real operational load; an execution failure on one leg
  is not modelled.
- 2016–2026 is still one broad regime. Every year is positive, which is encouraging,
  but it is not a guarantee.

## 8. Files

`results/combo/`
- `summary.json` — portfolio, per-strategy, per-pair, correlations, yearly
- `trades_combo.csv` — 21,925 trades
- `days.csv` — daily equity envelope in R (minute-level across all open positions)
- `daily_R.csv` — daily R and trade count
- `prop/historical.csv`, `prop/monte_carlo.csv`
- `prop/historical_eod_trail.csv`, `prop/monte_carlo_eod_trail.csv`
- `prop/historical_phase2_reset.csv`
- `prop/monthly_*.csv`

`results/combo/eurusd_gbpusd/` — the 2-pair variant, same layout.
`results/lab/screen.json`, `results/lab/validation.json` — family screen and validation.

Scripts: `lab.py` (engines), `screen.py`, `validate.py`, `combo.py`,
`prop_sim_combo.py`, `combo_stats.py`, `combo_subsets.py`, `combo_window.py`,
`combo_margin.py`, `combo_monthly.py`, `compare.py`.
