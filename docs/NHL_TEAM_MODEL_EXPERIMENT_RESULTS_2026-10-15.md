# NHL Team-Model Experiment — October 15, 2026

**Completed offline. Useful baseline signal, insufficient evidence for real-money recommendations.** No model was deployed or approved. The existing dashboard, production verification gates, bankroll and provider limits were unchanged.

## What was established

Suitable free data is enough to test a basic NHL team-strength model without archived pregame goalie confirmations or a paid AI service. This run used 13,512 official regular-season results from 2015–16 through 2025–26, reconciled against the existing MoneyPuck archive by game identity and date.

The preselected calibrated statistical model improved on a simple home-team reference across two held-out seasons. Its latest season was substantially weaker, and there are no matched historical PlayNow prices. Consequently this experiment does not establish that the model beats sportsbooks, offers positive expected return or qualifies any live bet.

## Data and cost

The official NHL historical-results route returned final scores, team IDs and period identifiers. Two capped result pages plus a team reference and a small schema probe used **four requests, 3,378,935 bytes**, with **zero Odds API credits and zero OpenRouter generations**. No subscriptions or runtime dependencies were purchased/installed.

The collector has durable admission/cache verification, a ten-attempt total limit, 12 MB per-request and 48 MB aggregate byte exposure limits, with no automatic retries or redirects. Failures and uncertain attempts remain consumed. It accepts fixed public NHL historical routes only. Model execution itself is offline and cannot call a provider.

All 13,512 game IDs, opponents, venue sides and dates matched the cached archive. The official final scores resolved **1,022 shootout winners**. Five games had other score discrepancies in the archive, totaling ten affected team rows; these are listed in the manifest. Official scores are the sole source for training outcomes and goal history. No missing winner was guessed and no xG or specific-goalie feature was used.

