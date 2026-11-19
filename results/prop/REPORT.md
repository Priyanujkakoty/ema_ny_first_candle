# AquaFunded 2-Step Pro — simulation report

> **Superseded.** This report used 8% / 4% / 8% static rules, which belong to the
> **2-Step Standard** model. The official **2-Step Pro** page specifies 10% / 5% targets,
> 5% daily drawdown and a **10% trailing** max drawdown. See
> `../multi/REPORT.md` for the corrected simulation (3-pair portfolio, same rules) and
> `rules_verified.json` for the corrected rule set. The numbers below are kept for history
> only; they overstate the pass rate.

Strategy: NY range breakout, buffer 1.0 pip, 15m EMA200 bias, range stop, 16:00 ET exit.
Account: $5,000. Data: EURUSD M1, 2021-11-05 → 2026-11-03, 1217 trades, 0.8 pip round-trip cost embedded.

## 1. Rules — verified vs assumed

Verified 2026-11-20 from https://www.aquafunded.com/forex-rules and
https://help.aquafunded.com/en/ (Trading Rules collection).

| Rule | Your assumption | Official (used) |
|---|---|---|
| Phase 1 target | 10% ($500) | **8% ($400)** |
| Phase 2 target | 5% ($250) | 5% ($250), fresh start |
| Daily drawdown | 5% ($250) | **4%** of previous day's highest balance/equity |
| Max drawdown | 10% ($500) | **8% ($400)** of initial balance, fixed |
| Trailing drawdown | possibly | **none** — max DD floor is fixed at $4,600 |
| Daily reset | unknown | **00:00 UTC** |
| Floating P&L in limits | — | included in both daily and max DD |
| Consistency rule | — | **not applied to 2-Step evaluation** (instant models only: 15%/20%) |
| Minimum trading days | — | none in 2-Step Pro evaluation (3 days at funded stage) |
| Max lot size | — | **no limit** |
| Margin / exposure | — | max 80% of available margin per position |
| Leverage | — | 1:100 evaluation |

Not simulated: challenge fee, funded-stage rules (1:50 leverage, 3 minimum trading days,
payout consistency), swap (no overnight positions), news filter.

## 2. Simulation assumptions

- One trade per day maximum, as produced by the strategy; no re-entry.
- Risk per trade = risk% × current closed balance. Position size = risk$ ÷ (stop pips × $10/lot).
- Phase 2 starts fresh at $5,000 (rule text: "performance begins fresh in that phase").
- Daily floor = day-start balance − 4% × previous day's highest equity.
- Max DD floor = $4,600 for both phases (fixed to initial balance).
- Intraday low uses each trade's maximum adverse excursion, capped at the stop; gap fills kept.
- Profit target counts closed profit only, checked at each 16:00 ET close.
- Challenge fails immediately on any breach.
- Historical pass rates use a rolling start at every trade (1217 starts); late starts that run
  out of data are censored, not failed.

## 3. Historical results (5 years, rolling starts)

| Risk/trade | Starts | Resolved | Censored | Passed | Failed | Pass (resolved) | Pass (all starts) | P1 rate | P2 rate | Avg days | Median days | Max daily DD | Max peak-trough DD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.25% | 1217 | 1003 | 214 | 1003 | 0 | 100.0% | 82.4% | 100.0% | 100.0% | 160 | 148 | $17 | $308 |
| 0.50% | 1217 | 1121 | 96 | 1059 | 62 | 94.5% | 87.0% | 97.9% | 96.4% | 84 | 72 | $35 | $612 |
| 0.75% | 1217 | 1173 | 44 | 753 | 420 | 64.2% | 61.9% | 85.3% | 75.3% | 45 | 39 | $52 | $784 |
| 1.00% | 1217 | 1190 | 27 | 652 | 538 | 54.8% | 53.6% | 73.4% | 74.6% | 29 | 24 | $68 | $823 |

