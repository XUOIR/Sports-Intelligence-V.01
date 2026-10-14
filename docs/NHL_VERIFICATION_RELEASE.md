# NHL verification and regular-season history — October 14, 2026

## Problem and resulting behavior

Upcoming games showed eight empty gate marks because the scheduler evaluates them during the final thirty minutes before the official start. The panel did not explain what evidence existed before that checkpoint. The replacement panel shows the exact T−30 time, each check's purpose, source availability and observed times, regular-season form samples, rest and back-to-back status. NHL map veto is clearly not applicable. Available facts never grant a gate or fabricate a probability.

The detail endpoint remains authenticated and reads saved PostgreSQL data only. Refresh saved evidence is a database read, separate from the metered manual odds refresh. Passed badges disappear when the panel, price or confirmation expires, the fixture becomes dirty, or the game starts. The current black, blue and violet theme and existing match sidebar remain intact.

Starter and market-review evidence can now be recorded without entering advanced model factors. Optional factors still require all four valid source-backed values and their existing normalization contract. New factors remain prohibited after T−30. Saving confirmed starters does not populate a missing forecast or approve a model.

## Verified NHL history defects

Production saved no history for Washington–Montréal despite having both teams' club-season responses. Montréal's preseason split-squad games share a start time; the old adapter included those games and the interval validator rejected the overlapping history. Other saved histories also contained preseason games. The old adapter invented a next-day midnight ending, then rejected that ending's date when selecting prior-day games, excluding yesterday's results and distorting rest.

The adapter now accepts completed, current-season regular-season games involving the exact team, with explicit non-tied integer final scores. It excludes preseason, other seasons, unrelated teams, same-day/future games and malformed rows. Conflicting duplicate final results remain a hard error. No end timestamp is invented: completion was observed in the bounded club-schedule cache before the anchor, and the actual start's Pacific date determines prior-day eligibility and rest.

The new `nhl-completed-games-v2` contract is included in the NHL model digest. Production fixtures cannot freeze legacy history after their new source metadata is recorded, and offline calibration rejects legacy history. Existing historical snapshots are preserved; no retrospective timestamps or forecasts are inserted. CS2's digest and ingestion are unchanged.

A local replay of the actual saved Washington and Montréal responses recovered six regular-season games per team, excluded four/five preseason games respectively, and identified both teams as back-to-back from their October 13 completed games. This replay made no live database writes or paid provider calls.

## Free-data boundary

One bounded read of the [official matchup response](https://api-web.nhle.com/v1/gamecenter/2026020106/landing) confirmed schedule/venue data and goalie season comparisons. This matchup lists multiple goalie candidates and provides no explicit confirmed starting-goalie field. Candidates cannot establish pregame confirmations. Record a current public team confirmation through the private evidence workflow; missing confirmations remain a blocker.

MoneyPuck's already deployed daily import supplies descriptive 5v5 expected goals and goalie GSAx with its existing daily and monthly transfer limits. These are not automatically normalized master-model factors, an approved forecast, or starting-goalie confirmations. The remaining model work is documented normalization, genuinely observed pre-anchor inputs, chronological calibration and untouched testing, and approval only after the existing requirements pass. No forecast, PLAY badge, paid subscription, automatic paid loop or real ticket was created.

## Validation

- 173 backend tests passed; 17 frontend tests passed (190 checks).
- Production frontend build and type checking passed.
- Tests cover yesterday's rest, preseason split squads, malformed/unrelated/future rows, conflicting final results, post-anchor observations, authenticated cache-only detail reads, absent/expired prices, missed anchors, optional starter-only evidence and prohibited factor backfills.
- Browser QA verified the populated panel, starter-only form, current/expired price messages and saved-evidence refresh. Mobile inspection at 390 pixels showed eight stacked check cards without drawer horizontal overflow. Temporary viewport overrides and servers are cleared after QA.
- Preview data includes a deliberately illustrative matchup, test prices/forecast and disposable SQLite records. Preview images do not establish production prices or predictions.

## Rollout and spending status

At 2:30 PM Pacific, Render's public status API still reported **Builds, deploys, and queued deploys are not starting in all regions** as identified. The [incident](https://status.render.com/incidents/8tsd93r1wbmz) was last updated at 2:04 PM. The existing backend was healthy (`/health/ready` 200), but `/performance` still returned 404: the previously submitted market release was not live. Its existing backend/frontend deployments are `dep-db7uhnrl550s73dekqj0` / `dep-db7ulhd9fdbs73dj400g`; do not submit duplicates or describe their changes as live.

Metered feeds remain deliberately paused through the existing operator control. A free provider metadata check at 2:30 PM confirmed 494/500 Odds API credits remaining (6 used), US$0 OpenRouter usage, and the US$3 key cap with monthly reset. The wallet remains US$10 with US$0 usage. The two earlier three-credit requests were already accounted for; no additional metered refresh or AI generation was sent during this continuation.

### Combined rollout — 2:44 PM Pacific

The older deployments were canceled after Render reported their Docker image builds complete but before they became live. Their replacements both explicitly target the tested code commit `df65017b6b61e9b08030c301b2c5981d6d8bdf24`, including the market pages, odds-matching repair and verification/history fixes:

- Backend: `dep-db7vbm67bikc73ar1bk0`, submitted 2:36:24 PM Pacific.
- Frontend: `dep-db7veh2jnfac73d2aii0`, submitted 2:42:28 PM Pacific.

Both replacements still showed Building / Awaiting logs at 2:44 PM. This is submission evidence, not successful deployment. Render's public incident API reported monitoring at 2:44 PM, updated at 2:43 PM; recovery does not establish that our releases are live. No environment secret, service plan, spend cap or credit reservation was reset. Temporary QA servers were stopped and the local preview tab was closed; private local pages had returned login redirects and the detail proxy returned 401 without a session.

To complete rollout, verify these combined releases' actual commits, migration/startup logs, source inputs, health and private pages. Resume metered feeds only after confirming the repaired odds matcher is live; admit one guarded three-credit manual refresh and inspect its saved counts and actual PlayNow prices. Preserve any failed/uncertain admission and diagnose it without repeated paid requests. Confirmed starters and a compatible validated model remain required before any verified pick.

### Final check — 2:53 PM Pacific

The combined backend Docker image finished exporting at 2:45:48 PM; the frontend production compilation and image export also completed (2:48 PM). Render had not progressed the releases to Live. The live backend still returned 200 for readiness and 404 for `/performance`, confirming the previous version remained active. At 2:49 PM PostgreSQL independently confirmed metered pause = 1, zero saved odds, zero new-contract history records, and zero approved NHL models. The controlled metered refresh was deliberately not run through the old matcher. No new migrations, real forecasts, price imports or live UI changes are claimed. Both exact deployment tabs remain available for continuation; do not cancel/resubmit these combined releases again merely because the platform is slow.
