# First prospective PlayNow paper position — October 16, 2026

The user authorized one existing guarded three-credit NHL refresh to collect
real prices for the forward paper run. This was performed through the
authenticated production dashboard, without changing runtime code, model
weights, verification gates, budgets or automatic-refresh settings.

## Provider receipt

- Request: `a9895de1-a1c6-4378-897e-f31fe109ca6e`.
- Admitted: 14:58:20 Pacific; fully saved: 14:58:47 Pacific.
- Final durable state: `SUCCEEDED`, `odds_sync_status: complete`.
- Received and matched 16 events; no unmatched events.
- Saved 114 quotes, including 30 PlayNow quotes across markets.
- Provider-reported charge: 3 credits. October usage: 12 of 500; 488 remain.
- Rolling manual allowance after this request: 4 of 5 attempts remain.
- No second odds request or OpenRouter generation was sent.

The provider's successful HTTP response was recorded before quote ingestion
finished. Verification waited for the separate ingestion-complete marker and
the saved quotes; it did not equate the early provider receipt with completion.

## Actual forecast / price pairs

Both forecasts had already frozen at approximately 03:00 Pacific that morning,
before this refresh. Their probabilities were not fitted to these new prices.
The paired PlayNow moneylines carried the same source timestamp, 14:58:16
Pacific. The collector recorded both as `VALID` at 14:59:23 Pacific, within the
five-minute freshness window and before the games' scheduled starts.

| October 16 matchup | Home / away probability | Home / away decimal odds | Home / away signed edge | Paper decision |
| --- | --- | --- | --- | --- |
| Pittsburgh at Colorado, 18:00 PT | 58.1184172% / 41.8815828% | 1.47 / 2.75 | -9.90879368 pp / +5.51794644 pp | Pittsburgh, one simulated unit at 2.75 |
| Boston at Anaheim, 19:00 PT | 49.5723313% / 50.4276687% | 1.90 / 1.90 | -3.05924765 pp / -2.20391025 pp | No qualifying paper position |

The calculation is `forecast_probability - 1 / decimal_odds`. Pittsburgh's
41.8815828% forecast exceeds the quoted 36.36363636% break-even probability by
5.51794644 percentage points. This passes the frozen paper selection threshold
of +3 percentage points; neither Boston nor Anaheim passes it. All markets
here refer to final winner including overtime/shootout.

The active candidate remains `nhl-team-paper-v2-617e76ac7eda`. Its first paper
position references price observation `1583`, recorded at
`2026-10-16T14:59:23.063273-07:00`. Expected/unknown starters remain explicitly
permitted for this team-only research model; no goalie adjustment or starter
confirmation was invented.

## Production and spending verification

The authenticated Model Performance page displayed four saved forecasts, two
matched PlayNow pairs, and one simulated position. The first two prior-day
forecasts had already settled against official results. Tonight's two games
were still awaiting results; paper ROI and paired Brier scoring were therefore
not yet available. Two resolved forecasts do not establish model quality.

Read-only database verification found exactly one metered provider call today,
using three odds credits, no AI generation, CAD 1,100 initial bankroll and zero
actual wager tickets. Bankroll records were not altered. Automatic odds
refreshes remain off and the existing US$3 monthly AI ceiling remains intact.

After the next normal collection cycle completed at 15:00:31 Pacific, the
database still held exactly two valid paired-price observations, one paper
position and one odds call today. No duplicate position or price observation
was created. There were still zero approved production models.

Actual production screenshots are saved locally under
`artifacts/nhl-paper-prices-2026-10-16/`: `refresh-complete.jpg`,
`paper-position-live.jpg`, and `paper-prices-live.jpg`. These files are ignored
by Git. No synthetic fixtures, probabilities, prices, results, real wagers or
model approval were inserted to demonstrate the workflow.

The recorded entry prices and edges are historical evidence. After five
minutes the prices expire for a new selection; retaining the paper observation
does not make the offer current. Tomorrow's fixtures still require their own
match-day forecasts and fresh prices.

## Remaining work

The normal collector can settle the simulated position once the official final
result becomes available. Continue prospective collection under the frozen
protocol; its first workflow review requires at least 14 days and 100 resolved
forecast/price pairs. That checkpoint does not approve real-money use or prove
a sportsbook edge. The primary validated recommendations remain gated.

This run required no runtime changes or deployment. Verification used the real
approved odds batch, authenticated UI inspection and read-only database checks;
no paid calls were made to exercise failures or retries.
