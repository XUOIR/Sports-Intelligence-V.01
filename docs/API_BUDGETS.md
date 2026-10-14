# Provider allowances, cost controls, and data readiness

Published prices checked October 13, 2026. Actual account allowances come from authenticated provider metadata or the vendor billing page. The dashboard's **Check provider allowances** action checks the deployed credentials. An application limit is never presented as the provider's plan allowance.

The existing credentials were checked without paid odds or AI generation. Render verifies Odds API used 3 / remaining 497 (period allowance 500), PandaScore's hourly used + remaining sum of 1,000, and OpenRouter funded US$10 / used US$0. The user confirmed Odds API is the Free tier. OpenRouter's existing key was changed, with user authorization, to a US$3 limit that resets monthly. The saved setting was verified after reloading the account page. This limit controls spending; it is not a monthly credit grant. Supabase's authenticated organization dashboard confirms the Free plan, 27 MB / 500 MB database use, 0.00 / 5 GB egress for the current billing cycle, and 0 / 1 GB file storage. No plan was purchased or changed.

| Provider | Billing unit | Published allowance / price | Account verification |
| --- | --- | --- | --- |
| The Odds API | Credits per billing period | Free 500/month; 20,000/month US$30; 100,000/month US$59 | Free `/sports` metadata returns credits remaining and used. Their sum is the current period allowance; invoice confirms plan price and renewal date. |
| PandaScore | Requests per hour and subscription per game | Fixtures/context 1,000/hour; historical/live plans 10,000/hour | API headers expose remaining requests, sometimes the limit; the account dashboard confirms the plan. There is no monthly credit wallet. |
| OpenRouter | Prepaid USD; tokens charged per model | `deepseek/deepseek-chat`: US$0.32/million input and US$0.89/million output tokens at catalogue verification | Current-key metadata exposes key caps and usage. Wallet metadata can require a management key; use the billing page when unavailable through the existing key. No new broad credential is required. |
| Supabase | Database capacity, egress, storage, and monthly active users | Free: 500 MB database, 5 GB egress/month, 1 GB file storage, 50,000 monthly active users; unlimited API requests within resource constraints | Authenticated organization usage dashboard; there is no request-credit wallet. Database/file capacities do not reset monthly. |
| NHL public API | Public requests | No monthly credit wallet or verified published service-level allowance | Application request ceilings are protective local limits, not an NHL entitlement. |

