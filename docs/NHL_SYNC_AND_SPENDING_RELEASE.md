# NHL pipeline and spending clarity — October 14, 2026

## Actual spending audit

At 3:48 PM Pacific, the free provider metadata endpoints reported OpenRouter key usage US$0 all time, today and this month; key limit US$3 with monthly reset; wallet US$10 with US$0 usage. PostgreSQL independently showed zero AI generation admissions or USD reservations. The UI's US$0.30 was the configured daily ceiling in a `used / cap` display, not a charge. Odds API usage remained nine credits, 491 remaining. No generation or additional paid odds refresh was used to investigate.

Settings now separates provider-reported spending, conservative app reservations and hard daily/monthly limits. Provider metadata is explicitly checked, cached for an hour and never fetched by a dashboard/status GET. Missing, stale, invalid or previous-UTC-day usage is unavailable, not an invented zero. Sub-cent charges retain up to six decimal places. [OpenRouter documents its usage day/month as UTC](https://openrouter.ai/docs/api_reference/limits); the existing app reservations remain in Pacific time. Monthly protection still applies across all days; neither the US$0.30/day ceiling nor the US$3/month ceiling is a spending target. Checking allowances skips PandaScore requests during the NHL-only phase.

The saved-data reload moved out of the main navigation to the data-status row on Overview, Bankroll and Model performance. It is labeled Reload saved data, retains inactivity protection and does not request metered odds or AI.

## Pipeline defects repaired

- The engine, verification panel and readiness counts now share the latest saved quote reader and strict same-book, same-market, same-timestamp two-sided price contract. A newer partial quote or future timestamp cannot be paired with an older opposite side.
- Once a compatible calibrated forecast exists, it remains visible if prices expire. Without a valid price pair, betting edge, target price, recommendation and stake remain locked. No probability is created without model approval.
- Freeze records the actual completed collection timestamp, the factor evidence ID and the factor source's original timestamps/payload. NHL calibration rejects factors lacking genuine pre-anchor provenance and rejects mismatched, malformed or future-observed final scores. The NHL model digest includes the strengthened data contract. Existing snapshots are preserved; old inputs are never backdated into the new contract.
- Result reconciliation attaches outcomes to captured inputs even when no baseline forecast exists. It first uses a matching saved official final score, or an already recorded fixture outcome, then falls back only to the existing bounded free NHL request. Invalid identities, teams, dates, tied or malformed scores cannot supply a new result. A record without a forecast receives no invented Brier score or model prediction. No wager settlement is automated.
- Startup schedules existing fixtures' future T−30 checkpoints before attempting a free upstream refresh. A temporary free-feed outage or exhausted free budget cannot alone prevent registration of known future checkpoints. Missed checkpoints still cannot be reconstructed retrospectively.

## Validation and limits

The full isolated suite passed 200 backend and 20 frontend checks (220 total), and the production frontend build/type checking passed. The integrated rehearsal covers source ingestion into an exact frozen snapshot, synthetic database-only model approval, one mocked AI review, expiry locking, retained forecasts, cached final-score labeling and validation export provenance. Its test approval and probabilities exist only in disposable SQLite; they do not approve a live model or contact OpenRouter.

Desktop and 390-pixel browser checks confirmed separated spending labels, a clean navigation bar, the relocated reload and no horizontal overflow. All caps, provider-side key settings, failure latches, duplicate protections, manual odds policy and private login remain enforced. No service plan, environment secret, paid subscription, real wager or live model approval was changed.

At 4:01 PM, production independently showed a newly captured Montréal–Washington T−30 snapshot at 4:00:01 PM, with the current regular-season history contract and no baseline forecast. Four older input snapshots lacked attached outcomes despite their fixture results already being recorded; the corrected reconciliation can attach those known outcomes without fetching them again. Those legacy snapshots remain ineligible to validate the current model. The live database still has zero approved models and zero usable outcome-labeled baseline records.

The remaining forecast work is a documented, reproducible normalization from the advanced facts into all four weighted model inputs, verified starting goalies and an adequate genuine historical validation corpus. Existing acceptance requires at least 300 training, 100 calibration and 100 untouched test records after date embargoes. Available xG percentages, a passed software test or an AI opinion cannot substitute for these. Recommendations remain on HOLD/WATCH until the actual requirements pass.

Deployment, live spending checks and outcome reconciliation results are recorded below after verification.
