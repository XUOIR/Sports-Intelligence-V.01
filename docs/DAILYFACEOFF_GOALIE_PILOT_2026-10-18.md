# Daily Faceoff goalie pilot — October 18, 2026

## Scope and operation

A private, explicitly started, 72-hour shadow test reads the public, dated
starting-goalies HTML page. It saves only game/team identities, goalie names,
reported states, the site's update times, sanitized reporter links, observation
times and body hashes. Article prose, images, rankings, sportsbook odds and
Daily Faceoff player IDs are excluded. No hidden API, /api/ or /cms/ route is used.

Settings → Daily Faceoff Test Feed provides Start 72-Hour Test, Pause, Resume,
Check Now and Reload Test Status. The deadline and every allowance survive
restarts and other tabs. Resume preserves the original deadline and cooldown.
The scheduler is idle before activation and after expiry. When active it checks
only within eight hours of today's upcoming NHL games. An explicit initial or
manual check can observe started games, clearly labeled as review-only.

## Hard safeguards

- At least ten minutes between shared collection admissions; concurrent tabs
  and instances serialize on the same database control row.
- 100 HTTP request reservations per Pacific day, including crawler-policy reads.
- 12 MB of reserved source-body wire bytes per day; 200 MB per calendar month.
- Before dispatch, reserve 1 MB per possible HTTP request. Successful, fully
  validated imports release only known unused body-byte capacity. Failed,
  canceled or uncertain attempts retain all reservations, including requests
  conservatively reserved but not sent. Headers/TLS are not measured here.
- Each response: 1 MB maximum wire body, 2 MB maximum decoded HTML; robots.txt
  is limited to 64 KB decoded. Streaming gzip decoding is bounded.
- Forty-second overall collection timeout. No redirect following, browser
  impersonation, automatic retries or challenge bypass.
- Access failures, format changes, crawler denial and uncertain failure halt
  the pilot until an explicit resume. An unfinished attempt also stops later
  admissions after restart. Pause does not revoke an already dispatched read.
- Crawler rules are cached for at most 24 hours and re-evaluated against each
  dated public URL. More specific agent/path rules win; equal paths favor Allow.
  A slower crawl-delay/request-rate requirement stops the current pilot policy.
- ETag/304 reuse requires compatible, previously validated, same-date facts.
  Unchanged reports do not create duplicate evidence revisions.

## Verification boundary

Reports appear alongside the existing manual goalie workflow as source reports.
They never change manual selections, personnel confirmation, fixture dirty/state,
model weights, frozen inputs, probabilities, prices, stakes, bankroll or AI calls.
There are no paid API calls in this collector. The existing US$3 monthly AI cap
and all Odds API safeguards are unchanged.

Match by unambiguous normalized team identities and a compatible absolute game
start. Match names to saved NHL player IDs only when unique; never interpret a
Daily Faceoff ID as an NHL ID. Historical identity references do not make old
statistics or roster availability current. Missing/ambiguous matches stay visible.

Manual-versus-source comparison distinguishes agreement, conflict, expired manual
confirmation and an unconfirmed source. Removed reports and expired observations
cannot retain a fresh label. Source reports are never backdated into an anchor.
The site update time is not claimed to be the original reporter's publication time.

Existing private/RLS-protected provider_state, runtime_limits and source_evidence
storage is reused without a schema change. Changed reports retain observed
revisions; source evidence follows the existing seven-day retention, and pilot
page/report caches expire after eight days. The frozen paper candidate is unchanged.

## Validation

Tests cover factual-only extraction, expected/confirmed separation, malformed and
future reports, unsafe reporter links, crawler specificity, request/byte caps,
atomic rollback, stale cache identity, wrong/ambiguous game/player matches,
retractions/removals, ETags, failures/redirects, compressed oversized bodies,
interruptions, pause/resume/deadline persistence, auth and cache-only GET routes.
The unmodified paper model passes its offline consistency checks.

Deployment and actual source checks are recorded below after release. Passing
local/mock tests does not establish reliable Render access or multi-day coverage.
Source reuse terms remain unverified; this test is not a claimed API licence.

## Owner actions

**Urgent:** sign in to the dashboard when requested so the live interface can be
checked. No API key, subscription or provider purchase is needed for this pilot.

**Can Get To:** send the prepared Daily Faceoff enquiry asking about supported
access, factual-status caching, research/model use and any published limits or
pricing. Reuse the contact text in NHL_STARTER_AND_SOURCE_RELEASE_2026-10-16.md.
