# NHL First Release — Agreed Direction and Proposed First Experiment

Prepared October 15, 2026, from this active chat's release interview. Active repository: XUOIR/Sports-Intelligence-V.01. The product decisions below were accepted individually. The owner confirmed the shared direction and authorized the bounded offline experiment with “Let's go with yes.” This document does not approve any fitted model for production recommendations.

## Product decisions accepted by the owner

1. **NHL first, pregame recommendations.** Continue showing live scores; defer recommendations made during games.
2. **Final game winner.** Initial recommendations target the eventual winner, including overtime/shootout. Regulation-only winners, spreads, totals, props and other sports are later scope. Match actual provider settlement terms before using any price.
3. **Selective plays.** No minimum daily pick count. A game or entire slate may have no worthwhile bet. Show useful analysis where adequate data exists.
4. **Historical testing, then genuine live paper tracking.** Record forecasts and available prices before games. Distinguish reconstructed historical research, actual forward forecasts, simulated wagers and real transactions. Paper results do not change the real bankroll.
5. **Unconfirmed-goalie forecasts are permitted under a suitable tested model.** Display the actual information state and its uncertainty.
6. **Expected goalies may also be used for potential actionable plays initially.** Formal confirmation is not a universal first-release requirement. Test the model and decision policy for expected-lineup errors and late changes. Preserve source/projection basis and timestamps; expected is not confirmed. The present goalie-dependent model cannot gain approval by marking its missing confirmation gate true.
7. **Automation is the preferred outcome.** Manual review of a candidate's current PlayNow price and flagged news is reluctantly acceptable as a temporary initial fallback. Do not turn this into manual research on every fixture or a permanently manual design. Automated wager placement is outside the authorization.
8. **Free first, value over a rigid zero-cost rule.** Use suitable free sources when possible. A reasonable paid source/model can be reconsidered if it demonstrably fills a necessary gap; present verified capabilities, rights, costs and safeguards before purchase. No new subscription or numerical general data budget was approved. Existing provider limits and separately discussed AI/hosting costs remain distinct.

Additional matchup-simulation work is deferred unless evidence shows it adds value. Genuine forecast-versus-result tracking remains part of testing; a full-season study is optional, not a requirement to wait a season before a release decision.

## What a successful release must demonstrate

The owner's objective is a measured edge over available sportsbook prices. A high win rate, beating a simple historical-average reference, or a favorable backtest alone does not establish that objective. Recommendations need probabilities with demonstrated predictive quality and suitable calibration, matched actionable prices, an evaluated selection policy and honest forward performance reporting.

The technical pass criteria must be specified before the final approval test is examined. Exact sample sizes, uncertainty estimates, observation period and numerical thresholds are not yet accepted. Do not invent a profitable ROI history where matching historical PlayNow prices are absent or relabel reconstructed research as saved live forecasts.

The dashboard remains useful for statistics and clearly labeled research while those requirements are assessed. Model-quality, input-validity, freshness and exposure checks still apply. A provider outage, exhausted allowance or missing input must yield an explicit state, with no retry storm, paid fallback or manufactured edge.

## Proposed next implementation: isolated offline experiment

This bounded experiment was authorized and completed. Its [results and limitations](NHL_TEAM_MODEL_EXPERIMENT_RESULTS_2026-10-15.md) are separate from approval of live picks.

The completed [read-only inventory](NHL_TEAM_HISTORY_INVENTORY_2026-10-15.md) found 21,713 regular-season game IDs in the cached team file. Of these, 21,607 passed basic pairing checks; 2,132 of those have tied score fields and need verified final-winner labels. The cached goalie ZIP covers only season 2026. These are source-coverage findings, not ready training samples or evidence of model quality.

1. **Audit and manifest existing local history.** Verify source checksums, fields, seasons, paired fixtures, dates and target labels. Mark original collection times and reconstructed history honestly. The previously cached MoneyPuck team and goalie files have been located during the read-only inventory. Shootout winner labels require specific reconciliation; score fields alone must not silently produce wrong final-winner targets.
2. **Use the simplest dependable information contract first.** Test a team-strength baseline built from earlier completed results, opponent strength, home/away and rest. Compare an Elo-style rating and a small fitted statistical model. Add advanced factors only if their historical versions and availability are defensible. Do not use the current game's actual goalie as if known beforehand.
3. **Keep retrospective feature construction chronological.** Every game uses earlier eligible games, with date-grouped partitions and embargoes. Fit parameters and preprocessing using the appropriate earlier partition; fit probability calibration separately. Avoid final-season aggregates and provider-model revisions that introduce future knowledge.
4. **Preserve a genuinely untouched final evaluation.** Document model selection and the criteria before inspecting it. Do not select features or release thresholds repeatedly against the same final test. Preserve existing validation minimums; assess whether larger samples are required rather than treating a minimum as sufficient proof.
5. **Produce an honest benchmark.** Report data/label coverage, exclusions, Brier score, log loss, reliability, uncertainty, simple-reference comparisons and known failure cases. Use time-matched market comparisons only where actual compatible prices exist. If required labels or history are insufficient, report the gap and a bounded acquisition proposal rather than filling it with guessed outcomes.
6. **Return with the results and a concrete validation/release proposal.** A weak or failed result stays research. A promising result proceeds to the already-agreed genuine forward paper phase under a versioned contract, with final release criteria settled before approval testing.

The initial experiment should use existing local files and existing runtime libraries where possible. There are no paid provider requests, AI generations or new subscriptions in this experiment. Any necessary additional historical source access must be bounded, permitted and separately visible; no bulk fetch or provider-cap bypass is implied. A newly discovered paid need returns to the owner first.

## Implementation and operational boundaries

- Preserve the existing theme, information, login, FastAPI routes, scheduler, Next.js pages, source records and bankroll behavior.
- Keep the new offline model/version separate from the existing goalie-dependent model and its approvals. An experiment report is not a production approval record.
- Preserve durable spending admission, shared caches, concurrency protection, failure cooldowns and provider reconciliation. Do not issue paid odds refreshes or AI generations for testing.
- Preserve immutable forecast/input versions and actual quote timestamps. Price changes require recalculation using a matching approved forecast; a cache read never makes an old price current.
- Reuse the final-results ingestion path where appropriate for later paper tracking. Record operational failures and missing observations so the performance report does not hide unsuccessful collection periods.
- No production deployment, migration, fabricated approval, synthetic settlement or real-money recommendation activation is part of the offline experiment.

## Review status

The interview record is `docs/NHL_RELEASE_INTERVIEW.md`. The owner confirmed shared understanding and authorized the isolated experiment. It has produced a reproducible historical benchmark with no deployment or live approval. Numerical production approval criteria, a future paper candidate and any paid additions remain concrete follow-up decisions.
