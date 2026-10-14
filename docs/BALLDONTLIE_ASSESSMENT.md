# BALLDONTLIE: NHL, CS2 and MLB assessment

Reviewed October 13, 2026 for XUOIR/Sports-Intelligence-V.01. Public documentation, the keyless plan catalog and the NHL schema were inspected. No account, subscription, card-backed trial, authenticated sports-data request or production integration was created. Catalog/schema copies are retained in ignored local research artifacts.

**Decision:** do not buy NHL ALL-STAR to complete the current advanced model. It covers basic data already obtainable through the existing NHL integration. Keep BALLDONTLIE as a later CS2/MLB candidate, with field, freshness and cost checks before activation. The NHL release remains the priority.

## Coverage and subscription limits

The [public plan catalog](https://api.balldontlie.io/account/v1/plans) returned 40 league/competition products with sports specifications; this means 40 products, not 40 distinct sports. Catalog retrieval returned HTTP 200 without authentication. See the [account documentation](https://www.balldontlie.io/account/) for the public discovery endpoint.

| Family | Catalog products |
| --- | --- |
| Hockey | NHL |
| Baseball | MLB, college baseball |
| American football | NFL, college football |
| Basketball | NBA, WNBA, college men/women; EuroLeague, EuroCup, Basketball Champions League, Liga ACB, Turkish Super League, Greek Basketball League, Lega Basket Serie A, Basketball Bundesliga, LNB Elite, ABA, Lithuanian Basketball League, VTB, BNXT, Israeli Premier League |
| Soccer | EPL, La Liga, Serie A, Bundesliga, Ligue 1, MLS, Champions League, FIFA World Cup |
| Esports | CS2, Valorant, League of Legends, Dota 2 |
| Other | MMA, PGA Tour, ATP, WTA, Formula 1 |

Standard monthly subscriptions cost US$9.99 ALL-STAR or US$39.99 GOAT **per league/product**. Advertised request ceilings are 60/minute and 600/minute respectively; free/trial is 5/minute. The catalog identifies a 60-second rate window. No monthly credit wallet, universal monthly request allowance, precise window algorithm, failed-call accounting or request-overage tariff was verified. Do not reinterpret a per-minute limit as guaranteed unlimited access. [Account plans](https://www.balldontlie.io/account/), [NHL pricing](https://nhl.balldontlie.io/#account-tiers).

| Priority | ALL-STAR entitlement | What requires GOAT | Assessment |
| --- | --- | --- | --- |
| NHL | Teams, players, games, standings, box scores | Play-by-play, injuries, season statistics, leaders, odds and props | Basic-feed alternative; does not establish the missing advanced inputs. |
| CS2 | Reference data, team map pool, rankings | Matches, maps and detailed match/player statistics | US$9.99 alone cannot power our intended match analytics. US$39.99 is a research candidate. |
| MLB | Games/reference data plus injuries, active players, standings and game player stats | Season stats, splits, pitcher/batter matchups, plays, pitches, lineups, odds and props | Potential later basic-stat candidate; richer modeling requires additional coverage. |

Sources: [NHL tiers](https://nhl.balldontlie.io/#account-tiers), [CS2 tiers](https://cs.balldontlie.io/#account-tiers), [MLB tiers](https://mlb.balldontlie.io/#account-tiers). Three ALL-STAR subscriptions would total US$29.97/month before tax, but that combination lacks CS2 matches. NHL/MLB ALL-STAR plus CS2 GOAT would cost US$59.97 and still would not establish NHL advanced-model completeness. These are calculated subscription totals, not a purchase recommendation.

## NHL model gaps

The [NHL OpenAPI schema](https://www.balldontlie.io/openapi/nhl.yml) downloaded successfully (52,885 bytes). No dedicated xG/GSAx fields or pregame confirmed-starting-goalie endpoint were documented. A nullable boxscore `starter` field has no documented pregame confirmation time/source guarantee. It cannot satisfy our starter gate merely because it exists.

GOAT play events describe coordinates, goalie IDs when available, and skater/goalie presence. These can identify 5v5 events when complete, but do not supply a trained expected-goal model or ready-made 5v5 xG share. Deriving GSAx from saves/save percentage alone is invalid. Historical coverage, source-publication times and correction history still need verification; game dates alone are not genuine pregame observations.

BDL Lab is a separate model/backtesting product and is not included in US$9.99 ALL-STAR. Buying data does not approve a G$ predictive model. [Lab API entitlement](https://lab.balldontlie.io/docs/api/).

## Delay claims and user reports

- **February 19, 2026:** two participants in [Sports Betting Data, API Sources](https://www.reddit.com/r/algobetting/comments/1r8jcuz/sports_betting_data_api_sources/) said they used BALLDONTLIE alongside The Odds API; one described satisfactory operation and pricing. This is an anecdote from a product builder, not measured latency.
- **April 2026:** [Best Odds APIs?](https://www.reddit.com/r/algobetting/comments/1sdygwx/best_odds_apis/) includes positive price/value comments for BALLDONTLIE and use across several sports. The complaints about mixed home/away teams and market types in that thread concern other odds feeds; they must not be attributed to BALLDONTLIE.
- A [separate user's settlement workflow](https://www.reddit.com/r/AiAutomations/comments/1s2ssuw/i_built_a_fully_automated_sports_betting_edge/) uses BALLDONTLIE and periodic checks for delayed/corrected statistics. The described possibility of late statistics is not a measured outage or a verified NHL delay. Their model-profit claims are not audited evidence.

Targeted searches did not substantiate a widespread current NHL delay/outage complaint. The reviewed sample is small and not representative; absence of a located complaint does not establish reliability.

Independently of Reddit, [provider terms, sections 8–9](https://www.balldontlie.io/terms.html) explicitly describe best-effort data that can be incomplete, revised or delayed by seconds, minutes or longer, with no guaranteed live delivery time. [Webhooks documentation](https://www.balldontlie.io/webhooks) describes possible one-minute delays and lists NHL events under ALL-ACCESS, rather than the US$9.99 plan. Neither statement is a measured REST latency result.

## Use and spending safeguards

Provider terms permit lawfully obtained data for analysis, caching, retained research, derivative tools and lawful wagering/AI uses, subject to restrictions including competing products and unmodified raw-data resale. This is provider permission, not blanket third-party rights clearance. It does not extend endpoint entitlement. [Terms, sections 6–7 and 11](https://www.balldontlie.io/terms.html).

The advertised 48-hour GOAT trial requires a payment method and converts to paid unless canceled. Do not start it automatically. [Trial conditions](https://cs.balldontlie.io/#48-hour-free-trial).

If later admitted, begin with one sport and an explicit fixed subscription budget. Use a shared cache, persistent request ceilings, bounded single attempts, cooldowns and retained truthful timestamps; never auto-upgrade, create another key or switch to a paid fallback after a failure. A single shared slate request every 30 seconds for eight hours would be 960 requests/day, approximately 28,800 in 30 days before pagination and other endpoints. This is our workload estimate, not entitlement or a source freshness guarantee. Paying for GOAT does not compensate for missing required fields.
