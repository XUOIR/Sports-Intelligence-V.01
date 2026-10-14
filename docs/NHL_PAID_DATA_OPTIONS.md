# NHL data purchase shortlist

Reviewed October 13, 2026 for XUOIR/Sports-Intelligence-V.01. This is a research recommendation, not an authorization to subscribe. No provider accounts, paid calls, subscriptions, or production configuration were changed.

## Purchase recommendation

For the full preflight results, see [NHL_PROVIDER_PREFLIGHT.md](NHL_PROVIDER_PREFLIGHT.md). The owner subsequently excluded Sportlogiq from the active shortlist; its price was never verified. Keep the budget-unrestricted enterprise comparison as curiosity-only background, without quotes, purchases or trial work. The active release uses free sources and manual starter confirmation; published low-cost subscriptions are optional and unpurchased.

The owner subsequently clarified the current private statistics-tool use. The [expanded low-cost source review](NHL_LOW_COST_DATA_OPTIONS.md) takes precedence for immediate procurement: test permitted free downloads and public NHL datasets first. The paid providers below remain optional candidates, not prerequisites for a useful NHL statistics release.

Keep the official NHL feed for scores, schedules and basic statistics. Prioritize the missing advanced inputs and confirmed starters. Extra odds capacity is useful after those inputs work, but does not make the model valid by itself.

First establish whether MoneyPuck's published downloads can cover the current private use. Its policy permits noncommercial use with credit; other uses require inquiry, and scraping outside published downloads requires approval. A future public subscription product needs appropriate rights. No commercial price is published on the reviewed page. [MoneyPuck downloads and use policy](https://moneypuck.com/data.htm).

For inexpensive paid research, Evolving Hockey Pro is the strongest candidate found. For automated pregame goalie confirmation, SportsDataIO's commercial feed is the most specific documented match. Obtain a narrowly scoped NHL goalie quote before considering a broad package. These are different jobs; neither provider has been verified to satisfy every requirement alone.

## Ranked by usefulness to our NHL release

The rank reflects documented fit, integration effort and known cost, not a measured reliability score. Quote-only providers cannot honestly be ordered by price. Dollar amounts are the providers' advertised prices before tax and currency conversion. The Odds API explicitly identifies USD; Evolving Hockey and PropLine's reviewed pricing pages display `$` without explicitly identifying currency, so confirm their billing currency before purchasing. Annual amounts are annual commitments, not monthly billing.

| Priority | Candidate | Published cost | Feature fit | Remaining limitation |
| --- | --- | --- | --- | --- |
| 1 | Evolving Hockey Pro | $9.99/month or $99.99/year; Standard is $4.99/month | Pro includes CSV exports and query tools. Its goalie glossary defines GSAx; team tables define xGF% and discuss 5v5 strength states. Useful for advanced-factor research and an owner-uploaded data workflow. | No public production API or confirmed-starter feed was verified. Membership is not automatic permission for scraping, redistribution or commercial feed use. |
| 2 | SportsDataIO commercial NHL | Quote required | Dedicated `StartingGoaltendersByDate` endpoint; individual goalie `Confirmed` boolean separates projected from confirmed. Documentation recommends a three-minute call interval. Best documented candidate for removing manual starter confirmation. | Need an NHL-only quote, real sample data, ID mapping, timestamps and confirmation revision history. GSAx and 5v5 xG were not verified in the reviewed dictionary. |
| 3 | MoneyPuck permitted/commercial data access | $0 for eligible noncommercial published downloads; other use requires inquiry | Published historical/game-level goalie and team data, shot xG and a documented GSAx definition. Strong alternative to a stats subscription. | No published commercial price or confirmed-starter API verified. Historical data downloaded now does not establish what was published before each past game. |
| 4 | Sportlogiq | No public price verified; request quote | Advertises expected-goal analysis, 300+ advanced metrics, manpower/date filters and raw-data API delivery. Strong specialist advanced-data candidate. | Specific NHL GSAx fields, pregame starters, historical publication timestamps and betting-product license need confirmation in the offered package. |
| 5 | Sportradar NHL | No public price verified; request quote | Official NHL data partner; REST, live events, injuries, depth charts, historical/season statistics and optional push feeds. Broad production infrastructure candidate. | Exact GSAx/5v5 xG and advance confirmed-starter fields were not verified. A media API trial/package is not proof of the appropriate betting license. Mostly duplicates our existing basic feed unless the required gaps are included. |

