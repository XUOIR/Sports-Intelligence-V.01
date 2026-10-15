# NHL Forward Paper Candidate — October 15, 2026

The owner authorized correcting team continuity and preparing genuine forward
paper tracking after the first historical experiment. This implements the
collection phase of the proposed paper protocol. It does not approve the model
for real-money recommendations. The remaining statistical release criteria in
the protocol remain a separate evidence-review decision.

## Frozen candidate

`backend/app/data/nhl-paper-v2.json` and its SHA-256 file contain the small fitted
candidate, seed team states, admitted official source hashes and collection
rules. The version includes the bundle hash. The inference/collection source
hashes are also frozen; a logic change requires refreezing before collection,
which produces a separate candidate/cohort. NumPy is an offline training
dependency only. Production inference uses the standard library.

Utah team IDs 59 and 68 share official franchise 40 and now share one history.
Arizona is not merged into Utah. The original v1 experiment and results are
unchanged. Actual expansion teams still require ten real previous games.

The selected settings remain K=10, home advantage=35, season carry=0.75 and
ridge penalty=1, with rating/rest/back-to-back features. Fit seasons are
2018–19 through 2024–25 (8,449 games); calibration is 2025–26 (1,312 games).
The examined test seasons are now fitting/calibration data, **not a new
untouched historical test**. Only future observations count as new evidence.

## Collection and spending

- A one-minute scheduler task reads saved data; authenticated UI reads cannot
  initiate collection or provider requests.
- Upcoming regular-season fixtures within 48 hours are enrolled. Probabilities
  freeze on match day before puck drop, using only prior Eastern calendar-date
  results actually observed before capture. Missing inputs retain a visible
  exclusion reason and can become eligible later, at the real later timestamp.
- One complete current-season official NHL refresh is cached per Eastern date
  after 06:00 ET. There are at most two admitted batches per Pacific day,
  separated by six hours; HTTP attempts also consume the existing 300/day NHL
  request allowance and inherit its response-size, retry and circuit limits.
  Pagination, unknown teams, unresolved/nonstandard previous-day fixtures or
  changed schemas block inference. A failed cache never becomes current.
- No extra Odds API calls or OpenRouter generations are made. Existing manual
  odds limits and the configured US$3 monthly AI cap remain unchanged.
- Expected/unknown goalies are allowed in this **team-only paper** contract.
  Their context is saved honestly. No goalie adjustment or confirmation is
  invented; the existing production model's stricter gates remain unchanged.

## Prices, paper decisions and results

The collector preserves price observations, including missing/stale-price
statuses. A matched two-way PlayNow/BCLC final-winner h2h pair must use the same
book and source timestamp, have no numerical line, and be at most five minutes
old. Future timestamps are rejected. Exact team selections are required.

Signed edge = model selection probability − 1 / offered decimal odds. The first
valid observation exceeding or equalling +3 percentage points can create one
flat simulated-unit position per fixture/candidate. A valid observation with no
edge remains a no-bet. Later prices cannot overwrite the forecast or position.
The first valid paired price is retained for paired Brier comparisons against
the margin-adjusted market; paper returns use the actually recorded offer.

Settlement reads the existing reconciled official result. Changed starts/team
identities and explicitly postponed/cancelled score-cache records void the
paper cohort entry; unresolved games remain pending. Voids are excluded from
settled-position ROI. Result corrections require an explicit audited workflow;
the collector does not silently rewrite settled evidence.

Private `paper_forecasts`, `paper_price_observations` and `paper_input_archives` tables are migrated
through the existing Alembic deployment workflow. RLS is enabled and access is
revoked from Supabase's public client roles. Existing seven-day quote/evidence
retention does not delete paper provenance. Immutable normalized input archives
preserve each daily season snapshot for replay without duplicating it per game.
This candidate is limited to 2026–27; another season requires a new candidate
with complete intervening history. No writes target Account,
PersonalBet, Snapshot or ModelValidation.

## Dashboard and remaining evidence

Model Performance gains an explicitly labelled NHL Paper Research section with
input coverage, paired prices, paper positions, simulated ROI, probability
scores and per-game history. Existing model results and the actual Bankroll
remain separate. The displayed saved-price edges are historical observations;
they are not advertised as current offers or verified picks.

The first operational review requires at least 14 calendar days and 100 resolved
forecast/price pairs. No early ROI or win-rate chart establishes profitability.
The later 60-day/300-position/eight-week review floors in the protocol are not
sufficient on their own. Precise release-level uncertainty, calibration and
stability criteria still require a prospective review plan before that study;
no code automatically approves or enables this candidate.

Deployment must follow local tests and visual review. Do not call paid APIs
merely to populate the paper ledger during testing. If no fresh prices are
available at rollout, that is an honest collection gap, not a reason to spend
credits without an actual odds-refresh request.

## Verification before deployment

The free-source integration probe on October 15 returned 1,344 scheduled
2026–27 regular-season games and 107 completed prior-date games. Validation and
the immutable input archive succeeded. This was one successful free NHL request,
using an isolated persistent ledger; no Odds API or OpenRouter call was made.
The probe can be repeated against the same ledger without another successful
request on the same date:

```
cd backend
..\.venv\Scripts\python.exe -m research.check_paper_source --ledger ../artifacts/nhl-forward-paper-qa/source-check.sqlite3
```

The final candidate SHA-256 is
`405edb95e305256297af50fe6f77efdcabf3949db9587edb212f486743afeb11`.
The private production database migration and live scheduler/price collection
must still be verified at deployment. Local SQLite migration checks and
PostgreSQL DDL compilation do not substitute for that live verification.
