# Provider allowances, cost controls, and data readiness

Published prices checked October 13, 2026. Actual account allowances come from authenticated provider metadata or the vendor billing page. The dashboard's **Check provider allowances** action checks the deployed credentials. An application limit is never presented as the provider's plan allowance.

The existing credentials were checked without paid odds or AI generation. Render verifies Odds API used 3 / remaining 497 (period allowance 500), PandaScore's hourly used + remaining sum of 1,000, and OpenRouter funded US$10 / used US$0. The user confirmed Odds API is the Free tier. OpenRouter's current key cap is US$100 with no recurring reset; this is not a monthly allowance. Supabase's authenticated organization dashboard confirms the Free plan, 27 MB / 500 MB database use, 0.00 / 5 GB egress for the current billing cycle, and 0 / 1 GB file storage. No plan was purchased or changed.

| Provider | Billing unit | Published allowance / price | Account verification |
| --- | --- | --- | --- |
| The Odds API | Credits per billing period | Free 500/month; 20,000/month US$30; 100,000/month US$59 | Free `/sports` metadata returns credits remaining and used. Their sum is the current period allowance; invoice confirms plan price and renewal date. |
| PandaScore | Requests per hour and subscription per game | Fixtures/context 1,000/hour; historical/live plans 10,000/hour | API headers expose remaining requests, sometimes the limit; the account dashboard confirms the plan. There is no monthly credit wallet. |
| OpenRouter | Prepaid USD; tokens charged per model | `deepseek/deepseek-chat`: US$0.32/million input and US$0.89/million output tokens at catalogue verification | Current-key metadata exposes key caps and usage. Wallet metadata can require a management key; use the billing page when unavailable through the existing key. No new broad credential is required. |
| Supabase | Database capacity, egress, storage, and monthly active users | Free: 500 MB database, 5 GB egress/month, 1 GB file storage, 50,000 monthly active users; unlimited API requests within resource constraints | Authenticated organization usage dashboard; there is no request-credit wallet. Database/file capacities do not reset monthly. |
| NHL public API | Public requests | No monthly credit wallet or verified published service-level allowance | Application request ceilings are protective local limits, not an NHL entitlement. |

Sources: [Odds API plans](https://the-odds-api.com/), [Odds API quota costs](https://the-odds-api.com/liveapi/guides/v4/), [PandaScore limits](https://developers.pandascore.co/docs/rate-and-connections-limits), [OpenRouter current key](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key), [OpenRouter wallet](https://openrouter.ai/docs/api/api-reference/credits/get-credits), [OpenRouter live model catalogue](https://openrouter.ai/api/v1/models), [Supabase pricing](https://supabase.com/pricing).

## Usage estimates and proposed budgets

The configured odds batch requests two bookmakers and three markets. At the documented <=10-bookmaker grouping, this is **3 credits per sport batch**, covering all returned fixtures. NHL-only every two hours costs at most 12 × 3 × 31 = **1,116 credits per 31-day month**, before failures or skipped empty schedules. The protective application ceiling is **500/month and 120/day**, matching the confirmed free monthly allowance. Five hundred credits support only 166 complete three-credit batches, so they cannot fund that full-month schedule. These ceilings do not purchase credits or increase the subscription.

Two-hour prices cannot support continuously fresh five-minute execution gates. A later NHL + MLB scenario of five-minute batches during six active hours daily, plus two-hour batches in the other 18 hours, is approximately **14,580 credits per 30-day month** (12,960 active + 1,620 quiet), before a safety margin. This is a planning scenario, not an enabled schedule. Candidate-only pre-game refreshes may reduce usage substantially, once advanced inputs and model validation are available. We have not verified a CS2 odds key or PlayNow CS2 coverage, so CS2 is excluded from that estimate.

At the verified DeepSeek rates, 3,000 input + 600 output tokens cost **US$0.001494/review**. Thirty reviews/day for 30 days cost approximately **US$1.3446**, excluding funding fees/taxes and rate changes. A proposed conservative allowance is **30 reviews/day, US$0.30/day, US$10/month**, with US$0.01 reserved per review. **This proposal is not enabled or approved.** Current AI daily/monthly USD caps are zero. AI reviews should run only for changed, fully verified candidates, never on every UI poll or for raw sports-data synchronization.

PandaScore hourly capacity is not a monthly allocation: 1,000/hour mathematically permits 720,000 calls in a 30-day month, but unused hours do not carry over, endpoint access still depends on the plan, and burst limits apply. Its published statistics subscriptions also exclude betting-related use. [Pricing](https://www.pandascore.co/pricing) and [terms, Article 6.4](https://www.pandascore.co/terms-and-condition) require confirming an appropriate betting-use arrangement before CS2 odds-related processing. No license purchase or vendor message is authorized by this document.

## Safeguards implemented

- Transactional daily/monthly reservations precede every paid call. Requests have durable identities and survive process restarts. Concurrent instances cannot admit the same request twice.
- Paid calls have one transport attempt. Authentication errors, rate limits, server failures, malformed responses, cancellation, and uncertain timeouts stop that provider until explicit operator resume. Failed or uncertain reservations are retained, never treated as refunds.
- AI additionally requires a provider-side monthly key cap, bounded prompt/output, price ceilings, JSON output, and a three-review lifetime cap per fixture. Changed quote IDs alone do not generate a new review.
- The authenticated dashboard exposes an emergency pause, provider status, local budgets, and explicit cached account checks. Reading the dashboard never calls an external provider. Account checks request metadata only and finish within a bounded deadline.
- NHL history is cached with its original observation time; empty NHL schedules do not trigger paid odds batches. Other sports remain inactive.

A provider can bill a request before a network failure becomes visible. These controls bound exposure and prevent automatic repetition; they cannot promise reimbursement or undo an already accepted call. A pause stops new admissions, not an already in-flight request. Local calendar budgets reset in America/Vancouver and may differ from the vendor's billing renewal date; provider quota checks provide a second boundary.

## NHL sources and recommendation prerequisites

Keep the official NHL API for schedules, standings, rosters, rest, and results. Its community references are useful discovery aids, not verified contracts for starting-goalie confirmation or advanced factors. PandaScore is an esports source and does not replace NHL data.

[MoneyPuck's published download files](https://moneypuck.com/data.htm) are a candidate for game-by-game 5v5 expected goals and goalie GSAx, with correct situation filters and [metric definitions](https://www.moneypuck.com/glossary.htm). Free use is subject to non-commercial use and attribution; commercial use needs permission. No adapter or unapproved website scraping is enabled. Confirmed starters still need an explicit, timely source. The dashboard now provides an evidence-entry form requiring a public source URL, source observation time, goalie names, and all normalized factors; it cannot backfill factors after the T−30 anchor.

Recommendations remain HOLD until source-backed advanced factors, current starters, fresh complete PlayNow prices, genuine frozen inputs, and an approved compatible historical validation pass all eight gates. The minimum is 300 training + 100 calibration + 100 test records after chronological date embargoes. Historical data without real observation times cannot be relabeled as genuine frozen snapshots. No neutral inputs, invented probabilities, or made-up historical results are supplied.
