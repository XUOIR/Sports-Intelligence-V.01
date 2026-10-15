# NHL lineup sources: cost and feasibility review

Reviewed October 15, 2026. Active project: XUOIR/Sports-Intelligence-V.01. This review supplements the earlier provider research; it does not replace the current architecture.

Public provider documentation, published schemas and pricing were examined. No new accounts, trials, subscriptions, paid sports requests, odds refreshes or AI generations were started. No deployment, spending cap or application code was changed. Documentation establishes a candidate's stated capabilities; it does not establish measured live coverage or latency.

## Decision

**No permanently free, supported automatic feed was established that supplies all the missing NHL pregame evidence.** This is a result of the sources reviewed, not a claim that no such service could exist.

The strongest documented automatic fit is **SportsDataIO**, followed by **RotoWire's licensed feeds**. Neither publishes a verified price for our required NHL-only package. **Left Wing Lock's Personal API** is the most relevant narrowly scoped quote to obtain, but its public page does not establish the complete injury/confirmation/timestamp contract.

The immediately usable no-subscription route is **human verification of original reports**, using Daily Faceoff and team/reporter announcements for discovery. Left Wing Lock also offers inexpensive human-facing tools. Neither route should be presented as automatic ingestion.

The owner's subsequent question about a different approach is addressed in [the staged-model proposal](NHL_STAGED_MODEL_PROPOSAL_2026-10-15.md). A separately validated model designed for the information we can reliably obtain could remove lineup confirmation as a universal forecast dependency. That proposal does not alter or approve the existing goalie-dependent model.

**Subsequent interview/experiment update:** the owner accepted expected goalies for the first-release design and authorized an isolated team-model experiment. The [completed benchmark](NHL_TEAM_MODEL_EXPERIMENT_RESULTS_2026-10-15.md) establishes a free-data starting point, not a sportsbook edge or live approval. This provider comparison still describes the stronger pregame-reporting contract; its missing free complete feed does not prevent team-only research.

Official X ingestion could be inexpensive and fast, but it is a custom engineering route with unmeasured coverage. A low post-reading bill does not establish that it will capture every important announcement. Do not buy unrelated scoreboard APIs to solve this gap.

## What would actually close the gap?

Our missing data is not simply a list of registered goalies or the goalie who eventually played. A usable source needs:

1. A named goalie tied to the correct fixture **before puck drop**, with expected/probable separated from confirmed.
2. Timely injury, scratch and line-combination updates, where those are required inputs. NHL line combinations differ from the first line that actually takes the ice.
3. Distinguishable publication, provider-update, observation and re-verification times; attribution or an agreed provider confirmation policy; corrections and retractions.
4. Adequate NHL coverage, appropriate private analytics/storage rights, explicit quotas and bounded billing.
5. A usable delivery schedule relative to our forecast checkpoint, rather than a vague claim of real-time scores.

The existing model contract freezes inputs at T−30 minutes. A report first received at T−20 cannot be inserted into that earlier snapshot. A still-valid morning announcement must retain its original timestamp; any later check must be recorded honestly as re-verification. No vendor can force a team to announce before our checkpoint. A separately designed and validated later-checkpoint model is possible, but is not part of this research change.

There are also independent model tasks: reproducible factors, genuinely chronological evaluation, correctly matched current PlayNow prices, saved forecasts and outcomes. Buying a feed does not validate win probabilities. Historical actual starters do not establish what was known before each historical game.

## Ranked automatic-feed shortlist

Ranking is by documented fit for the missing inputs, not by a guessed price. These are procurement candidates, not approved integrations.

