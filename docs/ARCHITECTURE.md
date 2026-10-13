# Architecture and operational contracts

## Data flow

```mermaid
flowchart LR
  NHL[NHL official API] --> W[FastAPI scheduler]
  O[The Odds API] --> W
  P[PandaScore] --> W
  W --> Q[Durable budgets and circuits]
  Q --> DB[(Supabase PostgreSQL)]
  DB --> F[30-minute frozen input vector]
  F --> M[Baseline and approved calibration]
  M --> G[Eight factual gates]
  G --> A[Bounded OpenRouter review]
  A --> R[Rechecked recommendation]
  R --> DB
  DB --> API[Authenticated FastAPI reads]
  API --> N[Next.js private proxy]
  N --> UI[Responsive dashboard and manual ledger]
  UI --> N
```

The two services are independently deployable containers. The database is the durable authority. There is no desktop dependency, browser-triggered ingestion, raw-statistic LLM loop, or automatic wager execution.

## Tables

`fixtures` stores state, source identifiers, probability, required target price, edge, suggested CAD stake, gates, bounded metrics, and the latest risk report. `market_odds` stores normalized per-outcome prices with exact market/selection/line identity. `personal_bets` stores actual ticket prices/stakes, frozen unit size, settlement state, and profit. `account` holds the initial CAD bankroll.

`source_evidence` records provider timestamps separately from observation timestamps. `frozen_snapshots` stores the 15-field vector, original bounded source payloads/provenance, frozen baseline factors, baseline and calibrated prediction, model version, outcome, and Brier error. `model_validation` stores sport-specific calibration parameters and holdout results.

`runtime_limits` stores per-provider Pacific-day reservations and durable outage cooldowns. `evaluation_cycles` stores per-cycle attempt counts and bounded reusable assessment results. `job_leases` prevents duplicate job/evaluation dispatch during restarts or overlapping processes. `audit_log` stores wager actions, evidence verification, and archived snapshots when official start times change.

All application timestamps use timezone-aware `America/Vancouver`. PostgreSQL `timestamptz` stores instants; sessions and application output use Vancouver time. The pinned IANA `tzdata` wheel handles Vancouver's 2026 permanent Pacific time rule and older historical DST dates. The frontend formats the server's Vancouver wall-clock timestamp instead of trusting an outdated browser timezone database.

## Schedule

| Job | Frequency | Limit and recovery |
|---|---|---|
| NHL history and fatigue collection | Daily 04:00 Vancouver | One instance; bounded team count; no target-date games |
| NHL schedule/standings + available personnel details | Hourly | Histories remain daily; at most six imminent game details per cycle |
| PandaScore upcoming/recent matches and rosters | Every two hours | 50 records per endpoint; max six roster tournaments per sport |
| Sportsbook prices | Every two hours | NHL/NBA/MLB/NFL; 48-hour horizon; three exact market types |
| Frozen snapshot | Official start minus 30 minutes | Date trigger; all source observations must precede cutoff; max five seconds processing delay |
| Gate refresh | Every minute | Database only; max 60 imminent fixtures; no background paid loop |
| NHL/esports final outcomes | Every four hours | Bounded unresolved fixtures; final scores never settle tickets automatically |
| Database pulse | Every 48 hours | `SELECT 1`; no uptime guarantee for a free database |
| Raw source and quote retention | Daily | Seven days; frozen source provenance and ticket/audit history survive |

Scheduler jobs coalesce missed interval triggers and allow one concurrent run each. Persistent leases last at least as long as each job's deadline. Exact anchors are never backfilled with post-anchor information. A reschedule archives the old snapshot in the audit log, clears the active snapshot, revokes recommendations, and schedules a new anchor. Startup recovery is bounded and does not replay every missed paid request.

## Hard request boundaries

| Boundary | Default |
|---|---:|
| Odds credits per Pacific day | 120 |
| PandaScore HTTP attempts per day | 120 |
| OpenRouter HTTP attempts per day | 12 |
| NHL HTTP attempts per day | 100 |
| Attempts per HTTP cycle | 3, only for short 429 cooldowns |
| LLM attempts per fixture evaluation cycle | 3, persisted before transmission |
| OpenRouter total deadline | 15 seconds, including retries/body reading |
| Other providers' total cycle deadline | 45 seconds |
| Provider response | 1,000,000 bytes by default, streamed with bounded chunks |
| Backend/proxy mutation body | 16,384 bytes |
| Dashboard login body | 1,024 bytes |
| LLM serialized statistics summary | 3,500 bytes |
| LLM completion | 600 tokens |
| Normal circuit cooldown | 15 minutes |
| Invalid provider authentication cooldown | 24 hours |

Budget reservations commit before a network attempt and are not refunded after errors or crashes. Odds attempts reserve three credits for three markets and fewer than ten explicitly selected bookmakers. Every retry consumes a reservation. Provider quota exhaustion opens a cooldown. Retry-After values over four seconds stop this request cycle and open a cooldown instead of polling rapidly. 500/503 and network/timeout failures trip the circuit and do not retry the same paid POST. Other application/account activity is outside these per-application budgets; provider account spending limits remain necessary for an account-wide currency cap.

