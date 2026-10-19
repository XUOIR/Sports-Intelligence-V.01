# NHL forward validation — October 19, 2026

## Release scope

This continues the authorized private NHL paper release in
`XUOIR/Sports-Intelligence-V.01`. Existing FastAPI routes, Next.js theme, bankroll,
manual goalie confirmation, odds refresh safeguards and US$3 monthly AI cap are
preserved. No provider subscription, new hosting service, schema migration or
production model approval is introduced.

The original frozen candidate `nhl-team-paper-v2-617e76ac7eda` and its three
inference source files remain unchanged. No prior forecast, position or outcome
is overwritten. The new cohort is `nhl-xg-paper-v1-4e666a9116b1`, with full bundle
SHA `4e666a9116b1549d12c4da2fe995b8aa80bd13c0d90dfc383093e6cb66892ce4`.

## 1. Goalie source validation

The existing 72-hour Daily Faceoff pilot keeps its deadline, ten-minute cooldown,
request/transfer limits and failure latch. Changed reports remain immutable
revisions. Small, separate receipts now record successful unchanged rechecks,
including ETag/304 checks, without inventing new revisions. Missing-page events
are recorded as removals. Rechecks/removals use their actual observation times.
For new reports published after pilot activation, the dashboard also measures
source age at first observation, with sample count, median and 95th percentile.
This uses the site's update time; it is not original beat-writer-post latency.
Resolving a previously unknown NHL player ID does not create a new report sample.

After a reconciled official final, a separate bounded worker reads the public NHL
boxscore once and requires one explicit `starter: true` flag per team. It never
infers the starter from who played longest, a win decision or a pregame candidate
list. The fixture ID, scheduled start, team abbreviations and final state must
match. Official postgame truth cannot confirm a pregame lineup.

At T−30 and immediately before scheduled puck drop, grade the latest actually
observed source state, with a maximum twenty-minute observation age. Expected and
confirmed reports are scored separately. Removed, stale, unknown, unmatched and
post-cutoff reports cannot earn accuracy credit. Games entirely missing from the
feed during the pilot window still enter the coverage audit. Source times never
substitute for observation times.

The worker shares the existing free NHL request allowance and additionally caps
checks at sixteen per day, one attempt per fixture, a 1 MB response and 200 MB of
conservative monthly response reservations. It follows no redirects and performs
no automatic retry. Interrupted attempts remain consumed. Private cached results
retain selected checkpoint evidence and report revision references; regular raw
evidence follows existing retention.

Initial production check: the two October 18 completed games have explicit
official starter truth saved. None of their four goalie sides is counted as a
correct pregame prediction: our first reports arrived after both games started.
Tonight's pregame observations can only be graded after genuine finals.

## 2. Prices and genuine forward comparisons

The owner refreshed NHL prices around 1:12 p.m. PT on October 19. The original
paper workflow captured those prices. No duplicate odds refresh was issued while
building or testing this release.

The new candidate's forecasts were saved at their actual collection times,
approximately 1:33 p.m. PT. The earlier price snapshot was already stale and is
not backfilled as a fresh candidate observation. Both cohorts read future price
updates through the existing saved-odds path. One new guarded refresh near a
useful pregame decision window can supply both cohorts; no separate provider
request per model is needed.

The five attempts per rolling 24 hours, three-credit reservation per complete
NHL refresh, daily/monthly provider limits, unique request identities, failure
stops and prohibition on automatic paid retries remain intact. AI is not needed
for paper forecasts, grading, calibration, source validation or model fitting.

## 3. Independent xG/goaltending candidate

The target remains the home team's final win, including overtime/shootout. The
five inputs are prior-result rating difference, rest difference, back-to-back
difference, prior-game 5v5 xG share difference and team goaltending form difference.
No market price is a prediction input.

Team goaltending sums goalie GSAx and exposure in the last ten prior team games,
with an eight-game zero-centered exposure prior. At least five prior games are
required for both xG and goalie windows. It is a team goaltending feature, not a
named starting-goalie adjustment. Actual starters from the target game never
enter historical feature construction. Expected/unknown named starters are
permitted under this declared team-level model contract.

Historical data: the already cached MoneyPuck team file, already admitted official
NHL result pages, and eight published 2018–2025 goalie archives. Acquisition has
one durable attempt per archive, 2 MB per archive and 24 MB overall, with no
redirects, paid calls or automatic retries. Only about 4.3 MB was downloaded.
Game identity/date/source reconciliation quarantines inconsistent statistics;
official outcomes alone determine winners. Shootout score handling is preserved.

The plan was written before fitting: fit 2018–2021, select among three declared
ridge penalties on 2022, refit fit+selection, calibrate on 2023 and compare on
2024–2025. All games on a date are predicted before that date updates ratings.
Rolling statistics exclude the entire target date. Scaling is learned from fit
data, and calibration uses a separate later partition.

On 2,446 matched historical comparison games:

| Measure | Team-only comparator | xG/goaltending candidate |
| --- | ---: | ---: |
| Brier score | 0.242480 | 0.241015 |
| Log loss | 0.677704 | 0.674570 |
| Directional accuracy | 56.30% | 56.99% |

Paired Brier improvement: 0.001465; exploratory 95% week-block interval
0.000505–0.002461 across 51 blocks, 2,000 resamples, fixed seed 20261015. This
qualifies the candidate for a separate forward paper test under the declared
research checks. It does not demonstrate an edge over a sportsbook.

Historical source vintages were downloaded recently and are not verified as the
versions available before historical games. The test seasons were examined in
earlier team-only research. These are explicitly retrospective exploratory
results, not untouched prospective validation, original historical forecasts or
historical PlayNow profit. No simulated game outcomes are used as training data.

