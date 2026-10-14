# Daily NHL markets and private results pages

October 14, 2026. Active repository: XUOIR/Sports-Intelligence-V.01.

## Odds diagnosis

The production database had zero saved quotes after two successful three-credit manual requests. A separate, documented [zero-credit NHL events request](https://the-odds-api.com/liveapi/guides/v4/#get-events) returned 13 upcoming events; its headers confirmed 494 remaining, 6 used and last cost 0. Their start times were ten minutes later than the official NHL fixtures (Washington–Montréal: 23:40 UTC versus 23:30). The old five-minute matcher discarded such events. Prior full odds responses were not retained, so those original payloads cannot be replayed or independently inspected now.

NHL matching now allows fifteen minutes, requires exact normalized ordered participants and exactly one candidate, and preserves the official start and T−30 anchor. It saves the provider event ID, start and offset for diagnosis. Ambiguous fixtures and a sixteen-minute offset remain rejected in tests. Non-NHL tolerance remains five minutes.

Each new manual refresh records received/matched/unmatched event counts and saved quote counts, including PlayNow. Its response explains the outcome. A response with no matched events or no newly saved prices opens the odds circuit, retaining the consumed reservation and preventing another empty credit spend until an explicit resume. Automatic refreshes and all existing daily, rolling and monthly limits remain unchanged.

## Product changes

- Overview focuses on daily matchups. The shared date controls change both the main cards and the sidebar. Prices and statistics are separate feeds.
- PlayNow two-way moneyline prices, observation time and raw break-even probability appear on each card. Old prices remain visible as last received and do not pass freshness gates. Pinnacle never substitutes for missing PlayNow execution prices.
- Saved model probabilities use the engine's selected side, with the opposing side calculated as its complement. Probability indicators are read-only. Signed edge is `model probability − 1 / PlayNow decimal odds`, expressed in percentage points; model fair odds are `1 / model probability`. Estimated return per unit, `model probability × decimal odds − 1`, is separately labelled and depends on the forecast. Missing forecasts remain unknown. Descriptive xG share is not relabelled as a win probability.
- A separate Pinnacle market benchmark normalizes the two inverse prices to remove the margin. It is explicitly market-derived, not the G$ predictive model, and cannot approve a play.
- Latest quotes are read in one database query, deduplicated by fixture and quote identity. Complete moneyline pairs must share a bookmaker and source timestamp; books, lines, markets and observation times cannot be mixed.
- Model Performance is a protected page with sport-scoped saved forecasts, resolved accuracy, Brier score, original anchors, versions and prediction history. Only NHL is currently active. Tickets do not establish model accuracy or model ROI.
- Bankroll is a protected page containing existing capital, exposure, ticket performance, logging and manual settlement functionality. Existing filters, watchlist, matchup details, evidence entry and Settings remain available. The theme and hologram are preserved.

No database schema, credentials, provider budget, staking rule, model approval or confirmed-starter rule changed. Opening pages and changing dates read cached data; score-feed demand retains its existing shared limits. No subscription or paid fallback was introduced.

## Verification

All 158 backend tests and 14 frontend tests passed (172 checks). Frontend type checking and the production build passed. Browser QA verified a complementary 38%/62% test forecast, negative/positive edges, blank unknown values, date navigation, separate saved model grading and ticket returns, and a 390-pixel mobile viewport without horizontal page overflow. Local QA uses disposable SQLite, synthetic prices/forecasts/tickets and real previously audited descriptive statistics; it cannot establish production quote availability. Production deployment IDs, first actual saved quotes and live UI proof still require verification.

## Rollout status — 1:59 PM Pacific

Code is pushed and both authorized Render deploys have been submitted once:

- Backend `1f4d2d69052d946cc6f40195924994716e988e1b`: `dep-db7uhnrl550s73dekqj0`, submitted 1:41:03 PM Pacific.
- Frontend `d9b82e4`: `dep-db7ulhd9fdbs73dj400g`, submitted 1:49:09 PM Pacific. This later commit changes expected-return labels/tests and research notes; backend code is identical to the backend deployment commit.

Both remained Building with no build logs after approximately eighteen and ten minutes. [Render's incident](https://status.render.com/incidents/8tsd93r1wbmz) concerns builds not starting across all regions, including Oregon. A fresh public status API read at 1:58 PM showed the incident still identified, updated at 1:55 PM; the earlier cached webpage had shown monitoring. This supports a platform queue/start problem; it is not evidence of an application build error. The existing backend `/health/ready` remained 200 and `/performance` remained 404, confirming the new route was not yet live. Do not describe these new pages or the matcher fix as deployed until verified.

**Metered feeds were paused through the existing private Settings control.** The UI shows METERED FEEDS PAUSED and PostgreSQL independently confirms `control:paid = 1`. This prevents another empty manual request through the old matcher. Free NHL scores and descriptive statistics are unaffected by that control. No additional metered odds refresh or AI generation was sent. Fresh provider metadata at 1:58 PM confirmed 494 odds credits remaining/6 used and US$0 OpenRouter usage, with the US$3 monthly-reset cap intact.

Protected local `/bankroll` and `/model-performance` requests without a session returned 307 to `/login`; `/api/data/performance` returned 401. Final browser QA also verified separate probability-point edge and estimated return labels. The illustrative preview is not a production forecast or actual bookmaker price.

To complete rollout: wait for both existing deploys to become Live; confirm their commits, migration logs, health and unauthenticated route protection; then explicitly resume metered feeds and admit **one** guarded three-credit manual refresh. Verify its counts, stored real PlayNow prices, both teams' main-page prices, benchmark source age, and unchanged AI spending. An empty/uncertain request must not be repeated; preserve reservations and diagnose its saved report. No deploy cancellation, duplicate deploy, provider-budget reset or paid fallback was used during the incident.

## Next steps for verified NHL forecasts

1. Verify a single bounded manual refresh actually saves current PlayNow quotes after deploying the matcher. Check its saved counts and both teams' main-page prices; do not repeat uncertain requests.
2. Capture source-backed confirmed starters through the existing evidence workflow. A goalie comparison selection does not confirm a starter.
3. Complete documented normalization and source-backed model factors, preserve genuine observations before the official T−30 anchor, and evaluate the required chronological training/validation/test partitions. Newly downloaded postgame statistics cannot be backdated into observed snapshots.
4. Approve only a model passing the existing criteria; then rehearse all eight gates with current prices, starter evidence and exposure. AI remains a bounded veto after deterministic checks, not a probability generator.

The remaining starter and model-validation requirements are not solved by rearranging the dashboard or by another provider's advertised predictions.
