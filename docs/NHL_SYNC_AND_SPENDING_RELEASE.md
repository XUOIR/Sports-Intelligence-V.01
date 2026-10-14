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

## Verified rollout and data repair — 4:14 PM Pacific

Both existing paid Docker services are live on `68b71455900972bb20b2b13932f40b1969885743`:

- Backend `dep-db80o19srm7s7389cf90`, submitted 4:11:01 PM, live 4:11:39 PM. Alembic pre-deploy completed, startup passed and readiness returned 200.
- Frontend `dep-db80o30u01pc738fhjj0`, submitted 4:11:08 PM, live 4:12:19 PM. The production Next.js build and startup passed.

One explicit allowance check through the live Settings page used only free metadata. It saved and displayed OpenRouter daily/monthly spending **US$0.00**, app reservations **US$0.00**, daily ceiling **US$0.30** and monthly ceiling **US$3.00**. The provider key remains capped at US$3 with monthly reset and the wallet at US$10. Odds API usage remains **9 used / 491 remaining**; PandaScore checks were skipped. The main navigation contains Overview, Model performance, Bankroll, Settings and Sign out; Reload saved data sits in the data-status row and was exercised without a paid request. Live cards still show real xG and expired-price labels with no forecast or betting edge. Anonymous backend/proxy reads returned 401 and private pages redirected to login.

The local maintenance connection failed to authenticate; no secret was printed, reset or changed. The connected Supabase session independently verified the four existing fixture outcomes and recovered exactly those four missing snapshot labels, guarded by null outcome, null baseline, null prediction and null Brier conditions. Four audit records record the recovery. No upstream request, wager mutation or forecast was involved. A subsequent independent query confirmed five raw snapshots, four attached outcomes, zero baseline records, zero model predictions and zero Brier scores. The recovered legacy records remain ineligible for current-model calibration.

Both temporary QA servers were stopped and the mobile viewport override reset. No metered feed was paused/resumed, and no reservation, cap, service plan or credential was reset. The next required model work remains normalization plus authentic validation data and starter evidence; no passing test or recovered outcome is represented as a live approved model.