## Probability, market, and personnel contracts

The user-specified NHL and CS2 weights live in `model_config.py`. Each factor must be a complete, source-backed normalized home-minus-away difference in [-1,1]. A weighted logit is a deterministic baseline, not a calibrated win probability. The supplied 40/35/15/10 and 40/30/20/10 impacts sum to one. Other sports have no invented baseline.

The fixed vector order is:

1. Home points percentage
2. Away points percentage
3. Home minus away points percentage
4. Home season games
5. Away season games
6. Home recent win rate
7. Away recent win rate
8. Home minus away recent win rate
9. Home recent sample size
10. Away recent sample size
11. Home days rest
12. Away days rest
13. Home minus away days rest
14. Home back-to-back flag
15. Away back-to-back flag

Season samples need five games; recent samples need three to ten. Rest is the number of complete off-days between game dates; zero means a back-to-back. NHL season-schedule responses lack verified end timestamps, so the adapter conservatively uses a next-day boundary and excludes target-date matches; that can omit a recent game rather than leak an overlapping one. Esports history is restricted to the preceding three calendar months and excludes same-date/overlapping matches. Full season statistics are never inferred from a truncated esports history page.

Source age at the logical anchor is at most two hours for schedule, three hours for standings, and 26 hours for team history. Source time and observed time must both precede or equal the anchor. Model-factor observations also precede the anchor and must be at most 30 minutes old. A late anchor remains HOLD.

Recommendation probabilities apply only to complete binary **h2h** markets. Three-way moneyline markets are rejected. Spread/totals quotes are retained for comparison and manual logging, with exact numerical targets; they do not borrow a moneyline probability. A quote with decimal odds <=1.0001 is rejected. `q=1/decimal_odds` is quantized to four decimals using `ROUND_HALF_UP`. Home/away provider joins require exact normalized team names, sport, and a start within five minutes; ambiguous joins are rejected.

Missing starting personnel causes HOLD. Missing execution source otherwise causes WATCH. Missing model validation causes HOLD; insufficient edge causes PASS. The eight factual gates are price, personnel, form, maps/veto, other markets, opposing case, overlap/exposure, and probability. NHL maps/veto is explicitly not applicable and passes as such. A positive AI statement cannot open a missing factual gate; it can only veto or explain existing evidence. Data/exposure changes mark the fixture DIRTY, zero the suggested stake, and require re-evaluation. Data revision is rechecked after the paid review returns.

Kelly uses a 0.25 multiplier, a 1.5% per-ticket bankroll hard cap, a 6% total open-exposure cap, and a duplicate pending-fixture block. Cent rounding never increases a hard cap. The default probability edge threshold is three percentage points. These extra conservative boundaries are configurable in `model_config.py`.

## Browser behavior and settlement

Dashboard reads are at most once per minute while active; they only query the backend database. Hidden tabs abort active reads and stop polling. Fifteen minutes of inactivity stops polling and rendering until user activity resumes. Source age—not time of the browser fetch—determines the five-minute stale badge and suppresses the recommendation shortlist.

The WebGL asset uses custom vertex/fragment shaders, translucent electric-blue wireframe geometry, smooth cursor rotation, and camera field-of-view distortion. Reduced-motion, hidden-tab, and inactivity behavior reduce rendering work. Static PWA identity assets may be cached; session HTML, odds, and ledger responses are never cached. PWA installation needs HTTPS or localhost; offline financial execution is not supported.

Wagers use a request UUID for idempotency and an account row lock to serialize balance changes. Prices are stored as Decimal with eight fractional digits, stakes and unit size as CAD cents. WIN profit is stake times (decimal odds minus one), LOSS is minus stake, and PUSH/VOID/PENDING profit is zero. ROI excludes VOID and PENDING stakes; PUSH remains in settled turnover. Changing settlement recomputes the profit from original ticket values and audits the before/after states. API Decimal values serialize as strings to preserve financial precision.

## Outstanding production verification

This files-only preparation did not mutate Supabase, contact paid providers, create Render services, or upload a repository. Docker and a PostgreSQL server were unavailable locally. GitHub CI includes Linux container builds; the real direct Supabase migration, certificate path, service permissions, provider plan contracts, and live NHL feed access remain to be verified at deployment. A public NHL feed smoke check was rejected by the network/provider during preparation, so it does not establish the live schema. Advanced metric, personnel, and esports odds adapters stay closed until supported contracts are verified.

## Requested delivery files

`backend/main.py` is the complete API entry point and uses the implemented `backend/app/` analytics modules. `backend/requirements.txt` is fully pinned. `frontend/package.json` is pinned to the installed frontend dependencies and declares the build/run/test commands. The database adapter accepts the configured direct Supabase host or an official Session Pooler host with this project's qualified username on port 5432. It rejects transaction pooling and normalizes password encoding without logging credentials. The existing `.env` is unchanged.