Evolving Hockey's [subscription page](https://evolving-hockey.com/subscribe/), [goalie glossary](https://evolving-hockey.com/glossary/standard-goalie-tables/) and [team glossary](https://evolving-hockey.com/glossary/standard-team-tables/) support its price/features. Its [overview](https://evolving-hockey.com/evolving-hockey-overview/) says in-season data updates daily. Its [terms](https://evolving-hockey.com/terms-of-use/) limit data to personal use, restrict copying/automated access and permit sharing attributed models; they do not establish a general commercial data-feed license. Subscription downloads must use the offered export mechanism, with any broader use clarified first.

SportsDataIO's [NHL API documentation](https://sportsdata.io/developers/api-documentation/nhl) and [NHL dictionary](https://sportsdata.io/developers/data-dictionary/nhl) establish its starter endpoint and confirmation flag. Its [licensing FAQ](https://sportsdata.io/help/data-rights-and-licensing-questions) says commercial licensing is quoted by feeds, leagues and use case. Request only the feeds we need.

MoneyPuck's [glossary](https://moneypuck.com/glossary.htm) defines GSAx. Its [about page](https://moneypuck.com/about.htm) describes predicted starters separately from media-identified starters. A predicted goalie must never satisfy our confirmed-personnel gate.

Sportlogiq's [hockey offering](https://www.sportlogiq.com/hockey/) establishes advanced metrics and API delivery. Sportradar's [NHL overview](https://developer.sportradar.com/ice-hockey/reference/nhl-overview) and [marketplace NHL listing](https://marketplace.sportradar.com/products/64ef56469b750f4d54d28503) establish its coverage. No authenticated evaluation or vendor quote has been obtained for these candidates.

## Paid odds: separate, optional ranking

| Rank for our existing application | Candidate | Cost / allowance | Why consider it |
| --- | --- | --- | --- |
| 1 | The Odds API 20K | US$30/month; 20,000 credits/month | Existing adapter minimizes migration work. Paid plans include historical odds. The US$59/month 100K tier is available if a measured research workload exceeds 20K. |
| 2 | PropLine Hobby / Pro | $9/month, 5,000 requests/day; $19/month, 25,000/day | Advertises line history, opening/closing prices and derived comparisons. Pro adds bulk graded-result exports. Evaluate the free 1,000/day tier before paying. |

Prices and allowances are from [The Odds API](https://the-odds-api.com/) and [PropLine pricing](https://prop-line.com/pricing). PropLine's [book list](https://prop-line.com/) includes PlayNow, but we have not authenticated a BC-specific price/market comparison. The specific PlayNow coverage page could not be reopened during this review; the earlier research is not a live quality guarantee. Its advertised archive begins April 2026, with depth varying by sport, so it must not be assumed to contain multiple full NHL seasons. Its [export documentation](https://prop-line.com/docs) describes synthetic watermark rows: exclude them from training and validation. Validate applicable use rights before activation.

Illustrative NHL-only usage, not an activated schedule:

- Three markets and two selected bookmakers cost three credits per current Odds API batch. Five-minute polling during an eight-hour daily window for 30 days would consume `12 × 8 × 30 × 3 = 8,640` credits. Reserve additional capacity for failures and research.
- A three-market historical timestamp query for one region-equivalent costs 30 credits. One hundred such queries consume 3,000 credits. A query can return multiple games; do not charge the estimate per game or assume every fixture needs a unique timestamp query. Historical book availability must be checked. [Quota and bookmaker rules](https://the-odds-api.com/liveapi/guides/v4/).
- One shared goalie-date request every three minutes for an eight-hour pregame window would be 160 requests/day, or 4,800 over 30 days. This is our proposed workload, not a vendor entitlement or an accepted billing quote.
- Advanced stats from completed games can normally be refreshed once daily, with bounded pregame freshness checks when required. Paying for a 30-second advanced-stat loop offers little value for a pregame model; the separate free live-score feed can retain its existing cadence.

Buying additional odds capacity would not itself enable automatic refreshes. The present five-attempt rolling-24-hour limit remains until the owner approves a specific replacement schedule and budget.

## Budget decision

| Budget choice | Practical result |
| --- | --- |
| No additional subscription | Assess permitted MoneyPuck downloads; keep free NHL scores and current free/manual odds. Starters remain source-backed manual evidence. |
| One small stats subscription | Evolving Hockey Pro at its advertised $9.99/month, subject to use/export rights. Supports research and manual import; does not buy automated confirmed starters. Prefer monthly evaluation before an annual commitment. |
| Add more odds capacity | Add US$30/month for the existing Odds API 20K plan, only if the measured usage/coverage need justifies it. This is separate from the stats subscription and existing hosting/AI costs. |
| Automate starters | Add the accepted NHL-only SportsDataIO quote to the chosen advanced-data option. A defensible total is not available until the quote and billing currency are known. |
| Broader commercial feed | Compare written Sportlogiq/Sportradar offers only if they demonstrably include missing features and fit the owner's budget. Do not infer an enterprise price from unrelated providers. |

SportsDataIO Discovery Lab is **not recommended for this live release**. Its developer guide advertises $99/month Fantasy or Odds and $149/month combined, but explicitly says next-day data and personal-use restrictions. Its ordinary free trial also uses scrambled data. Neither can establish today's pregame starter confirmation. [Product distinctions](https://sportsdata.io/developers).

## Questions to settle before any purchase

These are procurement requirements to send only if the owner explicitly authorizes vendor contact:

1. Can you provide NHL-only GSAx per goalie, team 5v5 xGF/xGA, strength-specific samples, game/player IDs and metric/model versions? Which fields are actual data rather than predictions?
2. Does the starter feed explicitly distinguish projected, confirmed, changed and withdrawn? How early is confirmation available, what is its source, and are original publication/update times retained?
3. Do historical responses preserve the version available before each game's T−30 anchor, including corrections and goalie-confirmation changes? Final box scores, historical outcomes and current season aggregates alone do not satisfy this.
4. Does the license cover private betting analytics now, derived model predictions, retained training data and a possible public subscription dashboard later? Which raw data may be displayed or exported?
5. What are the exact currency, monthly fee, commitment, included requests/objects, failure/retry accounting, overage policy, cancellation rules and NHL historical-data cost? Can overages and automatic top-ups be disabled?
6. Can a small real-data sample demonstrate confirmed starters, IDs, source times, 5v5 splits and goalie changes before a paid commitment? Scrambled examples are parser fixtures only.

## Integration safeguards and release consequence

Any selected adapter needs a shared server-side cache, durable admission counters, one admitted transport attempt for metered calls, bounded response size/time, cooldowns for failures, concurrency protection, preserved observation times, usage reconciliation and no automatic paid-provider fallback. Configure fixed monthly/day request budgets before enabling the adapter. Trials cannot silently upgrade or charge overages.

The existing US$3 monthly OpenRouter cap stays unchanged. AI reviews remain veto-only after deterministic model/evidence gates; a new provider or research import must not trigger paid AI automatically.

An advanced-data purchase may supply research features. It does not supply approved predictive performance or make newly downloaded historical rows genuine past observations. Keep reconstructed offline research separate from actual T−30 snapshots; reject postgame leakage, probable starters, invented timestamps and incomplete factors. The current release still needs valid source contracts, genuine evidence and chronological model validation before VERIFIED PLAY can be enabled.