| Rank | Option | Evidence relevant to our gap | Cost / access | Remaining qualification |
| --- | --- | --- | --- | --- |
| 1 | [SportsDataIO NHL](https://sportsdata.io/developers/api-documentation/nhl) | Dedicated pregame projected/confirmed goalie endpoint, plus injuries and line combinations. | Live production package: **quote required**. No verified inexpensive starter-only price. | Real NHL sample, original confirmation/update semantics, retention rights, correction behavior and live coverage test. |
| 2 | [RotoWire licensed feeds](https://www.rotowire.com/partner/) | NHL news, injuries and expected/confirmed lineup coverage. | **Quote required**; line-combination detail can be an additional product. | NHL-specific package/sample, source times, revisions and allowed analytics/AI use in the agreement. |
| 3 | [Left Wing Lock Personal API](https://leftwinglock.com/api/) | Advertises goalies, lines and stats for a single private user, with customizable update intervals. | **Quote required**; monthly/yearly packages. | Confirm injury coverage, actual confirmation fields, report times, update frequency and price. Public documentation is not sufficient to approve it yet. |

**Why SportsDataIO leads:** its [data dictionary](https://sportsdata.io/developers/data-dictionary/nhl) explicitly defines `Goaltender.Confirmed`. The documented endpoint is `GET /v3/nhl/projections/json/StartingGoaltendersByDate/{date}`, with a suggested three-minute call interval. Its [workflow guide](https://sportsdata.io/developers/workflow-guide/nhl) describes confirmations shortly after announcements, but that is a provider statement, not our timing measurement. It also says historical line combinations are unavailable and does not supply the first line to take the ice. A current feed alone therefore does not supply a point-in-time historical validation archive.

**Why use a licensed RotoWire feed rather than scrape it:** the [general API guide](https://rotowire.readme.io/docs/rotowire-general-guide) distinguishes lineup/depth-chart products and additional NHL combinations. Its [quick start](https://rotowire.readme.io/docs/quick-start) recommends five-minute lineup checks near game time; this is a client schedule, not a guaranteed editorial delay. Its [terms](https://www.rotowire.com/termsandconditions.php), Articles VI–VII, require authorization for automated collection and relevant AI/model uses. A consumer login does not establish those rights.

**Why ask Left Wing Lock first when controlling cost:** it explicitly offers a private single-user API, matching our present deployment more closely than a large distribution contract. However, the public API prices are placeholders, not actual dollar amounts. An API quote and schema/sample are necessary; inexpensive consumer access is not evidence of an inexpensive API.

No numerical monthly ordering between these three can be substantiated without quotes. There is no basis to invent either a $20 or a $5,000 price.

## Free and inexpensive routes

| Route | Incremental data cost | What it can do | What it cannot establish yet |
| --- | --- | --- | --- |
| Original team/reporter statements, discovered through [Daily Faceoff](https://www.dailyfaceoff.com/starting-goalies), then entered by a person | **$0 subscription**; human time required | Record genuine confirmations with the source URL, actual observation time and later corrections. | No verified supported free DFO API, automation permission or complete coverage/SLA. |
| [Left Wing Lock Season Pass](https://leftwinglock.com/seasonpass/) plus manual entry | Advertised **$7.99/year upfront**, approximately $0.67/month equivalent; page does not identify currency | Human-facing goalie confirmations, game-day combinations, player news and injury tracker. | Explicitly excludes API access. Checkout currency/tax must be checked. |
| Official [X API](https://docs.x.com/x-api/getting-started/pricing) plus our own extraction/review | Usage-based; examples below | Ingest original reporter/team posts through server-side filters. | Complete all-team coverage, ambiguity handling and total monthly volume have not been measured. |
| [MySportsFeeds](https://www.mysportsfeeds.com/feed-pricing/) | Personal NHL **from CAD $5/month**, but that is CORE, non-live; DETAILS and faster access cost extra | Possible inexpensive source of fixture lineups/injuries. | Required total price and true pregame expected/confirmed goalie semantics are unverified. The $5 headline is not our package price. |
| [FantasyPros personal API](https://www.fantasypros.com/api-data/) | HOF from **US$8.99/month equivalent billed annually: $107.88/year** | Licensed personal news/injury access advertised for NHL and other supported sports. | No verified complete NHL confirmed-goalie/line-combination endpoint or coverage. It is a supplementary lead, not a qualified replacement. |

FantasyPros [subscription pricing](https://support.fantasypros.com/hc/en-us/articles/25996886459931-How-much-do-your-premium-subscriptions-cost-What-plans-do-you-offer) lists HOF month-to-month at $22.99. Its free API tier is sample-data prototyping, not unrestricted live production. Its public [API documentation](https://api.fantasypros.com/public/v2/docs/) lists NHL news/injuries. However, linked [API terms](https://api.fantasypros.com/public/v2/terms-of-use) are dated 2020 and describe 100 calls/day, whereas current marketing promises higher paid limits without a number. Obtain the actual production allowance and applicable license before paying.

### X cost model and practical limitations

X lists **US$0.005 per returned post**. For a 30-day month, the following is arithmetic, not a coverage forecast:

| Average returned posts/day | Monthly post reads | Post-reading charge |
| ---: | ---: | ---: |
| 20 | 600 | $3.00 |
| 30 | 900 | $4.50 |
| 40 | 1,200 | $6.00 |
| 60 | 1,800 | $9.00 |
| 100 | 3,000 | $15.00 |

User lookups and other resources can add charges. Configure the provider billing limit and disable automatic recharge. The documented daily duplicate protection is a soft guarantee, so local safeguards must not assume repeated reads are always free. OpenRouter funds do not pay X bills. These figures exclude AI extraction and existing hosting.

[Filtered Stream documentation](https://docs.x.com/x-api/posts/filtered-stream/introduction) advertises approximately 4–5 seconds P99 delivery latency. That measures delivery after a matching post exists, not time until a team announces or a reporter publishes. Access requires a developer account/app and credentials; no access was provisioned here.

Filter upstream by approved reporter/team accounts and relevant terms. Collecting all their posts and filtering locally still pays for returned content. Use deterministic parsing where reliable, send ambiguous cases to a person, and treat any model-produced extraction as a candidate record. An LLM cannot turn a probable report into a confirmed fact or retrieve an announcement it cannot access.

An all-team injury/lineup stream could exceed the 20–40 posts/day examples. Therefore **X has a plausible low running cost, not a demonstrated $3–$7 complete solution**. A cap can stop spending, but then missed coverage must be visible and verification must stay blocked.

## Candidates that do not presently qualify

These findings explain why a cheaper headline is not necessarily a solution. They are not a recommendation to purchase or start testing each service.

| Provider | Relevant cost, where established | Specific issue |
| --- | --- | --- |
| [BALLDONTLIE NHL](https://nhl.balldontlie.io/) | ALL-STAR $9.99/month; injuries require GOAT $39.99/month | NHL is supported, but the published NHL API/spec does not document a pregame confirmed-goalie/line-combination endpoint. Two $9.99 subscriptions would not establish the missing evidence. |
| [BetsAPI](https://betsapi.com/mm/pricing_table) | Hockey advertised $10/month | Its documented [event-lineup endpoint](https://betsapi.com/docs/events/lineup.html) is soccer-only. NHL scores/odds are not NHL starter confirmation. |
| [SportsFBI](https://sportsfbi.com/api-docs) | No purchase needed to establish this mismatch | Its goalie documentation explicitly derives confirmation from game boxscores and sets `pregame_confirmation: false`. Expected goalies are inferred. |
| [KingsPlaybook](https://kingsplaybookai-production.up.railway.app/devs) | Advertises free 100 requests/day | Both linked public contracts, `https://api.kingsplaybook.org/openapi.json` and `/llms.txt`, returned HTTP 404 during bounded checks. Actual NHL semantics, access and rights remain unverified. |
| [Big Balls Sports Data](https://bigballsdata.com/coverage) | Free tier advertised | NHL lineup coverage is marked coming soon. Current injuries do not supply confirmed pregame goalies. |
| [Highlightly NHL](https://highlightly.net/nhl-api/documentation/lineups/) | Earlier pricing review: free 100/day; paid plans available | Published lineup fields include player position and scratch status, but no documented confirmed-starting-goalie field. Examples are schemas, not measured coverage. |
| [Fantasy × AI](https://docs.fantasyxai.io/) | Price not relevant until the data gap is resolved | Documents probable goalies and lines derived from the last completed game; those are not confirmed day-of-game evidence. |
| [PuckAPI](https://puckapi.com/for/bettors) | Advertises 500 initial free credits; monthly renewal not established | Describes goalie research derived from played-game data, not tonight's pregame confirmations. Historical odds also do not replace current PlayNow prices. |
| [Statorium NHL](https://statorium.com/ice-hockey-api/nhl-api) | $19/month next-day scores; $49 live scores; $99 advanced package advertised | The inexpensive tiers do not close the gap; actual advance goalie-confirmation semantics are not established for the higher package either. |
| [Goalserve hockey](https://goalserve.com/en/sport-data-feeds/ice-hockey-api/prices) | NHL live statistics advertised $200 month-to-month | Rosters/injuries/statistics coverage is not proof of a pregame confirmed-goalie contract. Needs a concrete sample before it merits the cost. |
| [Sportradar NHL](https://developer.sportradar.com/ice-hockey/reference/nhl-overview) | Production quote required | Strong official statistics infrastructure, but this review did not establish the required advance-confirmation fields/timing. A game-summary starter flag is insufficient. |
| [Rolling Insights](https://rolling-insights.com/datafeeds/price-plans) | Pregame plan advertised $1,200/year, or $100/month equivalent | Depth charts and injuries alone do not establish a genuine goalie-confirmation feed. |
| [API-Sports hockey](https://api-sports.io/documentation/hockey/v1) and [SportsBlaze rosters](https://docs.sportsblaze.com/nhl/core_endpoints/team_rosters/) | Not qualified for a price comparison of the missing inputs | No verified advance confirmed-goalie contract established. Fast roster updates cannot substitute for fixture-specific starter announcements. |

The official NHL endpoints, their Python wrappers and MCP interfaces remain useful for the statistics they actually expose. Wrapping an existing source in another API or an LLM does not add pregame reporting coverage.

## Cost-controlled qualification before integration

The next procurement step is a written NHL-only package description/sample from the three shortlisted feeds. No messages have been sent to providers. Ask for:

- All 32 teams, projected versus confirmed starting goalies, injuries/scratches, EV/PP combinations and exact endpoint entitlements.
- A real NHL pregame response, field definitions, ID mapping, source/publication/update times, late-change/retraction behavior and a written description of confirmation policy.
- Published-to-feed delay distribution, polling/push options, daily/monthly limits, batch size/pagination, caching expectations and whether failures consume quota.
- Monthly total, setup charges, minimum term, currency/tax, overages, cancellation and a hard spending limit. Exclude duplicate odds/scores and unrelated sports from the quote.
- Permission for this private dashboard, retained evidence, historical evaluation and any external model processing. Future public or subscription distribution needs its own rights.
- Whether historical records preserve original pregame revisions/times or merely today's corrected/final values. Do not assume a historical feed is point-in-time evidence.

A bounded comparison should measure coverage at morning skate, T−60, T−30 and warmups; first publication versus first receipt; false confirmations; missed/retracted reports; and actual cost. Include a busy slate and a late-change case. An initial sample can reject a bad fit but cannot prove full-season reliability. Start in observation mode, with no automated plays and no paid AI generation required for qualification. Account creation, paid access or a paid pilot would need a concrete scoped decision first.

For polling arithmetic, one shared request every 30 seconds for eight hours is 960/day; every minute is 480; every three minutes is 160; every five minutes is 96. Per-team requests, pagination, injuries and retries add to that. A 100/day allowance is not a 30-second live feed. Browser sessions must read a shared server cache, not each poll the provider.

Preserve durable admission limits, concurrent-request protection, response caching, failure cooldowns, bounded retries, visible stale/error states and provider reconciliation. New source failures must never trigger paid odds refreshes or AI fallbacks. No existing spending limit was raised by this review.

## Recommended sequence for this project

1. Continue the existing official NHL/MoneyPuck/PlayNow stack and the model work. Use clearly labeled provisional goalies separately from source-confirmed evidence.
2. Use original-source manual confirmation as the immediate bridge. Optional inexpensive human-facing LWL tools can reduce searching, but are not an API integration.
3. Obtain LWL Personal API, SportsDataIO and RotoWire NHL-only quotes/specimens before selecting an automatic provider. SportsDataIO is the best documented technical choice; LWL is the most targeted private-use pricing inquiry.
4. Consider official X only as a bounded alternative if feed quotes are unsuitable. Establish useful-post volume and all-team coverage before claiming it fits the budget.
5. Release verified predictions only when both data verification and genuine model validation pass. Otherwise show the precise missing evidence, rather than fabricated probabilities or generic HOLD labels.

## Optional independent-research prompt

Use the following to obtain a second opinion without transferring credentials or restarting architecture planning:

> Research current production-viable sources for NHL pregame starting-goalie confirmation, injuries/scratches and game-day EV/PP line combinations for a single-user private FastAPI/Next.js dashboard. We already have official NHL scores/history, MoneyPuck xG/GSAx and protected PlayNow odds; another scoreboard is not the missing piece. Prioritize genuinely free supported automation, then inexpensive personal APIs, then quote-based feeds. Evaluate SportsDataIO, licensed RotoWire, Left Wing Lock Personal API and official X ingestion, and find better alternatives if supported by evidence. For each option, cite primary documentation, an actual endpoint/schema, expected versus confirmed semantics, original announcement/update timestamps, correction behavior, all-team coverage, latency (measured versus advertised), production license, retention/model-use rights, quotas, failure billing, overages and total monthly/upfront cost/currency. Do not treat a consumer subscription as API permission, a temporary trial/sample tier as free production, a postgame starter flag as pregame confirmation, or next-day/historical data as a live source. Our present forecast checkpoint is T−30; no provider can manufacture an earlier team announcement. Historical validation needs point-in-time pregame evidence, not final game records. X post charges and AI extraction charges must be separate; do not assume a few posts/day is enough. State all unknowns and reject products that cannot actually close the gap. Rank complete documented candidates separately from unverified leads. Do not invent quote prices or buy/activate anything. Provide exact vendor questions and a bounded qualification plan before recommending integration.
