# NHL reliability check and midnight odds reset — October 19, 2026

## Scope

Continue the authorized NHL paper workflow in `XUOIR/Sports-Intelligence-V.01`.
Preserve the minimal interface, all existing information, frozen forecast
versions, provider spending safeguards and the US$3 monthly AI cap. The owner
also requested changing odds-refresh attempts from a rolling 24-hour allowance
to a daily allowance renewing at midnight.

## Findings and recovery

- Both existing Render releases were live; no application error logs appeared
  in the checked post-release window. Database logs had no ERROR/FATAL entries
  in that window. The database advisor check raised no data-path blocker;
  unrelated advisory findings were not used to expand this change's scope.
- The Daily Faceoff pilot halted at **3:13 p.m. PT** after an HTTP `ReadTimeout`.
  The stored error category establishes a transport timeout, not an access
  denial or schema failure. The reservation remained consumed; there was no
  automatic retry. Its last successful observation was 3:02 p.m.
- One explicit recovery used the existing authenticated Resume control at
  **4:35 p.m. PT**. It succeeded, matched all four games and used one additional
  free source request. The request count moved from 42 to 43; the original
  October 21, 6:53 p.m. PT expiry and all caps were retained.
- The earlier outage is real missing coverage. New observations cannot repair
  a missed T−30 or pregame checkpoint for games that have already started.
  Expected reports remain expected; postgame truth never confirms a lineup
  retroactively.
- No newly completed fixture was waiting for settlement. The new candidate's
  four saved forecasts had no finals yet at the check; those games cannot be
  graded early. The scheduled result/settlement and postgame starter jobs remain
  responsible for actual finals.

## Independently checked forward accounting

Read-only SQL recomputation agrees with the dashboard:

| Cohort | Saved forecasts | Resolved | Brier | Resolved price pairs |
| --- | ---: | ---: | ---: | ---: |
| Baseline `617e76ac7eda` | 24 | 20 | 0.2223123325 | 2 |
| xG candidate `4e666a9116b1` | 4 | 0 | — | 0 |

The baseline's two resolved matching PlayNow pairs have market Brier
0.1856708070. The baseline has six matching saved pairs overall and the xG
candidate four. These samples do not demonstrate a sportsbook edge. The older
`405edb95e305` cohort remains separate.

The audit found zero captured forecasts at/after their scheduled start, zero
finals missing a settlement timestamp, and zero settled outcomes disagreeing
with a saved official fixture outcome. No real bankroll or ticket was changed.

## Changes

1. **Daily odds admission:** count durable Odds API admissions within the current
   America/Vancouver calendar day, including failed/uncertain attempts. At
   midnight the next day's allowance becomes available by querying a new date
   range; no ledger row or credit reservation is deleted. Reuse the existing
   `ODDS_REFRESHES_24H=5` deployment setting as a legacy name, with its new daily
   semantics documented. No environment secret or hosting setting changes.
2. **Midnight safety:** derive the date range, request timestamp and daily/monthly
   credit keys from the same admission instant after the shared control lock.
   Cross-midnight waits cannot mix two allowance periods. Prior unfinished calls
   continue to block new requests. The monthly 500-credit cap, 15-credit daily
   cap, UUID idempotency, no-resend rule and provider failure latch remain.
3. **Minimal counter clarity:** Settings shows “used today” and “remaining”, plus
   the next midnight reset. A 5/5 remaining display previously meant no attempts
   used, rather than exhaustion. The actual live allowance was three remaining
   at audit time. The midnight browser update reloads saved status only, using
   the server's remaining interval to tolerate client clock differences. It does
   not issue a provider refresh or make old odds current.
4. **Useful goalie errors:** future source timeouts/network failures receive
   allowlisted explanations in the existing status message. Raw exception URLs,
   credentials and response bodies are not exposed. Recovery still requires an
   explicit resume; there is no added automatic retry.
5. **One existing forecast label:** Daily Matchups identifies its displayed
   baseline as “BASELINE · PAPER RESEARCH”. No model selector, page, chart,
   prediction change or additional information block is added.

## Verification

- **355 backend tests passed**, including Pacific midnight, UTC-midnight
  non-reset, 23/25-hour historical DST days, monthly-cap preservation, durable
  old UUIDs and unfinished calls spanning midnight.
- **29 frontend tests passed**, and the Next.js production build passed.
- A mocked read-timeout test proves saved goalie reports survive, failed
  transfer reservations stay consumed, automatic repetition is blocked, explicit
  recovery preserves the deadline and no paid provider call is created.
- An end-to-end local settlement test resolves two differently predicted
  cohorts against one official outcome. Repeated settlement preserves forecast
  inputs/times and original settlement times, and keeps scoring/paper returns
  separate without touching Bankroll or calling a provider.
- Both model integrity checks pass with the original full hashes:
  `617e76ac7eda011241cd396ca45b0a80c97d62f2d70c30294c4253cd43667756` and
  `4e666a9116b1549d12c4da2fe995b8aa80bd13c0d90dfc383093e6cb66892ce4`.
- The actual React refresh component was mounted in an isolated local harness
  with a simulated server midnight. It changed from five used/zero remaining
  to zero used/five remaining through one saved-data callback and **zero provider
  calls**, despite the browser and simulated server clocks differing. This
  verifies behavior without changing production time or spending odds credits.
  It is not a claim that a real production midnight has already been observed.

No Odds API refresh or AI generation was issued during this work. At the audit,
the day's ledger still had only the two earlier successful odds requests,
reserving six credits total. The verified production release identifiers are
recorded below.

## Verified live release

Commit `6583afd4e3261bfa3f65c2fdc9e19fe9d084cf23` is live on both services in
the previously authorized Terry's workspace:

- Backend `dep-dbban5c9v7es73ehgf9g`, live at 23:46:16 UTC.
- Dashboard `dep-dbbanpvf3r2c7386cu90`, live at 23:47:44 UTC.

Backend liveness/readiness and frontend sign-in returned HTTP 200. No new Render
error logs appeared in the checked post-release window. No migration, hosting
plan change or secret update was required.

Authenticated Settings visibly shows **2 of 5 used today · 3 remaining**, with
the next reset **October 20, 12:00 a.m. Pacific**. The actual live screenshot is
`artifacts/nhl-reliability-2026-10-19/daily-reset-live.jpg`. The separate
`midnight-reset-local.jpg` records the explicitly simulated component check,
which is not a live reset of production allowances.

The recovered goalie collector also completed its next regular scheduled check
at **4:46 p.m. PT**, matching four games; the pilot remained active at 44/100
daily source requests. This is a verified recovery and one following scheduled
success, not proof of permanent source reliability. The earlier missed pregame
coverage remains missing. Both frozen forecast versions and their saved counts
remain intact. Actual new-game results still await official finals.

Authenticated Overview also shows the baseline paper label on all four existing
Daily Matchups cards. No additional selector, chart or page was introduced.

## Owner actions

**Urgent:** none for this change. A daily reset does not keep prices fresh or
remove the need to resume a genuinely failed paid-provider request.

**Can Get To:** confirm supported ongoing automated access with Daily Faceoff.
The private pilot still has its original deadline; reliable permanent sourcing
is separate from a successful recovery.