The frozen bundle contains coefficients, calibration, source-manifest hash,
research report and inference source hashes. Pure Python runtime inference is
checked against the research implementation. Production needs no NumPy install.
The current baseline's immutable input archive is verified before its prior-game
rating/rest vector can be reused by the candidate.

Daily imports now save the small team-goaltending feature batch alongside the
existing descriptive cache. For today's first candidate only, an explicit,
one-time bootstrap read the exact same goalie ZIP checksum already admitted by
the 9:00 a.m. import. It reserved 2 MB within the existing MoneyPuck monthly limit,
kept that conservative reservation, and recorded the actual new derivation time.
It did not reset the daily import, renew the original statistics timestamp or
replace a source version. A checksum mismatch would have stopped it until the
next scheduled import. The bootstrap cannot be automatically repeated.

All four October 19 candidate forecasts are genuinely saved before puck drop:

| Away at home | Home probability | Away probability |
| --- | ---: | ---: |
| Anaheim at New York Rangers | 54.39% | 45.61% |
| Colorado at Philadelphia | 33.84% | 66.16% |
| San Jose at Toronto | 54.78% | 45.22% |
| Pittsburgh at Utah | 59.16% | 40.84% |

These are research forecasts and can be wrong. They are not verified plays.
Future fixtures remain pending their match-day statistics rather than receiving
invented inputs. Original baseline forecasts remain separately visible.

## 4. Forward performance and settlement

Model Performance gains a separate Forward Model Validation section with:

- Per-version genuine forecast and final counts; Brier, log loss and directional
  accuracy. Exact 50/50 forecasts have no directional pick.
- Model-versus-margin-adjusted-PlayNow Brier on the same resolved priced games.
  Price observations are rechecked for book, identity, source age and pregame time.
- Calibration groups, sample sizes and Wilson intervals for observed home wins.
- Independent one-unit paper positions and ROI; no wager ledger or bankroll writes.
- Closing value only when a matching price pair was actually observed in the last
  five minutes before scheduled puck drop. Earlier snapshots cannot masquerade as
  closing prices, and missing closing observations remain unscored.
- Candidate forecast history and goalie source-validation coverage/accuracy.

The existing official-result settlement job resolves all paper cohorts. No manual
wager is treated as a forecast. Fourteen collection days and one hundred resolved
price pairs trigger an operational review only; production approval is separate
and never automatic. The current NHL approval gate remains closed.

Reference methodology: [probability calibration](https://scikit-learn.org/stable/modules/calibration.html)
and [chronological validation](https://scikit-learn.org/stable/modules/cross_validation.html#time-series-split).
MoneyPuck's [published downloads and terms](https://moneypuck.com/data.htm) apply;
the dashboard preserves MoneyPuck attribution.

## Verification and owner actions

Local verification passed: **348 backend tests**, **29 frontend tests**, the
Next.js production build, and **5 research/runtime consistency and acquisition
checks**. Both frozen model integrity checks passed; the original baseline hash
remains unchanged. The API read test requires authentication and proves that a
performance request does not fetch a provider or create a forecast.

Commit `2efb7268c4e34b7dc3cfb31eeb4107ca3ce5dbb8` is live on both services:
backend deploy `dep-dbb83rajnfac738c8psg`, frontend deploy
`dep-dbb84dtg1s2s738ieedg`. Backend liveness/readiness and the frontend sign-in
page returned HTTP 200 after release. No new service error logs appeared in the
checked post-release window. No schema migration or hosting-plan change was
required. Authenticated interface and price results are recorded below.

The frontend release switch interrupted the first manual price request before
the Odds API admission. The saved request was checked, no new ProviderCall or
credit reservation existed, and the UI returned to four remaining slots. The
request was not blindly repeated. After both services were live, a new explicit
guarded snapshot was requested for the genuine saved paper forecasts.

Statistical validation requires future games to happen; no result is filled in
early to complete a checklist.

The guarded snapshot completed at **1:51 p.m. PT**: **48 quotes**, including
**24 PlayNow quotes**, from **15 matched games**, for **exactly three credits**.
The provider reported **482 credits remaining**. App reservations showed
**6 / 15 credits today**, **18 / 500 this month**, and **3 / 5 refresh slots
remaining**. No AI generation was requested. Both cohorts share this snapshot.

The candidate recorded eligible fresh pairs for all four October 19 games.
None reached its declared +3 percentage-point threshold, so it recorded zero
paper positions at that observation. A no-play outcome is permitted. These
saved edges remain historical when the five-minute price window expires.

Authenticated live verification confirmed the candidate probabilities, saved
price/source times and signed edges, separate per-version scoring, probability
calibration, and goalie coverage/actual-starter tables. The original cohort has
24 genuine forecasts, 20 resolved games, Brier 0.2223 and 70% directional accuracy
at this check. Only two resolved price pairs and one settled paper position
exist; market superiority is not demonstrated, and the paper position lost.
The candidate has four saved forecasts and no finals yet. No future outcome,
closing quote or goalie accuracy was fabricated to populate an empty metric.

The new comparison and candidate forecasts are placed before the original
ledger. Both complete histories remain available in bounded scrollable tables;
the sticky match feed, theme and existing information are preserved.

**Urgent:** no provider purchase or key is required. Use the guarded odds refresh
near a useful pregame window if current PlayNow comparisons are needed. A single
refresh supplies both paper cohorts and consumes three provider credits.

**Can Get To:** the Daily Faceoff supported-use enquiry remains useful. REA was
reviewed as an optional website-analysis tool; no REA software was installed and
no Statistips code, private endpoint or model was copied into this release.
