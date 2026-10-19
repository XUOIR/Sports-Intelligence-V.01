# Statistips REA review — October 19, 2026

## Outcome

The requested REA investigation ran successfully. The best immediate changes
for G$ are clearer model selection on Daily Matchups, smaller summary cards,
and an explanation of the exact inputs used by each saved forecast. A visual
calibration chart can follow using data we already collect. None requires a
new provider subscription or paid AI generation.

This review changes no application behavior, frozen model, approval gate,
provider configuration, spending limit, bankroll record or deployed release.
It proposes an implementation order; these UI improvements are not yet built.

## Scope and evidence

- Target: [Statistips](https://statistips.com/), public landing page and its
  explicitly offered completed-round dashboard preview. No account was created.
- Browser observations: NFL matchup analysis; AFL Model Stats and its missing
  saved-price state; Soccer fixtures, gap filters and matchup Odds tab.
- [REA 6.7.0](https://github.com/morluto/rea) was downloaded from its official npm
  package, with SHA-512 verified against registry metadata. Dependencies were
  isolated under ignored research artifacts, with installation scripts disabled.
- The bundled `reverse-engineer-anything` skill and JavaScript/recovery guides
  were read. REA ran through its CLI; Codex configuration and global skills were
  not modified. Its read-only doctor found no registered REA server; that did
  not prevent the supported standalone static analysis.
- Five publicly delivered JavaScript artifacts, totaling **1,203,134 bytes**,
  were analyzed as inert text. REA did not execute those downloaded files.
  Normal website behavior was inspected separately in the browser.
- No authenticated API probing, private endpoint access, guessed asset crawling,
  source-map discovery or provider request from our platform was performed.

REA Evidence records:

| Run | Evidence ID | Coverage |
| --- | --- | --- |
| Public main module | `ev_66f5d107144433a64dca698f73af4dee98b4d1ed76da568fc9b608dc4a0ca10b` | Parsed successfully. Application relationships partial; semantic graph explicitly bounded at 12,000 nodes / 10,000 unknowns. |
| Four selected feature modules | `ev_7ab60e107e41b41c25ce6a8f5b625014fb1e771f09cfb4614aa009978c617877` | Four parsed successfully; selected-file application graph complete. Semantic coverage remains unknown, with dynamic relationships unresolved. |

The feature modules concern API access, Model Stats, market divergence and
odds comparison. Their identities were selected from REA's main-module import
inventory. Other chunks remain outside this analysis. Static imports and
endpoint candidates do not establish runtime execution or backend behavior.

Local evidence is retained in
`artifacts/statistips-rea-2026-10-19/`: complete REA JSON records, package and
asset manifests, hashes, `analysis-summary.json`, browser accessibility captures,
and `statistips-model-stats.jpg`, `statistips-gaps.jpg`, `statistips-odds.jpg`.
Third-party source files and screenshots remain ignored, outside production.

## Public observations and limits

The preview uses compact fixtures with a detail panel, analysis tabs, driver
summaries, market-gap filtering and a calibration plot. AFL's record separates
several samples. Its disagreement explanation references team ratings, not
archived closing odds; one saved round lacks prices. Soccer preserves example
prices. These are observed interface features, not independently verified model
performance. The Odds panel also describes market information among its inputs.

The [methodology page](https://statistips.com/how-it-works) describes public data,
walk-forward testing and simulations. Those are the publisher's claims. This
investigation does not verify training vintages, leakage controls, full data
rights, live latency, operating costs or profitability. It does not reveal a
new NHL source or establish that an equivalent NHL product can run entirely free.

In the observed Soccer example, a Chelsea price of -137 implies about 57.8%
break-even, whereas its market comparison displays 55.3%. This is consistent
with a margin-adjusted market reference, but does not establish the server's
precise calculation. G$ must keep the offered-price break-even and a normalized
market benchmark explicitly distinct. Disagreement with a reference alone is
not proof of positive expected return at an available price.

## Comparison with the current G$ implementation

Repository inspection, rather than assumptions about the live UI, establishes:

- `Dashboard.tsx` passes `modelResults.paper` to `DailyMatchups`. The separate
  xG cohort is displayed in Model Performance, not selected on the main cards.
- `matchup-forecast.mjs` validates fixture identity, forecast timing and a
  complementary two-way probability before displaying paper output. It does
  not infer probabilities from sportsbook prices or descriptive xG share.
- `DailyMatchups.tsx` already has team logos, saved PlayNow prices, break-even,
  xG, baseline probability, signed edges, fair odds and detailed source notes.
  Much of this remains expanded on every card.
- Existing watchlist thresholds apply to fixture recommendation fields. They
  should not silently become filters for a different paper cohort.
- `NHLValidation.tsx` already exposes cohort-specific scoring, paired market
  comparisons, calibration bins and Wilson intervals. Its calibration surface
  is currently a table.
- `market.mjs` separates offered-price break-even from no-margin probabilities.
  Preserve that separation and all freshness/approval checks.

## Recommended implementation order

| Priority | Change for G$ | Implementation and acceptance criteria |
| --- | --- | --- |
| 1 | Explicit forecast choice on Daily Matchups | Add Baseline / xG Candidate research selection. Keep the current baseline default. Display selected model identity, capture time and PAPER status. Match fixture/start/team identities; never fall back silently between cohorts. Switching views does not write probabilities, create a position, refresh odds or alter approval. |
| 2 | Compact summary with expandable detail | Show teams/logos, start, both win probabilities, two PlayNow prices, signed edges, starter state and freshness up front. Put xG windows, fair prices, market benchmark and calculation detail behind clearly named expansion sections. Retain all information and the theme. On a ten-game slate, the default view should be easy to scan without ten expanded statistics panels. |
| 3 | Explain the actual forecast inputs | Start with recorded feature values: rating difference, rest/back-to-back state and, for the candidate, prior-game xG and team goaltending form. Derive displays from the saved input vector. Do not present descriptive metrics as model inputs when they are not. Do not invent percentage-point or causal contributions; exact attribution requires a separately verified calculation including calibration. |
| 4 | Calibration plot beside the existing table | Use the already returned bins, sample counts and Wilson intervals. Include a diagonal reference, accessible table and explicit cohort/sample labels. Empty bins stay empty; do not smooth a small sample into a precise curve or introduce arbitrary confidence labels. |
| 5 | Research model-versus-price list | Rank a selected cohort's signed PlayNow edges with source time, fresh/expired filter and clear units. Keep research estimates separate from verified recommendations. A strong winner forecast is not automatically a worthwhile price. Current production watchlist filters retain their existing meaning. |
| 6 | Small forecast/change history | Link real captured forecasts and eligible observed price pairs. Show what changed only where actual earlier observations exist. Never reconstruct a missing closing line or manufacture a price history between sparse refreshes. |

Items 1, 2 and 4 can use existing authenticated responses and browser-side
display calculations. Item 3 may need a small authenticated read-only projection
of the saved input vector; it needs no new external feed. Item 5 must reuse saved
prices, not add polling or paid refreshes. Incremental external-provider cost for
these display changes should be zero; normal existing hosting/database use still
applies.

Keep any implementation additive and small. Useful checks include wrong-cohort
and wrong-fixture rejection, stale/future quote handling, no paid calls on view
changes, exact numeric/chart parity and keyboard/mobile expansion behavior.
Frozen inference files and stored forecast cohorts must remain unchanged.

## Defer

Props, correlated parlays, scoreline distributions, goalie replacement what-ifs,
additional sports and native app distribution remain outside the initial NHL
moneyline release. They require new tested models or inputs; reproducing a
polished panel would not supply those requirements. Simulation volume alone
does not establish better probabilities.

Our next scientific step remains genuine forward forecast/result and matched
PlayNow validation. The review supplies interface improvements, not a shortcut
around that evidence.

## Owner actions

**Urgent:** none for this review. No purchase, credential or REA configuration
change is required.

**Can Get To:** review the ranked UI recommendations when convenient. Existing
Daily Faceoff supported-use questions remain separate from this website review.
