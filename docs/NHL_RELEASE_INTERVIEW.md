# NHL Release Interview

Started October 15, 2026, in the active XUOIR/Sports-Intelligence-V.01 chat.

## Purpose

Resolve product and model decisions before implementing the proposed NHL model change. Preserve the current application, theme, source evidence and spending protections. This interview does not approve a model, a provider purchase, a budget change or a production gate change.

## Owner's stated objective

Build a data-driven NHL model with an edge over sportsbook prices, producing solid, evidence-backed recommendations about game winners. The owner needs guidance defining a first release and has not set a numerical win-rate or ROI target.

This is an objective, not a demonstrated result. Guaranteed correct game predictions are not an achievable acceptance criterion. Prediction quality and price-relative wagering performance require separate evaluation; a high win rate alone does not establish a profitable edge.

## Interview setup

- Installed upstream `grill-me` and its required `grilling` dependency into the local Codex skills directory using the built-in Skill Installer.
- Source: https://github.com/mattpocock/skills/tree/main/skills/productivity
- Apply a one-question-at-a-time adaptation for this conversation, with an explained recommendation and room for a different answer.
- Investigate technical facts from the active repository and primary documentation; ask the owner for goals and tradeoffs.
- Record accepted decisions separately from proposals and unresolved questions. The staged team model remains a proposal to examine.
- Produce a release specification and measurable acceptance criteria once shared understanding is reached.

## Accepted decisions

**Q1 — Recommendation timing: pregame first.** The owner answered “Yes, I agree” to the clarified question asking whether the first release should make recommendations only before games start, with live betting recommendations added later. Existing live-score display and tracking earlier recommendations are separate from issuing new in-play recommendations.

The original timing question also mentioned two-way moneyline and overtime/shootout, but the clarification explicitly separated bet types. Q1 settled timing only; Q2 below settles the initial outcome target.

**Q2 — Initial bet type: eventual game winner, including overtime/shootout.** The owner answered “Yes” to focusing the first release on this outcome, with other bet types added later. Regulation-only winners, goal spreads, totals and player props remain outside the first-release recommendation scope.

Actual provider market labels and settlement terms must still be checked before implementing price comparisons. This product decision does not establish that any particular quote matches the target.

**Q3 — Selectivity: no forced bets or daily pick quota.** The owner answered “Yes, we don't want to manufacture a bet just because there isn't one.” The dashboard may recommend no bet on an individual game or no bets for the whole day when prices offer insufficient model-estimated value or required checks fail. Analysis can remain visible where adequate data exists.

This accepts selective recommendations, not any numerical edge threshold, model approval or relaxation of verification requirements.

**Q4 — Testing before real-money use: historical evaluation, then live paper tracking.** The owner answered “Yes” to requiring this sequence before treating recommendations as ready for real-money use. Paper tracking saves predictions and actual available prices before games and records simulated results without risking funds or changing the actual bankroll.

Numerical pass criteria, adequate sample sizes, uncertainty estimates and the observation period must be proposed after the data audit and agreed before the final test is used for approval. Research forecasts, simulated wagers and actual transactions remain distinguishable. This decision does not approve a particular model, test duration, gate change or new spending.

**Q5 — Forecasts with unconfirmed goalies: allowed under a suitable validated model.** The owner answered “yes” to showing a clearly labeled forecast while starters remain unconfirmed, provided the model is specifically designed and tested for that information state and passes the agreed requirements. Starting-goalie uncertainty must remain visible; an assumed starter cannot become a factual confirmation.

Q5 permits forecast availability; Q6 below separately resolves the owner's expected-goalie policy for potential actionable plays. Neither answer approves a particular fitted model or a production release. Confirmed-goalie adjustments remain a separately evaluated enhancement.

**Q6 — Starter evidence for actionable plays: expected goalies are acceptable for now.** The owner answered: “we can go forward with expected goalie lineup, it doesnt have to be confirmed, for now.” This rejects the proposed requirement that every first-release recommendation wait for both confirmed starters.

Expected, projected and confirmed statuses must remain distinct, with the actual source or projection basis, observation time and uncertainty visible. Expected goalies must never be stored or displayed as confirmed. The future model and recommendation policy must be designed and evaluated for the information actually available, including incorrect expected starters and late changes; all other applicable model, price and risk checks still apply. If the forecast depends on a specific goalie assumption, preserve it and handle a changed assumption explicitly.

This is authorization for the release design to accommodate expected lineups, not evidence that the present goalie-dependent model is validated for that use. Implement a compatible versioned contract after the interview and required evaluation; do not satisfy an existing confirmation gate by falsely setting it true. No runtime gates were modified during this interview.

**Q7 — Manual review: reluctantly accepted as a temporary initial fallback; automation is preferred.** After clarification of price checks, flagged lineup warnings and paper decisions, the owner answered: “I guess so, it's suppose to be automated, so I'd prefer if we can automate it fully, but initially, sure.” Do not interpret this as a preference for a permanently manual workflow or for reviewing every fixture.

Design for automated data collection, calculations and results tracking where reliable access and existing allowances permit. Surface concrete exceptions and use manual review for potential plays initially where automation cannot be qualified. Expected goalies remain permitted under Q6; a review does not require formal starter confirmation. No exact daily workload has been accepted. This preference concerns the analytics workflow and does not authorize automated wager placement, new subscriptions or increased spending caps.

