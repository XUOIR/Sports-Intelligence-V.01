# SportBot AI assessment — October 14, 2026

The rendered [pricing page](https://www.sportbotai.com/pricing) shows personal Pro at $18.99/month and Premium at $39.99/month. Lifetime Pro is $299 and lifetime Premium $999. These are website memberships. The separately advertised API starts at $999/month for Growth (10,000 requests/day), then $2,999/month for Scale (100,000/day). The site displays dollar symbols without an explicit currency label in the reviewed plan cards.

[API access](https://www.sportbotai.com/api-access) is manually reviewed for verified businesses using company details. Membership pricing does not establish programmatic access or redistribution rights. No account, inquiry, purchase or integration was created.

Their [NHL page](https://www.sportbotai.com/nhl) advertises hockey analysis, but the reviewed public pages do not establish a documented GSAx/5v5 xG or confirmed-starter API contract, PlayNow coverage or independent accuracy validation. Published model results are their own reports.

The [methodology](https://www.sportbotai.com/methodology) usefully distinguishes a margin-adjusted Pinnacle market benchmark from the predictive model. G$ now computes a similarly explicit benchmark from its own saved, complete Pinnacle price pairs; this introduces no new provider call. It does not replace NHL model validation or grant a verified-play status.

Decision: useful interface/methodology reference; the advertised integration tier is outside the current low-cost source plan. Continue the existing NHL/MoneyPuck statistics pipeline and repair the existing quote mapping before considering another feed.

## Props reference

The rendered [props page](https://www.sportbotai.com/props) has a working NHL selector. On October 14 it displayed two scheduled matchups, three public lines, and 311 advertised total props; the remaining 308 were Premium-gated. Those displayed counts and data were not independently validated. Useful patterns include exact player/line identity, L5/L10/L20 windows, source age, matchup context, explicit sample sizes, and separate projection and price columns. Historical hit rates must remain distinct from forecasts.

For G$, an eventual NHL player-research page can prioritize shots on goal and goalie saves, using permitted game logs and separately sourced exact PlayNow lines. First verify player IDs, starter/participation evidence, void/OT rules, sample integrity and quota cost. Every import must have shared caching, admission and failure limits before activation. The current three-market batch supplies game-level odds, not a player-props contract; this research introduces no additional requests or adapter.

## Suggested xG readings

The [EPLIndex article](https://eplindex.com/143517/why-expected-goals-xg-isnt-enough-without-a-probabilistic-model.html) distinguishes chance-quality summaries from outcome probabilities. It is a football explainer and promotes another analytics platform, not independent evidence validating our NHL model. The [Gecko Edge guide](https://geckoedge.ai/the-ultimate-guide-to-expected-value-betting-calculations-how-to-turn-raw-xg-into-value-odds/) describes a goals-distribution workflow and gives a priced expected-profit example. Its reported returns are promotional claims, not G$ test results.

Implementation decision: retain separate descriptive xG, predictive probability and market price fields. Do not transplant a soccer three-outcome scoring model into the existing two-way NHL model. For a binary market with decimal odds `d`, estimated profit per unit is `p*d − 1`; probability edge is `p − 1/d`, a different quantity. Tests verify that 65% at decimal 1.80 produces a 17% estimated return, without claiming that the probability is accurate. The daily comparison exposes both labels only when an actual saved forecast and price exist. Model calibration and chronological validation remain mandatory.
