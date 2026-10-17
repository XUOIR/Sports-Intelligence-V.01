# NHL starter workflow and data access release — October 16, 2026

## Delivered behavior

Starting Goalies has two team-specific dropdowns and one Confirm Selection button.
No URL, report-time field, checkbox or second form is required in this path. The
app saves the authenticated owner's attestation and real server time, labels it
Manually Confirmed, and retains immutable evidence/audit records. Historical
goalie comparison stays in NHL Matchup Statistics; workload details remain in an
expandable section.

The shortlist uses recent saved NHL comparison candidates and identified goalies
in current saved team history. It is not a verified active roster or injury feed.
The server rejects wrong-team/duplicate IDs, expired/changed lists, reschedules,
and post-start submissions. Identical retries do not duplicate evidence. Saving
does not refresh odds or call AI. Manual confirmation expires after 30 minutes.

A manual attestation is distinct from an independently checked public report.
It cannot rewrite frozen inputs or renew an old market/opposing-case review.
The normalized-input contract is version 3 to identify this evidence mode; its
baseline digest isolates older approvals. No production model was approved.
The frozen team-only paper candidate, parameters and prospective cohort remain
unchanged. Insufficient goalie samples and genuine model validation still block
production recommendations.

## Daily Faceoff

The [starting-goalies page](https://www.dailyfaceoff.com/starting-goalies) shows
status, displayed update time and reporter links. It is linked as a manual
reference. Its [crawler rules](https://www.dailyfaceoff.com/robots.txt) allow public
pages and disallow /api/ and /cms/. This is not a reuse licence or supported-feed
guarantee. No documented public API, published rate allowance or ongoing reuse
permission was verified. No scraper, hidden API, X ingestion or AI web extraction
was enabled. Their fantasy goalie rankings incorporate sportsbook odds; do not
use those rankings as independent forecast inputs.

Prepared text for [Contact Us](https://www.dailyfaceoff.com/contact-us), not sent:

> I run a private, password-protected NHL statistics and betting-research dashboard.
> Is there a supported API/feed for starting-goalie names, team/game identifiers,
> expected/confirmed status, update time and original reporter link? If not, may
> we cache those factual fields from the public starting-goalies page at a modest
> agreed interval, with attribution, no article text/images/raw redistribution,
> and no access to /api/ or /cms/? Please confirm caching, historical research/model
> use, request limits and cost. We can stop on access failures and prefer a
> supported feed to fragile page parsing.

An HTML adapter is technically possible. Before activation it needs a bounded
real-payload test, game/date/team/ID checks, explicit expected/confirmed states,
schema-failure stops, daily and response-size caps, conditional caching, and real
observation times. An old report must never become backdated pregame evidence.

## Download reliability

The next already-permitted scheduled import/probe saves safe response metadata:
status, server family, response type, reported challenge, known public redirect
destination. Credentials, unknown/private paths, query strings, cookies and bodies
are withheld. Redirects are never followed. No additional request or retry was
introduced. Existing daily/transfer caps remain unchanged.

Settings separates manual recovery from automatic daily imports. Three adjacent
successful scheduled days constitute an operational reliability check; manual
recovery cannot erase a scheduled failure or count toward it. This diagnostics
change does not itself fix upstream access. Today's admissions were not reset.

See the [MoneyPuck request](MONEYPUCK_ACCESS_REQUEST_2026-10-16.md) and
[ranked Plan B research](NHL_DATA_PLAN_B_2026-10-16.md).

## Validation

Backend tests cover authentication, save/replay, own-team IDs, stale lists,
reschedules, post-start rejection, frozen-input immutability, empty official
updates, manual normalization and independent review freshness. A disposable
Next.js → FastAPI API check passed login, origin rejection, save, reload and
retry without live credentials/database/provider calls. Frontend tests and
production build passed; offline paper consistency checks passed. The local
browser preview was blocked by the browser URL policy; no browser workaround
was attempted. The deployed HTTPS page is checked separately below.

CI now runs backend tests from backend/ to import the correct main module and
includes pinned offline consistency checks. No paid odds refresh or AI generation
was issued for this work. Live verification is recorded after deployment.

## Owner actions

**Urgent:** none for the paper-only workflow.

**Can Get To:** send the MoneyPuck request; optionally send the Daily Faceoff
enquiry. These unblock supported automatic-source decisions. The new manual
confirmation path does not depend on a provider reply.


## Live release verification

Code commit `6bc843b10bda95a3f0b440cb789552b12fb6d80b` was pushed to the active
repository. Both Render services report that exact commit live:

- Backend `dep-db9f1tfavr4c73dqt3mg`, live 2026-10-17 03:52:58 UTC.
- Dashboard `dep-db9f2b7btjjs73bg2hdg`, live 2026-10-17 03:54:25 UTC.
- Backend `/health/live` and `/health/ready`: HTTP 200.
- Final local checks: 276 backend tests, 29 frontend tests, two offline paper
  consistency tests, and Next.js production build passed. GitHub's combined-status
  connector returned no statuses; no claim of a passing GitHub Actions run is made.
- Database audit after deployment: Odds API 3 credits today / 12 this month;
  no daily/monthly AI reservations; MoneyPuck protected transfer 148,228,199 bytes
  with each October 16 import/probe/recovery admission still consumed. These are
  local counters, not a newly fetched provider invoice. Zero approved NHL models.
- The frozen current paper cohort remains four captured forecasts, two resolved,
  one paper position. Earlier candidate results are kept separate.

A separate score feed failure at 20:39 PT reported a schema validation error.
The existing free-provider 15-minute cooldown was preserved. Once it expired,
one bounded diagnostic read through the existing `nhl_scores` cap returned two
valid games and passed the parser. The public response is saved only in ignored
local QA artifacts. This did not use odds or AI credits; no parser rule was
weakened without a reproducible failing payload.


The normal scheduled score feed subsequently recovered at 20:54:57 PT with a
30-second interval and no parser relaxation or circuit reset. The refreshed live
site showed Pittsburgh–Colorado Final (2–5) and Boston–Anaheim still live. Original
prices retained their expired label. The transient failure remains recorded for
diagnosis; a different temporary response cannot be reconstructed from a later
successful one.
