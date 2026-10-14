# NHL release priorities and research

Reviewed October 13, 2026. Scope: XUOIR/Sports-Intelligence-V.01 only.
The additional research handoff is a source of leads, not a replacement specification.

## Owner's revision list

- Keep the current black, blue and violet theme, gradient buttons and interactive hologram.
- Require a private login before rendering the tool. Protect settings and development pages as well as all data routes. Provide sign out and session-expiry handling.
- Move credit limits, API connections, allowances and administrative controls to **Settings**.
- Keep **What's ready?** on a separate, temporary **Development** page. Remove it from the finished product when its acceptance criteria pass.
- Keep a fixed NHL match panel visible during desktop scrolling, with its own scrollbar. On mobile, keep its expandable match dock on screen.
- Order live matches first, upcoming matches by start time, then finals. Add previous/next dates, a date picker and Today. Initially support seven days either side of today.
- Show game state separately from WATCH / HOLD / PASS / VERIFIED PLAY. Unknown or expired evidence cannot produce a PLAY badge.
- Display actual source observation age and retained scores during outages. The displayed game clock is the last received clock, never a fabricated ticking estimate.
- Refresh a shared free NHL score feed about every 30 seconds during live play. Keep metered odds manual, at most five attempts per rolling 24 hours; keep the US$3 monthly AI protection.

## Hand-picked additions