All failures were max-drawdown breaches. **Daily drawdown never bound**: worst single day was
$68 at 1% risk (1.36% of balance) versus a 4% limit, because the strategy holds one trade per day
and a stop-out is ~1.1R.

Max peak-to-trough DD exceeds $400 because the rule is a fixed $4,600 floor, not a trailing peak.
A challenge can rise to $5,300 and fall back to $4,600 without breaching.

Longest losing streak in the 5-year sequence: **13 trades** (≈14.3R). At 0.5% risk that is 7.2%
of the account — just inside the 8% limit. At 0.75% it is 10.7% — a breach.

## 4. Monte Carlo (20,000 runs per risk, i.i.d. resampling of trade outcomes)

| Risk | Pass both | Daily breach | Max DD breach | Censored | Median trades to pass | DD p50 | DD p95 | DD p99 | Worst DD |
|---|---|---|---|---|---|---|---|---|---|
| 0.25% | **96.5%** | 0.0% | 3.2% | 0.4% | 100 | 4.1% | 8.7% | 10.8% | 16.0% |
| 0.50% | 79.3% | 0.0% | 20.7% | 0.0% | 44 | 6.1% | 11.6% | 14.0% | 16.2% |
| 0.75% | 63.0% | 0.0% | 37.0% | 0.0% | 25 | 7.9% | 12.6% | 14.9% | 16.8% |
| 1.00% | 52.2% | 0.0% | 47.8% | 0.0% | 17 | 8.3% | 13.1% | 15.5% | 17.0% |

Monte Carlo is more conservative than the historical pass rate at 0.5% (79% vs 94%). The actual
5-year path contained one deep drawdown episode (2024) rather than many, so rolling starts mostly
avoided it. Random reordering produces more frequent 16R drawdowns. Treat MC as the planning number.

## 5. Monthly P&L at 0.5% risk (static $25/R, not compounding)

61 months, 45 positive, total +$15,296. Last 12 months:

| Month | P&L |
|---|---|
| 2025-12 | −$273 |
| 2026-01 | +$247 |
| 2026-02 | +$149 |
| 2026-03 | +$407 |
| 2026-04 | −$107 |
| 2026-05 | −$62 |
| 2026-06 | +$578 |
| 2026-07 | +$245 |
| 2026-08 | +$265 |
| 2026-09 | −$251 |
| 2026-10 | +$85 |
| 2026-11 | −$55 (partial) |

Full series: `monthly_05pct.csv`. This is strategy P&L, not challenge outcome — targets and
drawdown limits truncate it.

## 6. Recommendation

**Use 0.25% per trade for the evaluation.** It is the only level with zero historical failures
and a 96.5% Monte Carlo pass rate. Median time to pass both phases is ~148 calendar days, which is
acceptable because AquaFunded has no time limit.

**0.50% is the aggressive alternative:** 94.5% historical, 79.3% Monte Carlo, median ~72 days.
Choose it only if a ~20% chance of a max-DD failure is acceptable.

**Reject 0.75% and 1.00%:** 37–48% Monte Carlo breach probability. They pass faster but the 8%
max drawdown is smaller than the strategy's observed 23.5R drawdown at those risk levels.

Daily drawdown is irrelevant for this strategy at any tested risk level. Max drawdown is the only
binding rule.

## 7. Caveats

- Results are in-sample, one pair, five years, with strong EURUSD trend years included.
- Entry/exit logic was not optimized further for this test; the only change from the validated
  config is the 1.0 pip breakout buffer.
- 0.8 pip cost may be optimistic at the NY open; at 1.6 pip cost EV falls from +4.17 to +2.51 pips.
- Bad data ticks were capped at the stop for floating-loss calculations; a live stop can slip.
- Phase 2 reset and per-phase DD reset are documented assumptions, not quoted rules.
- Monte Carlo assumes independent trades; actual trade outcomes have near-zero autocorrelation
  (lag-1 −0.017), so the assumption is reasonable.
