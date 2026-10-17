# NHL source continuity and Plan B — October 16, 2026

## Decision

Keep the current frozen team-only paper experiment running. It uses official
prior-game results, ratings, rest and back-to-backs; MoneyPuck is not an input
to that candidate. Advanced-statistics continuity and confirmed starters are
separate jobs. No new source, signup, paid plan or API generation was activated
by this research. No source below is certified as a complete drop-in replacement
without testing its actual payload and permitted use.

## What MoneyPuck's rules actually establish

The [download page](https://moneypuck.com/data.htm) permits its listed data for
non-commercial use with attribution, requests contact for other uses, and warns
that unapproved scraping outside the listed downloads is blocked. Our importer
uses the linked team CSV and goalie ZIP, not an undocumented page scraper.
The page does not explicitly settle whether our particular private betting
research/model-development use and cloud automation are covered. Written
confirmation is the appropriate way to resolve that uncertainty. Publishing or
selling subscriptions later would require a fresh rights review.

MoneyPuck also publishes a [betting-information page](https://moneypuck.com/bet.htm).
That demonstrates betting content is part of its site; it is not a data licence.
A 302 and a 403 do not identify motive, prove a project-specific ban, or establish
that betting analysis caused the denial. Local recovery succeeded using the same
public files, but it does not establish reliable future cloud access. The prepared
request is in `MONEYPUCK_ACCESS_REQUEST_2026-10-16.md`.

## Ranked alternatives for our specific gaps

| Priority | Option | Published cost / allowance | Fit and unresolved checks |
|---|---|---|---|
| 1 — immediate continuity | Existing official-data team-only model | No new subscription; existing bounded NHL requests | Already generates genuine paper forecasts independently of MoneyPuck. Keeps research functioning; supplies no proprietary xG or GSAx. This is the verified operational fallback, not proof of profitability. |
| 2 — free API evaluation | PuckAPI | 500 free credits each signup-anniversary month; paid Starter $19/month for 10,000; wallet top-ups start at $5/2,000 credits | Documents independently computed team 5v5 xG, goalie GSAx and daily updates. Season aggregates/leaderboards do not demonstrate our required game-level, pregame-safe rolling history. Verify timestamps, full goalie coverage and data quality before integration. |
| 3 — paid API evaluation | Project 94 Hockey Pro | $19.99/month, 10,000 requests/day; annual $199, before tax | Documents advanced goalie fields, game/per-period logs and team totals. Public discovery returned current 2026–27 coverage and xG/saves-above-expected fields. Need actual paid payload tests, exact 5v5 versus generic even-strength definitions, refresh timing, goalie denominator/identity checks and retention permission. |
| 4 — inexpensive manual/export evaluation | Evolving-Hockey Pro | $9.99/month; $99.99/year | CSV downloads and game logs are advertised. No public supported ingestion API was established. Confirm automation, model-development use and private retention before treating the subscription as a pipeline. |
| 5 — exploratory only | Big Balls Sports Data | Free 250 requests/day, 500 with linked GitHub; paid products vary | Public NHL page marks player-stat datasets historical/not currently ingesting, last June 6, while other pages advertise newer goalie/xG capabilities. Current-season advanced freshness and consistent coverage must be demonstrated before adoption. |
| 6 — longer development route | Our own xG model from permitted NHL event data | No new advanced-statistics vendor fee; engineering, transfer and compute still have costs | Needs admitted shot history, shot-quality training, strength/empty-net handling, calibration, goalie attribution and chronological evaluation. An independent research project, not an instant replacement. |

PuckAPI sources: [pricing](https://puckapi.com/pricing),
[xG coverage and method](https://puckapi.com/data/expected-goals),
[terms](https://puckapi.com/terms),
[goalie endpoint](https://puckapi.com/docs/get-goalie-stats),
[player game logs](https://puckapi.com/docs/get-player-game-log),
[refresh changelog](https://puckapi.com/changelog).

Project 94 sources: [pricing, endpoint documentation and terms](https://project94hockey.com/),
[public season discovery](https://project94hockey.com/v1/seasons),
[public field discovery](https://project94hockey.com/v1/fields).
Two bounded, unauthenticated discovery reads returned HTTP 200 from the local
computer; no paid API data or Render reachability was tested. The licence allows
dashboard/derived analysis but requires deleting stored raw responses after paid
access ends unless separately agreed, which matters for reproducibility.

Evolving-Hockey sources: [subscriptions](https://evolving-hockey.com/subscribe/),
[feature map](https://evolving-hockey.com/site_map/),
[terms](https://evolving-hockey.com/tos/). Its published terms restrict commercial
reuse; a website subscription does not establish an automated-feed licence.

Big Balls sources: [NHL capability/freshness page](https://bigballsdata.com/nhl-api),
[changelog](https://bigballsdata.com/whats-new). The inconsistency is an explicit
reason to keep it out of production pending payload verification.

## PuckAPI budgeting trap to avoid

One daily standings call costs 2 credits; one goalie-leaderboard call costs 5.
At 31 days that is 217 credits, within 500. **It does not establish complete
coverage**: the goalie endpoint documents a maximum of 50 results, while our
current MoneyPuck file contains 65 goalies. Its default minimum is 10 games,
which would omit early-season starters; a successful test must explicitly set
and verify the appropriate minimum. No leaderboard offset is documented.

A conservative completeness strategy of one goalie call for each of 32 teams
plus one standings call daily costs (32×5+2)×31 = 5,022 credits. This is within
Starter's allowance but outside the free tier. The 500 free credits would leave
4,522 wallet credits, about $11.31 of wallet consumption at 400 credits/USD;
actual deposits are sold in stated increments. These are calculated scenarios,
not a usage guarantee or purchase recommendation. Extra pagination, historical
data, retries and new endpoints must be budgeted separately. Paid overage can
draw from a wallet; our own durable cap must stop calls first. We cannot assume
a vendor refund until it is actually reconciled.

The [team endpoint](https://puckapi.com/docs/get-team-stats) accepts team and
season, with no documented as-of-date filter. Its documentation example also
has counting totals that do not reconcile, so sample JSON must not be treated
as a validated payload. The game-log contract does not document per-game xG/GSAx.
The public goalie-doc refresh label and current changelog differ. These need
clarification; historic season totals cannot supply earlier pregame features.

## Daily Faceoff: a different, useful part of the solution

The [starting-goalie page](https://www.dailyfaceoff.com/starting-goalies) currently
lists four confirmed starters with displayed timestamps and named source links:

| October 16 matchup | Away starter | Home starter |
|---|---|---|
| Pittsburgh at Colorado | Arturs Silovs | Mackenzie Blackwood |
| Boston at Anaheim | Michael DiPietro | Lukas Dostal |

Displayed UTC times convert to 11:03, 09:25, 11:20 and 10:51 Pacific respectively.
These are page-displayed times; original beat-writer publication times require
checking the linked reports. Preserve report time separately from actual read
time, status, game/date and source URL. Do not retroactively fill a missed anchor.

Existing manual source-backed confirmation can use these reports. No scheduled
scraper or public supported API was established. Ask via the site's
[contact page](https://www.dailyfaceoff.com/contact-us) about permitted automated
access before designing unattended ingestion. A privacy policy alone does not
grant scraping permission. Starting identity does not replace historical GSAx.
Do not use their fantasy goalie rankings as odds-independent inputs: the page
states those rankings incorporate sportsbook odds.

## Options excluded or held back

- [Hockey Alchemy](https://www.hockeyalchemy.com/pricing): published API/bulk-export
  plans are explicitly not available yet; not an operational backup.
- Natural Stat Trick: a credible analytics lead, but supported access/terms were
  not verified from its primary site in this run. Third-party scrapers do not
  establish either access rights or production reliability.
- [HockeyViz](https://hockeyviz.com/subscribe): useful analytical subscriptions,
  but no verified machine-feed route for our full required schema was found.
- [SportsDataIO NHL dictionary](https://sportsdata.io/developers/data-dictionary/nhl):
  no expected-goals/GSAx field was verified; do not buy a general NHL feed on the
  assumption that it fills this advanced-statistics gap.
- [EliteProspects API terms](https://developer.eliteprospects.com/legal/terms):
  model/AI work and sports-betting uses require separate written agreements;
  unsuitable as a presumed plug-and-play research feed.
- Scraper services republishing MoneyPuck: not independent continuity and do not
  resolve permission questions. Not recommended as a way around denied access.

## Admission checklist for any replacement

Before activation, verify exactly one bounded sample per necessary endpoint,
current-season completeness, explicit source cutoff/last-completed-game date,
pregame-safe history, team and goalie IDs, strength states, minutes/denominators,
GSAx sign and scope, model/source versions, allowed caching/model use, and reliable
Render access. Track request identity and maximum charge before dispatch; stop
after uncertain failures. Do not add a wallet, renewal, paid subscription or
automatic fallback without a concrete approved allowance. Run prospective
comparisons under a separate candidate; keep the frozen paper cohort intact.

## Owner actions

**Urgent:** none required to keep the current official-data paper workflow running.

**Can Get To:** send the prepared MoneyPuck request. It unblocks a supported
advanced-statistics feed/access decision; there is no promise about response
time. Optional later action: create a free PuckAPI key if we choose the bounded
evaluation, or request a Project 94 sample before purchasing. Keep keys out of chat.