## Simulation idea raised by the owner

The owner proposed simulating scheduled or hypothetical team-versus-team matchups repeatedly, for example 100 times, to inform picks, and asked whether this is affordable. This is an idea to evaluate, not an approved production model or evidence of a predictive edge.

**Priority update:** the owner suggested using the NHL season as a real-results comparison period, then asked to move on from additional simulation work unless it materially improves the model. Defer the extra simulation feature. Preserve the agreed historical evaluation and genuine forward tracking plan; use the existing results-ingestion path where suitable rather than introducing per-simulation API calls. A full-season experiment is an optional longer-term study, not an approved requirement to wait an entire season for a release. Any simulation improvement must be assessed on real held-out outcomes and price-relative performance, not an inflated count of simulated wins.

- Lightweight local simulations do not inherently require new data subscriptions or an AI call per run. Benchmark compute cost on the existing environment before selecting a production run count.
- Known matchups identify the fixtures to evaluate. Real earlier-game data and a suitable model must supply team strengths, scoring/win distributions, home advantage, rest and any justified goalie assumptions. A future schedule alone supplies no winning probabilities.
- A score-based simulation would need correctly modeled regulation ties and overtime/shootout outcomes to match Q2. Hypothetical pairings need explicit venue/date assumptions; future injuries and starters cannot be treated as known.
- A direct calibrated win probability can often be used without simulation. Repeatedly sampling that same probability only approximates it and adds no independent predictive signal. Simulation is potentially useful for scoring distributions, scenario sensitivity and uncertainty propagation, subject to real-data evaluation.
- One hundred runs can be noisy. More runs reduce numerical sampling noise, not uncertainty or bias in the underlying model. Candidate run counts in the thousands can be evaluated with bounded batches, reproducible seeds and shared cached results keyed to the model/input versions.
- Simulated games are not extra observed games, training labels, genuine forward forecasts or bankroll outcomes. They cannot count toward the validation sample or be used to prove that the model beats sportsbooks. Derived simulation outputs need testing against real held-out results.

## Budget decision

**Q8 — Additional data budget: free first, reasonable paid options remain open.** The owner answered: “If we can achieve what we want for free, then let's do it, if we need paid models, we'll reconvene later, it's not necessarily the money that matters the most, if it's reasonable and it fills the data we need, we can explore that route.”

Prioritize suitable free sources and the existing cached data. Do not treat free-only as an absolute product requirement or cost as more important than filling a necessary gap. A concrete reasonable paid source/model can be reconsidered with verified capabilities, permitted use, total price and spending safeguards; return to the owner before purchase or a budget increase. No numerical general data-subscription ceiling was set. The word “models” does not itself authorize a new AI subscription or a paid API trial.

Existing hosting costs and separately discussed AI allowances remain distinct. No provider cap, key limit, subscription or runtime behavior was changed by this decision.

## Next step in the interview

The main product choices are recorded. The completed bounded read-only inventory is in `docs/NHL_TEAM_HISTORY_INVENTORY_2026-10-15.md`: 21,713 regular-season IDs, 21,607 structurally clean pairs, and 2,132 clean tied-score pairs requiring verified final-winner labels. The goalie ZIP covers only 2026. No provider request or model fit occurred. Technical facts are the agent's responsibility; the owner should not be asked to invent statistical thresholds or research API facts. Numerical release criteria remain unresolved, and a data inventory is not a fitted model or approval.

## Current question

**Q9 — Shared direction and bounded implementation:** Does `docs/NHL_FIRST_RELEASE_BRIEF.md` accurately capture the owner's intended first release, so work can begin on its isolated offline team-model experiment?

Recommendation: yes, if the brief matches the owner's intent. The proposed next work audits/reconciles historical labels, builds chronological research baselines and returns an honest benchmark and concrete validation proposal. It does not deploy or approve a live model, activate recommendations, purchase data, increase budgets or run paid odds/AI tests. The remaining production criteria will be settled before approval testing.

**Status: accepted.** The owner answered “Let's go with yes.” This authorizes the bounded isolated experiment described in the brief, not live model approval or paid additions. The shared-understanding checkpoint required by the grilling workflow is satisfied for this phase.

## First experiment completed

The results are in `docs/NHL_TEAM_MODEL_EXPERIMENT_RESULTS_2026-10-15.md`. Four bounded free official requests supplied 13,512 historical regular-season finals and the team reference (3,378,935 bytes); all dates and identities were cross-checked against the cache, with 1,022 shootout winners resolved. The preselected calibrated team model scored 0.24195 Brier and 56.49% winner accuracy across 2,604 held-out games, versus 0.24831 and 54.22% for a home-team reference. The latest season's improvement is uncertain, there are no historical PlayNow prices, and the Utah ID rename exposes a continuity limitation for the next version. No sportsbook edge or production approval was established. Twenty research tests, 220 existing backend tests and byte-identical reproduction passed. There were no paid odds/AI calls, production writes or deployments.

## Unresolved topics

Remaining work: finish the factual data inventory; turn the accepted decisions into a concrete first-release/experiment specification; resolve any owner-facing tradeoff revealed by that inventory; confirm shared understanding before model implementation under the grilling workflow; and propose precise validation criteria before the final test is used for approval. Additional simulation remains deferred unless evidence supports prioritizing it. Provider failure behavior and separation of historical, simulated, paper and actual results must remain explicit in the specification.
