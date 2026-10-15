# A practical NHL release without a universal lineup dependency

Proposal prepared October 15, 2026. This is a response to the owner's request to reconsider the approach before buying more data. No model, verification gate, budget, provider or deployment was changed.

## Recommendation

Keep the current application, data adapters, accounts, dashboard, source evidence, bankroll and spending protections. Develop a **separate, versioned team-strength model** using reliably available pregame inputs. Evaluate it before making confirmed goalies, full line combinations or paid news ingestion a dependency for every useful forecast.

The current architecture can support this. The principal change is the model's information contract and the evidence required to approve that particular model, not a rewrite of FastAPI, Next.js or hosting.

This does not establish that a cheaper model will beat the market. It gives us a testable route to find out, without making a new subscription the next prerequisite. A functional analytics product, calibrated probabilities and a profitable wagering strategy are different milestones.

## What the current source actually does

Reviewed in the active repository:

- `backend/app/model_config.py` fixes NHL factor weights at 40% goalie/personnel, 35% expected goals, 15% rest/fatigue and 10% venue/special teams.
- `backend/app/maths.py` transforms that fixed weighted score into a probability. This is not a fitted team-strength model. Calibration alone does not learn all feature weights or prove the selected features are useful.
- `backend/app/nhl_factors.py` requires both confirmed starters, matching recent goalie statistics and timely pre-anchor source evidence.
- `backend/app/engine.py` freezes at T−30 and leaves the NHL baseline unavailable if those normalized factors cannot be produced. It also saves a 15-feature descriptive history vector separately.
- `backend/app/readiness.py` requires a compatible approved model, genuine saved snapshot, current gates and matching goalie identities. The existing training/calibration/test minimums are 300/100/100 after partitioning; they are minimums, not proof of sufficient evidence.

The existing safeguards correctly prevent us from presenting that goalie-dependent model as verified with missing goalie inputs. The dependency comes from the chosen model. A model intentionally trained without fixture-specific confirmed starters has a different input contract and must be evaluated on that basis.

