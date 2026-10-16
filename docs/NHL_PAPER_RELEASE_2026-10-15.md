# NHL paper-only release — October 15, 2026

The owner explicitly selected Terry's Render workspace for this release. Only
`XUOIR/Sports-Intelligence-V.01` and its existing two services were used. No
service, subscription, secret, paid refresh allowance or AI budget was added or
changed. The existing Blueprint and Alembic migration workflow were preserved.

## Deployed services

| Service | Code | Render deployment | Became live (Pacific) |
| --- | --- | --- | --- |
| Backend | `c1c096eb58b4c6b2ad75c5e5f666d5d8a4957737` | `dep-db8mrgavcj2c73b1no6g` | October 15, 17:21:01 |
| Dashboard | `225d4d223f68dc1b9bf302bd9837563325461cba` | `dep-db8mpvnavr4c73dhbl20` | October 15, 17:18:10 |

Both releases were verified against Render's actual deployment records, rather
than inferred from a Git push. Auto-deploy was off and each deployment was
explicitly triggered. The first backend deployment of `225d4d2` completed the
schema migration; its deployment was `dep-db8mp6navr4c73dh60g0`, live at 17:16:17.

## Database and access verification

Supabase reports Alembic revision `0003`. The `paper_forecasts`,
`paper_price_observations` and `paper_input_archives` tables all have RLS enabled;
neither `anon` nor `authenticated` has SELECT privileges. Backend health/live and
health/ready returned HTTP 200. Anonymous backend `/performance` and frontend
`/api/data/performance` requests returned HTTP 401. No model approval or fake
wager was inserted for deployment testing.

The security advisor's no-policy INFO findings are expected for these
backend-only tables. It also reports pre-existing EXECUTE-grant warnings for
`public.rls_auto_enable()`. Inspection identifies this as the automatic RLS
event-trigger function with a fixed `pg_catalog` search path; this release did
not create or alter it. See the advisor's
[public function privilege guidance](https://supabase.com/docs/guides/database/database-linter?lint=0028_anon_security_definer_function_executable)
for a separate permissions review. No public table access was granted.

## Real collection and transfer safeguard

The first scheduler run admitted one free NHL season-history batch: 1,344
scheduled games and 107 completed games on dates before October 15. It wrote
the immutable normalized input archive and captured two genuine pregame
forecasts: Utah at Edmonton, and Calgary at Vegas. Existing PlayNow prices were
expired, so both price observations were stored as `STALE_PRICES`; no paper
position was manufactured. Thirteen future-day fixtures were enrolled with an
explicit match-day waiting reason.

The live check found unnecessary history/archive reads for future-day fixtures.
The final backend checks that calendar condition before those full reads. The
new regression test asserts that neither history nor archive SELECT occurs for
a future fixture. All fitted coefficients, seed states, inputs and selection
rules are byte-equivalent as parsed JSON before and after this optimization.

Because collection code is frozen, the fix received candidate identity
`nhl-team-paper-v2-617e76ac7eda`. The first two forecasts remain under
`nhl-team-paper-v2-405edb95e305`; their records were not overwritten, deleted or
backdated. Cohorts must be assessed separately. The earlier two records had no
paper positions or real stakes.

At 17:23:32 Pacific, the new active collector was verified in Supabase with
15 enrolled fixtures, two captured forecasts, 13 match-day waiting entries and
no collection error. The new forecasts were actually saved at 17:23:30 and
17:23:31, before their 18:00 and 19:00 starts. Edmonton's home probability was
0.5234358752 and Vegas's was 0.5705150164, exactly matching the earlier candidate.
Both new price observations remained `STALE_PRICES`, and no position was added.
The shared history batch count stayed at one across the rolling handoff.

## Spending and test evidence

The pre-release audit showed no paid provider calls on October 15 Pacific and
nine reserved Odds API credits for October. Post-deployment checks continued to
show zero new paid provider calls, one paper-history batch, CAD 1,100 initial
bankroll, zero recorded tickets and zero approved production models. The
existing US$3 monthly AI setting and manual odds safeguards were not changed.

Local checks: 241 backend tests, 22 offline/model-consistency tests, 23 frontend
tests, and the production frontend build/type checks passed. The new migration
was exercised locally and then verified against the actual Supabase revision
and table privileges after deployment. Tests used no paid odds or AI calls.

## Remaining verification and research limits

Authenticated live UI inspection is pending the owner's sign-in to the opened
dashboard tab; the previous eight-hour session expired. The local test-data
screenshot is not evidence of the live private panel. Once signed in, inspect
Model Performance's paper section, actual saved forecasts/prices and Bankroll,
then save a production screenshot without submitting a ticket or refreshing
paid providers merely for testing.

This is a forward paper collection release. Historical benchmark performance,
two live probabilities and an operationally healthy deployment do not establish
a sportsbook edge. Fresh paired PlayNow quotes and actual final results must
accumulate under the prospective protocol before any profitability claim or
real-money model approval.
