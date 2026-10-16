# Daily forecasts and manual goalie confirmation — October 16, 2026

## Daily Matchups

The overview now reads the existing authenticated `/performance?sport=NHL`
endpoint alongside its saved dashboard data. It shows a matching saved paper
forecast when the separate production-model probability is absent. Matching
requires the exact fixture ID, ordered teams and start instant, a finite binary
probability, and a genuine capture before puck drop and no later than now.
Voided records cannot populate the bars. Existing model output takes precedence.

Paper forecasts carry a visible research label, capture time, stated inputs and
favored team. The team-only candidate uses previous results, ratings, rest and
back-to-back scheduling; neither bookmaker prices nor the displayed xG/goalie
statistics enter that candidate. Market prices only supply break-even
probabilities for the separate signed-edge comparison.

The first frontend change, `f6b20f8`, deployed as
`dep-db9b5iijnfac73bkqfm0`. Authenticated production inspection confirmed
Colorado 58.1% / Pittsburgh 41.9%, saved-price edges -9.9 / +5.5 percentage
points, and the original 14:58 Pacific PlayNow timestamp labeled expired.
Boston 50.4% / Anaheim 49.6% also rendered correctly. xG shares, logos, theme,
source details and verification states were preserved. No forecast, position,
bankroll, model approval or spending limit was rewritten for this display.

Offered decimal odds now display two decimal places throughout Daily Matchups,
the match drawer, paper history and wager ledger. Computations and stored
prices retain their original precision.

## Manual confirmation workflow

The historical goalie dropdowns previously selected comparison statistics only.
After selecting a valid candidate from each team's own list, the new **Verify
Selected Goalies** action opens the existing evidence form with both names
prefilled. It does not mark either goalie confirmed. A separate **Confirm
Starting Goalies Manually** action supports names absent from the historical
comparison lists.

The goalie form requires a public evidence URL, actual source-recheck time,
both distinct names and an explicit confirmation checkbox. Original report
publication remains separate and optional. The existing server validates the
30-minute recheck window, upcoming fixture, HTTPS source and T−30 restrictions.
Saving refreshes the open drawer so confirmation and remaining checks are
visible. Pregame confirmation actions close when the game starts. The general
evidence form still permits explicit retraction and optional research factors.

Dropdown selection never sets a gate, computes new probabilities, approves the
paper model, refreshes odds or directly requests paid AI. Other market and
opposing-case review checkboxes remain unchecked unless explicitly reviewed.

## Actual remaining prerequisites

| Check | Working mechanism | Remaining requirement |
| --- | --- | --- |
| PlayNow price and edge | Matched two-way quotes, independent saved probabilities, signed break-even comparison | Saved 14:58 prices are expired; a new executable decision requires genuinely fresh prices. Manual refresh safeguards remain active. |
| Starting goalies | Source-backed confirmation endpoint, explicit save flow, expiry and immutable evidence | Both actual starters must be checked against a public source. No production confirmation was fabricated for testing. |
| Form and rest | Official prior-game evidence and frozen normalization | Eligible source evidence must be available at the exact T−30 anchor. Missing snapshots cannot be backfilled. |
| Advanced inputs | Daily bounded MoneyPuck import with source reconciliation | October 16's 09:00 import failed; last cache remains October 15, verified through October 14. This attempt stays consumed. |
| Model probability | Compatibility, historical partition, scoring and approval checks | Zero approved production models and zero usable advanced-model baselines were present in the audit. The four team-only paper forecasts remain a separate experiment. |
| Spread/total and opposing case | Existing explicit evidence-review fields and deterministic checks | Actual matching-market and opposing-evidence review is needed; selecting goalies does not assert these reviews. |
| Bankroll and overlap | Existing duplicate-ticket, exposure, stake and temporal checks | Evaluated against a qualified candidate and current prices. Actual bankroll remains separate from simulated units. |
| Map veto | Explicit NHL not-applicable state | No esports veto evidence is required for NHL. |
| Paid AI audit | Existing scheduler, durable evaluation identity, budget and failure latch | Runs only after all deterministic prerequisites pass. It can veto evidence; it cannot approve an unvalidated model or substitute for statistical testing. |