[Statistips](https://statistips.com/) presents model probabilities beside market prices, explains drivers, and describes predictions logged before play and graded afterward. These are product ideas, not independently audited model results. Useful additions for G$ are:

1. A match explanation that identifies source, observation time, model version, probability, market probability and the reason to play or pass. Unknowns must stay explicit.
2. A pregame decision history that preserves revisions and records the final pregame decision. Postgame score updates must not rewrite the prediction.
3. Calibration and market-baseline comparisons alongside realized ROI and win rate. Accuracy alone does not establish an edge.
4. A postgame review comparing the saved prediction with the result, with losses retained.
5. Mobile readability and a consistent match-detail layout before additional sports, subscriptions or store packaging.

Statistips has actual [Apple](https://apps.apple.com/au/app/statistips/id6761458437) and [Google Play](https://play.google.com/store/apps/details?id=com.statistips.application) listings. Their existence does not establish future store approval for G$. Its public pricing offers a free tier and AUD9.99/month Pro; subscriber counts and profitability were not verified. No competitor code, private model or dataset has been copied.

## Verified provider shortlist

Reddit discussions are discovery leads. In particular, [NHL data pull](https://www.reddit.com/r/algobetting/comments/1isv0mg/) points to NHL data and SportsBlaze, and [Best Free APIs](https://www.reddit.com/r/algobetting/comments/1nftny1/best_free_apis_to_get_started/) mentions SportsGameOdds and OddsPapi. Claims below come from provider pages unless labeled as live verification. No accounts, subscriptions or new keys were created.

| Provider | Current evidence | Decision |
| --- | --- | --- |
| NHL Web API | Live unauthenticated `/v1/score/2026-10-13` returned actual live, upcoming and final NHL games, scores, period and clock fields. No published allowance or availability guarantee was verified. | Retain for scores, schedules, results, rest and basic stats. Keep the existing 300/day statistical request cap, with a separate **1,500/day score cap**. These are our protective limits, not vendor entitlements. It does not establish pregame starting-goalie confirmation or supply the complete advanced model. |
| The Odds API | Existing free key: 500 billing-period credits. Our three-market NHL batch reserves three credits; manual-only and rolling five-attempt cap remain. | Production baseline. Live scores do not call it. Retain exact PlayNow participant/market/line checks. |
| PropLine | [Pricing](https://prop-line.com/pricing) advertises 1,000 requests/day free. [PlayNow coverage](https://prop-line.com/odds-api/book/playnow) explicitly lists NHL and MLB, pregame only. [Docs](https://prop-line.com/docs) publish daily quota headers and UTC resets. | **First odds candidate to test.** No authenticated comparison has been performed; no G$ key is configured. An advertised book listing does not prove BC-specific prices, OT rules, complete market coverage, latency or reliability. Keep it out of production until those pass. |
| PropLine terms | [Terms](https://prop-line.com/terms) allow internal tools and individual derived values, prohibit bulk redistribution and describe synthetic watermark rows in bulk exports. | Review product use against these terms; exclude synthetic rows from research. A switch needs bounded calls, provenance and quotas before activation. |
| MoneyPuck | [Published downloads](https://moneypuck.com/data.htm) provide goalie and team data. Free use is limited to noncommercial purposes with attribution; other use requires inquiry. Unapproved scraping is prohibited. | Strong advanced NHL research lead. Verify dataset timestamps and rolling GSAx/5v5 xG definitions. Do not present end-of-season aggregates as facts available before historical games. Public/commercial deployment needs appropriate permission. |
| SportsBlaze | [Free plan](https://sportsblaze.com/pricing): all leagues, core endpoints, 10 requests/minute, up to three-minute delay. [NHL boxscore docs](https://docs.sportsblaze.com/nhl/core_endpoints/daily_boxscores/) require a key. | Potential backup score/basic-stat feed. Delayed free data does not solve the confirmed-starter or advanced-input blockers. No key or licensing trial performed. |
| SportsGameOdds | [Free plan](https://sportsgameodds.com/pricing): 2,500 objects/month, 10 requests/minute, ten-minute updates, nine listed US-oriented books. | Secondary research only. Objects are not requests; no verified free PlayNow coverage. It does not improve this NHL execution workflow yet. |
| OddsPapi | [Provider's NHL article](https://oddspapi.io/blog/nhl-first-period-odds-api/) advertises 250 requests/month and historical odds. | Historical-data lead. Provider comparisons contain claims that conflict with our verified The Odds API entitlement, so do not adopt them as facts. Verify actual NHL/PlayNow coverage and licensing before any replacement. |
| BALLDONTLIE | [Terms dated September 17, 2026](https://www.balldontlie.io/terms) expressly permit lawful betting analytics and model development subject to restrictions. | Research MLB when NHL is complete. These terms do not prove free advanced data or NHL coverage. No adapter is activated. |
| Cito / PandaScore | [Cito terms](https://docs.citoapi.com/terms/) disclaim underlying rights clearance and a betting-grade feed. Existing PandaScore restriction remains unresolved for this use. | CS2 remains paused. Require current rosters, map history, vetoes, quality timestamps and permitted betting use before enabling either. |

The strongest new finding from the supplied handoff is PropLine's **specific PlayNow NHL claim**, now checked against its own page. Its quoted competitor accuracy figures were not needed for this release and are not treated as verified financial performance. NFL, NBA and college expansion are outside this release's NHL → CS2 → MLB priorities.

## Shortest path to trustworthy NHL plays

The [paid NHL source comparison](NHL_PAID_DATA_OPTIONS.md) ranks advanced-stat, confirmed-starter and optional odds candidates by documented fit and published cost. It identifies Evolving Hockey Pro for low-cost research, SportsDataIO commercial NHL for explicit starter confirmation, and MoneyPuck as a permitted-download alternative. No subscription or additional spending is activated by that research.

The production audit found **zero approved models and zero labeled, usable training records**. No UI or AI review can cure that. The current strict model requires normalized goalie/GSAx, 5v5 xG, rest/fatigue and venue/special-team inputs, source-backed confirmed starters, a T−30 snapshot, current PlayNow prices and all eight gates.

1. **Data contract:** obtain permitted advanced NHL data plus confirmed-starting-goalie evidence. Preserve game/player IDs, original observation timestamps, sample windows, normalization definitions and raw source references. Reject probable starters, incomplete factors and postgame leakage.
2. **Historical validation:** import only genuine point-in-time records available before each historical anchor. Keep offline reconstructed research separate from observed live snapshots. Do not backdate newly downloaded season totals or declare them observed T−30 records. Run chronological 60/20/20 partitions with two-date embargoes and at least 300/100/100 records after embargo. Approve only a model meeting the existing calibration and market-baseline criteria.
3. **Execution rehearsal:** test new valid and invalid evidence, odds age, market rules, exposure changes, AI veto/failure, stake caps, duplicate ticket logging and settlement corrections in the disposable database. Bet placement remains manual; G$ records actual tickets.
4. **Live acceptance:** collect real T−30 snapshots, obtain current matching PlayNow prices, confirm starters and pass every gate. Measure realized return, calibration and eventually closing-line value using genuinely observed closing prices.
5. **Expansion:** after NHL acceptance, complete permitted CS2 sourcing, then MLB. Add subscriptions or native store submissions after the core tool works and data-use terms support that product.

PropLine may improve price freshness economically, but it cannot replace goalie evidence or model training. Changing a free odds source does not authorize automatic paid fallback calls. No new paid recurring cost is introduced by the current UI/score release. The completed work does not claim that NHL picks are ready to stake yet.
