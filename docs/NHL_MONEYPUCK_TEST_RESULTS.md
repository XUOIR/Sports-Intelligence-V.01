# NHL advanced-statistics test and verified release

Tested October 13–14, 2026 for XUOIR/Sports-Intelligence-V.01. Files came from [MoneyPuck's published downloads](https://moneypuck.com/data.htm), which permit attributed noncommercial use. No new subscription, paid odds refresh or AI generation was used.

## Actual source results

The October 14 team file contains **233,270 rows**, including **105 current-season games across all 32 teams**, through October 13. Actual decoded size: **127,056,736 bytes**. Server gzip transport was verified: **31,371,060 received bytes**, approximately 8.8 seconds. The goalie ZIP used **48,168 bytes**. Numeric validation, game/situation uniqueness, opposite-team reconciliation, power-play/penalty-kill inversion and goalie/team reconciliation passed.

All **16 completed October 13 games** in the independently fetched NHL response were present; final goals reconciled after accounting for the shootout winner's score bonus. This verifies that day, not every historical game against the NHL.

The archive contains **575 historical identity rows in 2011–2013** naming the same team on both sides. They remain quarantined, without inferred repairs or historical model approval. A cached season summary failed against the newer game file, even for some equal game counts. Fetching the current summary resolved this. The importer uses matched game-level team/goalie data, not unmatched season aggregates.

Rolling 5v5 share is `sum(xGF) / (sum(xGF) + sum(xGA))`, not an average of game percentages. GSAx is goalie `sum(xGA) − sum(goals)` using only `all` rows, without double-counting strength splits. Target-day/future games, playoffs and prior seasons are excluded from these regular-season windows. Samples use up to ten games and display the actual count. Minimum three for descriptive comparison is separate from existing model admission.

The isolated cache imported **96 entities**: 32 team windows and 64 goalie records. **44 goalies** have sufficient samples; **20** remain unavailable. Re-importing writes no duplicates. These data do not establish confirmed starters, normalized model factors, predictions or recommendations.

## Implementation and safeguards

- `backend/app/nhl_data.py` provides shared, tested validation and calculations for offline tests and the runtime adapter.
- Runtime ingestion defaults to disabled through `ENABLE_NHL_ADVANCED_STATS`. The Render release explicitly enables the tested feature; the development example remains disabled.
- The existing API service owns a daily **9:00 AM Pacific** task. No new paid Render service is created. The authenticated Settings import shares the same admission.
- **One batch attempt per calendar day** persists in PostgreSQL before network requests. Failures, cancellations, restarts and concurrent tabs cannot admit a repeat that day.
- Monthly transfer reservations stop at **1,500,000,000 bytes**. The team request requires gzip, allows at most 40 MiB received/160 MiB decoded, and gets one attempt. The goalie ZIP allows 2 MB received/8 MiB uncompressed; official verification allows 2 MB. No redirects or paid fallback.
- Complete, validated success releases only known unused transfer capacity. Failed/uncertain imports retain their reservation. Current measured team/goalie transfers imply about **0.94 GB in 30 days**, before small verification responses. This is a workload estimate, not a vendor quota or guaranteed future file size.
- Cache publication is atomic. Failure retains prior validated data, original observation time and visible stale status. Browser refreshes read the cache without downloading provider files.
- The matchup drawer preserves the existing theme and shows team 5v5 share, expected goals per 60, selected-goalie GSAx, dates and samples. Goalie selection leaves starter confirmation false. Administrative controls stay in Settings.
- Genuine pre-anchor raw statistics are retained in frozen snapshot context; post-anchor observations are rejected. The 15-feature vector, normalized factors, model approval and staking rules remain unchanged.

The source contract covers the 2026–27 season and requires an update before July 2027. Original historical observation times, model-version chronology and starter confirmation remain separate requirements.

## Verification

**35 offline/staging tests passed**, covering weighted aggregation, sample/day exclusion, duplicates, GSAx sign, schema changes, cache integrity, byte limits, gzip expansion/truncation, failed admission, atomic replacement and idempotency. Backend checks cover source ingestion, monthly rollback, successes/failures, absence of paid calls, authenticated refresh, repeated requests, stale cache reads and pre-anchor retention. All **152 backend tests**, **35 offline/staging tests** and **9 frontend tests** passed (196 total). Type checks and the production frontend build passed. The updated two-service Blueprint also passed Render's current public JSON Schema; automatic deploy remains explicitly "off".

Browser QA used real audited statistics in disposable local SQLite, with an explicitly illustrative Toronto/Edmonton matchup. It verified private login, unconfirmed goalies, insufficient samples, Settings isolation, the current theme and a 390-pixel mobile layout without horizontal page overflow. Live keys and real wagers were excluded; temporary servers were stopped.

Raw files, hashes, source observations, audits and SQLite caches stay in ignored `artifacts/nhl-low-cost-provider-research/moneypuck-offline-test/`. No predictive model is approved by this release.

## Verified live release — October 14

Both existing Render services are live. The backend deployed feature commit `73d22faee55dec8d27b608ae7d2ec25551e1e71c` in `dep-db7tkm0n74is73e523h0`, triggered by the Blueprint environment update. Logs show the Alembic pre-deploy completed and `/health/ready` returned 200. Independent requests also verified `/health/live` and `/health/ready` returned 200. The frontend deployed `762220c835cab4db141f6504eeb1c8e99cf8cf0f` in `dep-db7tndjl550s73dbtdm0`; Render confirmed Live. That later commit contains documentation and an EOF whitespace change only.

The production sign-in gate was verified using the existing credential. Independent unauthenticated requests to the frontend `/api/data/dashboard` and backend `/operations` both returned 401. The first authenticated Settings import was admitted at **12:50:26 PM Pacific** and succeeded at **12:50:47 PM**. Supabase independently confirmed **32 teams, 64 goalies and 105 games**, statistics date October 14, verified through October 13. Its durable ledger records exactly **one daily attempt** and **33,419,228 accounted bytes** against the 1,500,000,000-byte monthly cap. The initial 45,943,040-byte reservation released only known unused capacity on success. The import button is disabled after the daily attempt.

The actual October 14 Montréal–Washington matchup was opened through the live NHL sidebar. Both teams have six-game samples. Montréal's 5v5 xG share is 54.9% (2.62 xGF/60, 2.15 xGA/60); Washington's is 50.6% (2.98, 2.91). Selecting Jakub Dobes and Logan Thompson showed GSAx −4.022 and +3.452 with three and five appearances, respectively. Both remain explicitly **starter unconfirmed**. The selections did not write personnel evidence or change the WATCH state, unknown probability or zero stake. This validates those two displayed comparisons, not every fixture manually.

Post-release account metadata at **12:51:51 PM Pacific** still showed Odds API 497 remaining/3 used and OpenRouter US$0 use with the US$3 monthly-reset cap intact. The database recorded zero paid calls since the overnight audit interval began, zero bets and zero approved models. No paid fallback, odds refresh or AI generation was requested by the test/import.

The statistics feature is usable in the private dashboard. Verified-pick release remains dependent on genuinely confirmed starters, current matching execution prices, complete source-backed model inputs and successful chronological model validation. The importer and this release do not bypass those requirements. Daily scheduling is configured for 9:00 AM Pacific; the first scheduled run has not yet been observed.
