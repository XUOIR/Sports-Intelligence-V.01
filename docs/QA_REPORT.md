# Verification report — October 13, 2026

Prepared locally; no deployment, Supabase mutation, or paid sports/LLM request was performed.

## Completed checks

- Backend: **60 tests passed in 15.61 seconds** using an isolated SQLite database and mocked provider transports. Tests exercise the full `main.py` application through its compatibility import.
- Frontend: **3 tests passed**, covering hidden/inactive polling suppression, five-minute source freshness, and Vancouver wall-clock formatting after the 2026 timezone transition.
- Next.js **production build passed**, including TypeScript checks and route generation. The verified local environment is Windows / Node 24.19.0; Linux container standalone output remains a deployment check.
- Dependency lockfile passed the package registry supply-chain check; the requested manifest uses the exact installed versions. Python requirements match the pinned dependency lock.
- Direct database URL tests enforce the specified Supabase host, username `postgres`, database `postgres`, and port 5432. Raw `!` and encoded `%21` preserve the same password without double encoding. Wrong hosts/poolers/ports are rejected with redacted errors. Pool size, overflow, recycling, and pre-ping were checked without connecting.
- Earlier browser QA verified sign-in, the match drawer, logging a disposable CAD 10 wager at -110, WIN profit CAD 9.09, and VOID correction to the original CAD 1,100 bankroll. Mobile ledger layout measured 390 pixels of page content at a 390-pixel viewport. Those test servers were stopped and no test tickets were stored in Supabase.

## Covered calculation and failure boundaries

American/decimal conversion; invalid/near-one/nonfinite odds; HALF_UP money/ROI; quarter Kelly and the 1.5% cap; minimum history samples; overlapping/target-date exclusion; source age/post-anchor rejection; calendar-month esports windows; chronological date partitions and two embargoes; Brier boundaries; exact numerical market identities; execution-key normalization and withdrawal; rescheduled snapshot archival; immutable anchors and missed-anchor HOLD; complete eight-gate approval; assessment reuse; evidence revision changes during AI review; 429 retry caps; outage/network circuit opening; durable daily/per-fixture limits; actual 15-second OpenRouter total deadline; oversized HTTP/mutation bodies; wager idempotency; and settlement reconciliation.

## Remaining live verification

Docker and a live PostgreSQL server were unavailable locally. Actual Supabase migration/TLS/privileges and Render container operation have not been verified. Public NHL feed smoke requests were rejected, so live response contracts are not established by this preparation. PandaScore plan fields, advanced NHL metrics, explicit goalie confirmations, and executable esports price coverage require real provider validation. Missing evidence keeps recommendation gates closed. Historical calibration must meet the required samples and validation criteria before probabilities can authorize recommendations.

The existing four integration secrets were detected as configured without printing their values. The original `.env` was preserved; `ADMIN_API_TOKEN` remains missing and must be configured before authenticated operation. Render generates the server token and dashboard password when the Blueprint is deployed by the user.