There is a relevant primary-source example: [MoneyPuck's model description](https://moneypuck.com/about.htm) says its pregame model combines team results, scoring chances and goaltending; each goalie's contribution to the team goaltending rating is weighted by games played. This supports the feasibility of testing team-level goaltending information. It does not establish accuracy for our implementation, give us permission to scrape their forecasts, or prove that any particular fixture's starter is known.

## Three stages with separate evaluation

| Stage | Inputs and output | Evaluation and release condition |
| --- | --- | --- |
| Team forecast | Earlier completed games, opponent-adjusted team strength, home/away, schedule and rest. Optional team-level xG only after provenance/version audit. Produces a probability under ordinary lineup uncertainty. | Historical chronological evaluation, calibration checks and genuine forward observation. New model version and approval rules; cannot inherit the current model's approval. |
| Goalie scenarios / adjusted forecast | A separately tested model using available goalie history and a named, sourced current starter; or explicitly labeled alternative goalie scenarios. | Demonstrated improvement over the team model, adequate sample and honest evidence times. If starter evidence is absent, retain the team forecast rather than pretending the adjusted forecast exists. |
| Decision support | Approved model output compared with a current matching PlayNow price, plus current risk/exposure checks. | Price, market rules, model applicability and uncertainty criteria pass. A probability alone does not create an actionable play. |

These stages should appear distinctly in the UI: which model produced the number, what information it used, whether starters are confirmed, when the price was observed, and why a candidate is or is not actionable. Team forecasts must not receive a confirmed-lineup label.

Goalie projections can remain visible as contextual information. Do not substitute an unvalidated heuristic's guessed starter for a confirmation or invent numeric starter-selection probabilities. Any probability-weighted combination of goalie scenarios needs separately assessed selection probabilities. A sensitivity range is not automatically a statistically calibrated confidence interval.

## The first experiment I would run

1. **Specify one target:** NHL pregame two-way moneyline, including overtime/shootout where the selected PlayNow market does. Exclude regulation-only markets, props, parlays and other sports from this release experiment.
2. **Audit historical coverage before training.** Inventory existing cached data. Obtain additional allowed historical inputs only through bounded downloads/admitted requests if needed. Record original provider, season, event time, collection time, version and checksum. Do not promise a sample size before this audit.
3. **Start with a simple opponent-adjusted rating model.** Compare an Elo-style model and a small regularized logistic model using earlier results, home ice, rest and rolling team strength. Learn or tune parameters on the training partition. Keep a simple home-win-rate reference. Avoid a large feature set before it demonstrates added value.
4. **Reconstruct features sequentially.** Each game's inputs use only earlier completed games. No final-season standings, current game's goalie/results, future roster knowledge or fitted preprocessing from the test period. Reconstructed historical research remains labeled reconstructed; it is not an originally saved live forecast.
5. **Audit advanced data separately.** MoneyPuck [published downloads](https://moneypuck.com/data.htm) are available for attributed noncommercial use; other use requires inquiry. Its current [xG description](https://moneypuck.com/about.htm) says the 2026–27 model was trained on 2023–24 through 2025–26 shots. Applying retrospectively revised xG to those seasons needs a look-ahead audit. Omit that feature from the initial experiment if a suitable historical version cannot be established.
6. **Evaluate forward in time.** Split by game date, preserve embargoes, fit calibration on a separate earlier partition, lock choices before the untouched final test, and quantify uncertainty rather than choosing a model because one test looks good. No lowered record minimum or synthetic approval is proposed. [Time-series evaluation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) and [probability calibration](https://scikit-learn.org/stable/modules/calibration.html) documentation explain the relevant separation principles; use date-grouped logic appropriate to fixtures.
7. **Report the right outcomes.** Brier score and log loss, reliability plots, sample sizes and performance by season/probability band. A lower Brier score alone does not establish perfect calibration. Compare against a simple reference and, where genuine matched historical prices are available, a time-matched margin-adjusted market benchmark. Without historical PlayNow quotes, do not claim a PlayNow ROI backtest.
8. **Run genuine forward observation.** Save immutable predictions, input manifests, model version, cutoff/creation times and actual observed quotes. Settle outcomes automatically only from verified finals; personal ticket settlement remains its own workflow. Record failures and missing inputs as outcomes of the system's operation, not hidden exclusions.

The first deliverable is an offline benchmark report: data coverage, test design, measured scores, uncertainty, failure modes and a clear go/no-go conclusion. A failed experiment is useful evidence to improve the model or narrow the product; it is not a reason to label poor probabilities as verified.

## How the daily dashboard would function

- Collect slow-changing team statistics on the existing bounded schedule. Historical rolling features do not need 30-second paid calls.
- Keep scores on the existing shared free-source path, subject to its admission limits and failure cooldowns.
- Publish a team forecast only from an approved compatible model with the required fresh inputs. Show descriptive statistics while the model remains in research.
- Add starter confirmation and injury news when available. Preserve every update and correction. A later forecast gets a new version/time; it never overwrites an earlier prediction or repairs a missed checkpoint retrospectively.
- Make prices independently usable: show book, market/settlement rules, selection, price and real source timestamp. A stale saved price is still a saved price, not a current execution quote.
- Request a protected odds refresh when a user evaluates a credible candidate, within existing limits, or use a deliberately implemented source-backed manual quote workflow. Never refresh merely to make a badge green.
- Calculate signed probability edge as `p - 1 / decimal_odds` and expected return per unit as `p * decimal_odds - 1`, using an approved probability and the matching market. The two measures are not interchangeable.
- Keep zero-stake observation available. Enable any recommendation only under predeclared model-specific applicability, price and risk criteria. Missing high-impact news may still justify blocking a decision even when a team forecast is available.

The existing model must retain its current gates. A new model requires version-aware evidence, readiness and audit paths; simply changing the global personnel check to true would be an incorrect implementation.

## AI and spending

No LLM call is needed to calculate a fitted model's probability, compare a price or save a result. Local inference of a small fitted model can run in the existing backend. Additional hosting capacity cannot be guaranteed before measurement, but a separate paid AI service is not an inherent requirement.

AI can later summarize source-linked facts or propose structured extraction for review. It should not certify a team's lineup, invent an injury update or override statistical validation. Model computations and deterministic data checks must continue to work when AI is unavailable or its spending limit is exhausted.

**Incremental data/LLM subscription target for the first offline experiment: $0**, subject to the coverage and permitted-use audit. This is not a claim that public feeds have guaranteed availability, that every desired historical feature is already cached, or that a commercial product can use noncommercial data without permission. Existing hosting costs remain. No current budget was raised.

## What this changes and what remains uncertain

This proposal makes the next decision an empirical model test using obtainable inputs. It keeps the source/provider review available for later improvements, and avoids an architecture restart or a purchase based on marketing.

It cannot guarantee a profitable edge, erase unexpected lineup changes, provide a valid ROI history without historical prices, or create a historical original-publication archive. It can determine whether a simpler forecast is useful, and then measure whether better goalie/news data earns its cost.

If the owner requires every approved play to have confirmed starters, retain that requirement for plays and use the team model for earlier forecasting/ranking. If a model designed for unconfirmed lineups is considered for recommendations, its criteria and labeling must be explicitly designed, evaluated and approved as a new contract. That is a product/model decision, not a concealed relaxation of the current implementation.