Sources: [Odds API plans](https://the-odds-api.com/), [Odds API quota costs](https://the-odds-api.com/liveapi/guides/v4/), [PandaScore limits](https://developers.pandascore.co/docs/rate-and-connections-limits), [OpenRouter current key](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key), [OpenRouter wallet](https://openrouter.ai/docs/api/api-reference/credits/get-credits), [OpenRouter live model catalogue](https://openrouter.ai/api/v1/models), [Supabase pricing](https://supabase.com/pricing).

## Usage estimates and proposed budgets

The configured odds batch requests two bookmakers and three markets. At the documented <=10-bookmaker grouping, this is **3 credits per sport batch**, covering all returned fixtures. Odds now refresh **manually only**, with at most **five provider attempts in a rolling 24-hour window**. That is at most 465 credits over 31 days, leaving room below the 500-credit free allowance. Failed and uncertain attempts count, all prior automatic calls inside the window count, and the next slot opens exactly 24 hours after the relevant attempt. Reloading the page or redeploying does not reset the ledger. The calendar-day credit ceiling is 15; the calendar-month ceiling is 500, with provider remaining-credit checks as a second boundary.

The manual endpoint accepts a durable UUID. The browser saves it before sending and checks its status after a dropped response instead of repeating the external request. Only one odds refresh can be in progress. A crashed or unconfirmed refresh requires an explicit provider resume; resuming does not refund credits or restore its slot. Empty NHL schedules do not use a slot. Both recurring and startup odds scheduler jobs are removed.

Two-hour prices cannot support continuously fresh five-minute execution gates. A later NHL + MLB scenario of five-minute batches during six active hours daily, plus two-hour batches in the other 18 hours, is approximately **14,580 credits per 30-day month** (12,960 active + 1,620 quiet), before a safety margin. This is a planning scenario, not an enabled schedule. Candidate-only pre-game refreshes may reduce usage substantially, once advanced inputs and model validation are available. We have not verified a CS2 odds key or PlayNow CS2 coverage, so CS2 is excluded from that estimate.

At the verified DeepSeek rates, 3,000 input + 600 output tokens cost **US$0.001494/review**. Thirty reviews/day for 30 days cost approximately **US$1.3446**, excluding funding fees/taxes and rate changes. The user approved a **US$3/month maximum**. The Render configuration enforces **30 reviews/day, US$0.30/day, US$3/month**, with US$0.01 conservatively reserved per review. The existing OpenRouter key has a matching US$3 monthly provider cap. At this reservation size, up to 300 reviews can be admitted per month, even if actual token charges are lower; missing or failed cost confirmations never release the reservation. AI reviews should run only for changed, fully verified candidates, never on every UI poll or for raw sports-data synchronization.

PandaScore hourly capacity is not a monthly allocation: 1,000/hour mathematically permits 720,000 calls in a 30-day month, but unused hours do not carry over, endpoint access still depends on the plan, and burst limits apply. Its published statistics subscriptions also exclude betting-related use. [Pricing](https://www.pandascore.co/pricing) and [terms, Article 6.4](https://www.pandascore.co/terms-and-condition) require confirming an appropriate betting-use arrangement before CS2 odds-related processing. No license purchase or vendor message is authorized by this document.

## Safeguards implemented

- Transactional daily/monthly reservations precede every paid call. Requests have durable identities and survive process restarts. Concurrent instances cannot admit the same request twice.
- Paid calls have one transport attempt. Authentication errors, rate limits, server failures, malformed responses, cancellation, and uncertain timeouts stop that provider until explicit operator resume. Failed or uncertain reservations are retained, never treated as refunds.
- AI additionally requires a provider-side monthly key cap, bounded prompt/output, price ceilings, JSON output, and a three-review lifetime cap per fixture. Changed quote IDs alone do not generate a new review.
- The authenticated dashboard exposes an emergency pause, provider status, local budgets, and explicit cached account checks. Reading the dashboard never calls an external provider. Account checks request metadata only and finish within a bounded deadline.
- NHL history is cached with its original observation time; empty NHL schedules do not trigger odds batches. Five-attempt rolling limits include failures and cannot be reset by provider resume. Other sports remain inactive.

A provider can bill a request before a network failure becomes visible. These controls bound exposure and prevent automatic repetition; they cannot promise reimbursement or undo an already accepted call. A pause stops new admissions, not an already in-flight request. Local calendar budgets reset in America/Vancouver and may differ from the vendor's billing renewal date; provider quota checks provide a second boundary.

## NHL sources and recommendation prerequisites

Keep the official NHL API for schedules, standings, rosters, rest, and results. Its community references are useful discovery aids, not verified contracts for starting-goalie confirmation or advanced factors. PandaScore is an esports source and does not replace NHL data.

[MoneyPuck's published download files](https://moneypuck.com/data.htm) are a candidate for game-by-game 5v5 expected goals and goalie GSAx, with correct situation filters and [metric definitions](https://www.moneypuck.com/glossary.htm). Free use is subject to non-commercial use and attribution; commercial use needs permission. No adapter or unapproved website scraping is enabled. Confirmed starters still need an explicit, timely source. The dashboard now provides an evidence-entry form requiring a public source URL, source observation time, goalie names, and all normalized factors; it cannot backfill factors after the T−30 anchor.

Recommendations remain HOLD until source-backed advanced factors, current starters, fresh complete PlayNow prices, genuine frozen inputs, and an approved compatible historical validation pass all eight gates. The minimum is 300 training + 100 calibration + 100 test records after chronological date embargoes. Historical data without real observation times cannot be relabeled as genuine frozen snapshots. No neutral inputs, invented probabilities, or made-up historical results are supplied.


## Render build allowance and public addresses

The authenticated Render workspace is Hobby, with 500 included Starter pipeline minutes per month. At the account check it showed 6 minutes used and a US$0 additional pipeline spend limit. Deployments consume build/pre-deploy minutes rather than a fixed monthly deployment-count allowance. Extra Starter minutes cost US$5/1,000, but the current US$0 spend limit prevents purchasing extras. Exhaustion stops builds; existing successful deployments continue running. [Render pipeline documentation](https://render.com/docs/build-pipeline).

The dashboard is `https://sports-intelligence-dashboard.onrender.com/`. The backend's bare root previously returned FastAPI `{"detail":"Not Found"}` because it had no root route. Its GET/HEAD root now redirects to the dashboard; health and private API routes retain their behavior.
# Live NHL scores (October 13, 2026)

The match sidebar reads a shared database cache every 30 seconds while visible and active. A separate free NHL score worker polls about every 30 seconds during live games, every 60 seconds near puck drop, every 5–15 minutes on quiet current days, hourly for requested future dates and daily for finished historical dates. A date request only queues a bounded day; it never calls odds or AI. Dates are limited to ±7 days.

`NHL_SCORE_DAILY_REQUESTS=1500` caps score transport attempts per Vancouver day, independently of the existing `NHL_DAILY_REQUESTS=300` statistical cap. A typical six-hour live window uses about 720 shared score calls, plus quiet-day and selected-date requests; this is a workload estimate, not a published NHL allowance. Multiple tabs share the same cache and leases. Each score refresh has one transport attempt, a 15-second deadline, bounded response size, strict payload validation and a failure cooldown of at least 15 minutes. Long Retry-After values are respected. Failed refreshes retain successful scores and their original timestamps; freshness expires and PLAY labels fail closed. No automatic metered fallback is configured.

Provider controls and allowances are now on the private Settings page. The development readiness checklist is on the private Development page and is temporary.