The prospective paper study continues under its frozen identity and original
research protocol. UI work does not satisfy the outstanding model-validation
study or establish a sportsbook edge.

## Statistics failure diagnosis

The morning failure stored only `ValueError`, with no stage or safe reason;
available logs did not reveal its cause. Two header-only diagnostic requests
confirmed the team and goalie source URLs currently return HTTP 200 with
appropriate encoding/publication metadata. These observations cannot explain
the earlier response or establish that the full files reconcile. No second
large download or import was attempted.

Future failed imports now record the download/verification/validation/save
stage and an allowlisted fixed reason. Unexpected exception text, upstream
bodies and URLs are not exposed. Settings shows these diagnostics while
retaining the cache's original date. Byte reservations, one daily attempt,
timeouts, validation and no-retry behavior are unchanged. No new model cohort
is needed: frozen paper inference/collection source files are unchanged.

## Tests and verification boundaries

All 242 backend tests and 29 frontend tests passed; the production frontend
build and type checks passed. Coverage includes strict evidence handling,
same-candidate forecast binding, probability independence from prices,
expired prices, no paid retries, preserved previous statistics and redacted
import diagnostics. Backend tests must run from `backend/` to use its real
`main.py`; a repository-root run resolved the unrelated root entry point and
was corrected before verification.

A disposable local fixture verified that the save is blocked without the
explicit checkbox, both selected names arrive in the request, publication is
not invented, unrelated review flags remain false, and the drawer refreshes
after saving. It had no live database, provider keys or scheduler. These QA
names were never written to production. Actual production screenshots are
kept separately from the synthetic local preview under ignored
`artifacts/daily-matchups-2026-10-16/`.

No paid odds batch or AI generation was sent during this implementation.
The existing three-credit batch is still the only metered provider call today.
The configured US$3 monthly AI ceiling remains unchanged.

## Final live verification

Runtime commit `4ddbc87495d6e5b75fa4538f81b8e993bca92401` is live on both
services. Backend deploy `dep-db9bf167bikc73fdioqg` finished at 16:47:57 Pacific;
frontend deploy `dep-db9bf267bikc73fdirc0` finished at 16:48:25 Pacific.
Backend readiness/liveness and the frontend login page returned HTTP 200.
No error-level app logs were returned in the post-deploy inspection window.

A full production reload showed 2.75 / 1.47 in Colorado's card, 1.90 / 1.90 in
Anaheim's card, both saved forecasts and all four signed price edges. The
original 14:58 prices remained expired. The live dropdowns enabled **Verify
Selected Goalies** only after both sides were selected, and opened the form
with the matching names. Its source URL was blank and all verification
checkboxes were unchecked. The form was canceled without submission; these
UI selections were not asserted as the actual starters.

The real Colorado detail panel reported available official schedule, standings
and form; stale MoneyPuck statistics; a 17:30 Pacific T−30 checkpoint; and no
compatible approved NHL model. Those are actual remaining prerequisites.
Paper probabilities did not populate the separate validated-model field.

At 16:48:57 Pacific the production audit still showed one metered provider call
today (three odds credits), one consumed MoneyPuck import, zero new starter
evidence, CAD 1,100 initial bankroll and zero actual tickets. The paper collector
was healthy on its original candidate, with four forecasts, two resolved
forecasts and one simulated position. Restarting the backend did not duplicate
the position or repeat the failed statistics import.

The final production card screenshot is
`artifacts/daily-matchups-2026-10-16/daily-matchups-live.jpg`; the unsent
confirmation form is `goalie-confirmation-live-not-submitted.jpg`. The isolated
QA tab and temporary local server were closed after testing.
