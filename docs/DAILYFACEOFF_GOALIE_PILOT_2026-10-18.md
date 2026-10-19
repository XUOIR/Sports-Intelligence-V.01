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

The final backend suite passed **315 tests**, including 39 collector checks.
The frontend passed **29 tests** and its production build. The frozen paper
candidate also passed its two existing offline consistency checks. Passing
local/mock tests does not establish reliable multi-day access or source accuracy.
Source reuse terms remain unverified; this test is not a claimed API licence.

## Actual release and first collection

- Backend commit `49a8bf2eacb14dd0965293b5e5ce2a526fc1e8b1` is live on
  `sports-intelligence-api`; deploy `dep-dbanehlg1s2s73cpjsm0`. The existing
  migration/pre-deploy stage completed, and `/health/live` and `/health/ready`
  returned HTTP 200. No schema migration or service-plan change was required.
- The frontend's initial collector release on the same commit reached live;
  deploy `dep-dbaneics728c738rfoo0`. The final display-only refinement is also
  live on commit `f7e14238c4c4355ac0a913e5351fd9c115b617f7`, deploy
  `dep-dbanil49v7es7397irrg`. It preserves the gradient heading and describes
  a started game without claiming when the report was first observed.
- The requested bounded pilot was activated through the authorized project
  connection at **October 18, 6:53:33 p.m. PT**, with an audit entry. The original
  deadline is **October 21, 6:53:33 p.m. PT**. The stored deadline was formatted
  in the application's Pacific-time convention without changing its instant.
- The production scheduler admitted the first check and completed it at
  **October 18, 6:53:47 p.m. PT**. It fetched the public crawler policy and dated
  HTML page successfully, matched both games and stored two immutable report
  revisions. Zero source games were unmatched.
- Saved source reports: Minnesota — Jesper Wallstedt; Columbus — Cam Talbot;
  Calgary — Devin Cooley; Carolina — Brandon Bussi. Daily Faceoff labeled all
  four confirmed, and all four matched unambiguous saved NHL player IDs. These
  are source-reported labels, not new manual confirmations or approved plays.
- Both games had started before this first observation. The reports are
  review-only, and no report was backdated to a pregame decision. The scheduler
  remains idle for the rest of tonight unless explicitly checked; ordinary
  collection resumes only within the next day's upcoming-game window.
- The first successful check consumed **2 request reservations** and **22,766
  source-body bytes** after the unused reservation was released. The saved
  October Odds API allowance remained **12 credits**. No paid odds refresh or
  AI generation was issued. No service error logs appeared in the checked
  post-release window.
- The actual components were inspected in an isolated, noninteractive layout
  preview using the saved production test facts. This confirms layout and
  Pacific deadline formatting. Authenticated visual verification on the live
  dashboard remains pending the owner's sign-in; a preview is not that check.

One successful collection establishes cloud reachability for this route at
that time. The remaining pilot checks are repeated pregame coverage, changes
from expected to confirmed, conflicts/retractions, observation latency and
multi-day failure behavior. The test expires automatically; it does not extend
itself. Source-report storage never makes an unvalidated prediction actionable.

## Owner actions

**Urgent:** sign in to the dashboard when requested so the live interface can be
checked. No API key, subscription or provider purchase is needed for this pilot.

**Can Get To:** send the prepared Daily Faceoff enquiry asking about supported
access, factual-status caching, research/model use and any published limits or
pricing. Reuse the contact text in NHL_STARTER_AND_SOURCE_RELEASE_2026-10-16.md.