Source access was to [official NHL game results](https://api.nhle.com/stats/rest/en/game); individual query URLs and hashes are retained in the acquisition ledger and pre-evaluation manifest. The cross-reference file was an existing [MoneyPuck download](https://moneypuck.com/data.htm), used within this private research workflow and credited here. The original collection times remain preserved; these are reconstructed historical records, not originally saved pregame forecasts.

## Frozen experiment design

The declared plan is [nhl-team-v1.json](../backend/research/plans/nhl-team-v1.json). Configuration, source hashes and executable-code hashes were saved before evaluating held-out performance.

| Partition | Seasons | Eligible games | Use |
| --- | --- | ---: | --- |
| Warm-up | 2015–16 through 2017–18 | Earlier history | Initialize ratings/history; not final evaluation |
| Fit | 2018–19 through 2021–22 | 4,523 | Fit initial statistical candidates |
| Selection | 2022–23 | 1,312 | Choose declared rating/regularization settings |
| Calibration | 2023–24 | 1,312 | Fit probability calibration separately |
| Final test | 2024–25 and 2025–26 | **2,604** | Evaluate after selection/calibration are fixed |

The selected statistical candidate was refitted on fit plus selection data (5,835 games), then calibrated on 2023–24 only. All partition boundaries have more than the required one-day gap. Historical features use only earlier game dates; all predictions for a date precede that date's outcome updates. Fitted coefficients and calibration remain fixed throughout the final test, while ratings update using earlier actual results as predeclared.

Eighteen Elo configurations and six regularized statistical candidates were compared using the selection season only. The selected rating settings were K=10, 35 home-rating points and 0.75 season carry. The simpler statistical feature group—rating difference, rest difference and back-to-back difference—was selected over the group adding recent score/win-rate differences. This does not establish that xG or goalie data would be unhelpful; they were not tested.

The **calibrated statistical model** was declared the primary final model before final-test results were read. Other models remain comparisons; the primary was not chosen by taking the best test score.

## Final-test results

Lower Brier error and log loss are better. Winner accuracy means choosing the model's more likely winner across all eligible test games; it is **not** selective bet win rate or ROI.

| Model | Brier error | Log loss | Winner accuracy |
| --- | ---: | ---: | ---: |
| Home-team reference | 0.24831 | 0.68977 | 54.22% |
| Elo | 0.24313 | 0.67920 | 56.11% |
| Calibrated Elo | 0.24302 | 0.67892 | 55.99% |
| Statistical model | 0.24241 | 0.67752 | 56.72% |
| **Preselected calibrated statistical model** | **0.24195** | **0.67658** | **56.49%** |

The primary Brier improvement over the reference was 0.00636. The predeclared paired calendar-week cluster bootstrap gave an exploratory 95% interval of **0.00286 to 0.01013** across 54 week clusters, using 2,000 deterministic resamples. This supports further investigation of predictive signal; it is not evidence of a market edge.

### The recent-season weakness matters

| Test season | Games | Primary accuracy | Reference accuracy | Primary Brier | Reference Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024–25 | 1,302 | 58.83% | 56.30% | 0.23596 | 0.24697 |
| 2025–26 | 1,302 | 54.15% | 52.15% | 0.24794 | 0.24965 |

Additional, explicitly post-evaluation season diagnostics gave a Brier-improvement interval of **−0.00284 to 0.00637** for 2025–26, which includes no improvement. The aggregate result must not conceal that uncertainty. The season-specific diagnostics do not retroactively change the predeclared experiment checks or tune the model.

Calibration is also imperfect. For example, 985 games received home probabilities averaging 54.88%, with an observed home win rate of 52.79%. Only three games were in the 80–90% home-probability band, so that band cannot support a confident reliability claim. Full bins and Wilson intervals are in the machine-readable report.

## Known limits and next-version requirements

- **No historical PlayNow ROI or market comparison.** Compatible, time-matched prices are missing. Neither choosing favorites nor beating a home-team reference demonstrates a tradable edge.
- **No demonstrated expected-goalie adjustment.** This baseline deliberately omits specific starters, injuries and lineup news. A later adjustment must be evaluated for the actual expected/confirmed information state.
- **Team continuity needs refinement.** The official reference assigns Utah Hockey Club ID 59 and Utah Mammoth ID 68 to franchise 40. V1 keys history by team ID and restarts history after that rename. Its ten-prior-game rule excludes the first ten fixtures under each ID, accounting for 20 excluded final-test games. Preserve the reported v1 result; correct continuity in a new version before paper deployment, with honest acknowledgment that these final-test seasons have already been examined.
- **Reconstruction has limits.** Current historical source versions cannot establish original pregame observation times or every historical correction. Date-level inputs and declared exclusions do not replace a genuine forward record.
- **No production approval.** Passing three aggregate research-progression checks means promising for further paper research only. It does not meet the owner's objective of a proven price-relative advantage.

## Verification and reproducibility

All **20 isolated research tests** passed, covering source budget/cache failures, duplicate admissions, invalid outcomes, shootout labeling, score discrepancy handling, future/same-day leakage, chronological splits, cold starts, calibration and deterministic uncertainty. The existing backend suite passed **220 tests**. Production requirements and application files were unchanged.

A second run with the same plan, sources and model code produced **byte-identical prepared data, fitted parameters and prediction CSVs**. Independent recomputation from the prediction CSV matched the reported Brier scores, all 2,604 game IDs were unique, and every recorded latest input date preceded its target date. The frozen executable-code hashes still match. The second run made no provider requests and was a reproducibility check, not a retuning exercise.

Artifacts under `artifacts/nhl-team-model-experiment/run-v1/` include the pre-evaluation manifest, fitted model, prepared games, held-out prediction CSV, full report and post-evaluation diagnostics. The raw data/artifacts remain ignored by Git. Reproduction commands and the dependency boundary are in [the research README](../backend/research/README.md).

## Recommended next milestone

Prepare a separately versioned paper-research candidate with correct team/franchise continuity and a predeclared forward evaluation policy. Record original forecast/input versions and actual available PlayNow prices before games, then score real outcomes. Evaluate price-relative performance, calibration, recent-period stability and operational completeness; keep research and real bankroll records separate.

The minimum observation period, sample/power requirements, selection threshold, uncertainty margin, price freshness and paper-to-live criteria must be specified before that phase is used for approval. Do not promise a fixed short deadline or promote this model to verified plays on the basis of 56.49% winner accuracy. No paid data purchase is warranted by this first benchmark alone.

A [concrete paper-protocol draft](NHL_FORWARD_PAPER_PROTOCOL_DRAFT.md) proposes a 14-day/100-pair operational checkpoint, followed by a later evidence review with explicit sample/time floors and uncertainty requirements. These are proposals for review, not newly accepted criteria or a prediction that an edge will be demonstrated within that period.
