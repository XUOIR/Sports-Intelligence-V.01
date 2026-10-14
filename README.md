# Sports Intelligence V0.1

FastAPI + Supabase PostgreSQL + Next.js, deployed to Render from `XUOIR/Sports-Intelligence-V.01`. Initial bankroll: **CAD 1,100.00**. Unit value: CAD 100.00. Quarter Kelly is capped at 1.5% of current bankroll (initial cap CAD 16.50). The application records manual tickets; it does not place wagers.

## What is implemented

- Private dashboard with bankroll, available capital, exposure, edge-ranked recommendations, source freshness, sport filters, match drawer, custom cursor-reactive WebGL hologram, and mobile layout.
- American/decimal odds logging, repeat-submission protection, manual WIN/LOSS/PUSH/VOID/PENDING corrections, immutable execution unit size, and audited settlement history.
- Async SQLAlchemy pool: `pool_size=10`, `max_overflow=20`, `pool_recycle=1800`, `pool_pre_ping=True`, verified TLS, query timeouts, migrations, and Supabase public-role access restrictions.
- Pacific-aware scheduling, immutable 15-feature anchor snapshots, source age gates, exact market/line matching, audited rescheduling recovery, and chronological calibration with two date embargoes.
- Persistent per-provider budgets, durable fixture attempt caps, bounded HTTP bodies, rate-limit cooldowns, circuit breakers, and 15-second total OpenRouter deadlines.

## Data sources and deliberate locks

The Odds API supplies prices. NHL schedule, standings, team season schedules, game-center details, and final scores come from `https://api-web.nhle.com/v1/`. Advanced factors and confirmed starters require source-backed operator evidence until a suitable feed is verified. The active phase is NHL; CS2 follows, then MLB. PandaScore ingestion is disabled pending the required betting-use license and field contracts. OpenRouter is a final adversarial review after deterministic gates pass, and paid AI remains disabled until both USD budgets and a matching provider-side monthly key limit are set.

The Odds API documents PlayNow as **`playnow_ca`**. The adapter explicitly normalizes it to `playnow`; `bclc` also qualifies. No other bookmaker qualifies as the execution source. A missing, withdrawn, anomalous, future-dated, or stale quote closes the price gate immediately. Pinnacle movement compares the same market, selection, and exact numerical line. A 1.00 percentage point change requests re-evaluation against the PlayNow quotes in that batch, without recursively requesting more odds.

**These are safety constraints, not invented data:**

- NHL starting-goalie confirmation, GSAx, and 5v5 expected-goals evidence have not been verified against a live feed here. A goalie shown in a comparison panel is not a confirmed starter. The adapter remains closed without explicit evidence. An authenticated operator evidence endpoint is available for source-backed confirmations and normalized factors; it records provenance and never changes frozen factors after the anchor.
- PandaScore null, duplicate, short, or missing tournament rosters force HOLD. Plan-dependent player/map/veto fields remain unverified until the actual subscription supports them. Only the first bounded page is ingested; incomplete sample coverage cannot be advertised as full season statistics.
- No esports price key is assumed to exist in The Odds API. Esports stay under observation without a verified PlayNow price adapter. CS2 has baseline weights; VAL/LOL/NBA/MLB/NFL have no invented probability model.
- The 15-feature vector is built when all required standings/history evidence exists. Esports recent win rate is not silently substituted for NHL season points percentage.
- The initial NHL/CS2 weights are **uncalibrated baselines**. RECOMMEND is disabled until an explicitly approved, compatible historical validation exists and all eight factual gates plus adversarial review pass. At least 300 training, 100 calibration, and 100 test records are required *after* date embargoes.
- Odds ingestion runs every two hours. An individual execution quote expires after five minutes. The visible stale warning and sparse recommendation availability between batches are intentional cost/freshness consequences. No hidden faster polling is added.
- The 48-hour `SELECT 1` pulse is implemented, but it is not a guarantee against free-tier Supabase pausing. Choose an appropriate paid database plan for a production uptime requirement.

## Security and existing environment

Secrets are managed in Render. No secrets are included in source, client builds, or committed reports. `.env.example` lists required names. Do not copy live credentials into local QA environments.

Set a random server-only `ADMIN_API_TOKEN` of at least 32 characters and a `DASHBOARD_PASSWORD` of at least 12 characters. The Render blueprint generates these and shares only the internal API token between services. The dashboard uses signed, expiring, HttpOnly, SameSite=Strict cookies, checks mutation origins, limits login attempts, and proxies API requests on the server. No integration token uses `NEXT_PUBLIC_`.

For Render, copy the **Session Pooler** connection from Supabase's Connect panel: `postgresql://postgres.lagwnyxitcfrdfnuafea:[ENCODED-PASSWORD]@[POOLER-HOST]:5432/postgres`. Use the exact pooler host supplied by Supabase; do not infer it from a region. The configured direct endpoint remains supported with username `postgres`. Both modes require port 5432 and database `postgres`. Passwords are percent-encoded before parsing; existing encoding is preserved without double-encoding. Transaction pooling on port 6543, wrong-project usernames, and unrelated hosts are rejected. Never commit `.env`. Only the backend database role should access the tables. Health/liveness endpoints reveal no credentials.

## Local setup

Python 3.12 and Node 22 are the deployment versions. Dependency versions are pinned in `backend/requirements.txt` and `frontend/pnpm-lock.yaml`.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
.\.venv\Scripts\python -m pip install --no-deps -e backend
pnpm --dir frontend install --frozen-lockfile
```

Copy the frontend-only values into `frontend/.env.local`: `BACKEND_URL=http://127.0.0.1:8000`, the same `ADMIN_API_TOKEN`, and `DASHBOARD_PASSWORD`. Keep the integration keys in the root backend `.env`. Run migration only when you intend to modify the configured Supabase database:

```powershell
Set-Location backend
..\.venv\Scripts\python -m alembic upgrade head
..\.venv\Scripts\python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
```

In a separate terminal, run `pnpm --dir frontend dev`. Local scheduling defaults to disabled. Enable `ENABLE_SCHEDULER=true` only in the single service that should ingest live feeds. Container deployment uses `compose.yaml`; it intentionally keeps scheduling off until enabled explicitly.

## Render deployment

1. Commit and push changes to the active repository `XUOIR/Sports-Intelligence-V.01`.
2. In Render, create a Blueprint from `render.yaml`. It declares two always-on `0.5c-512mb` services in Oregon, one instance each. API migrations execute before deploy; the scheduler runs inside the single FastAPI process. Automatic redeployment is disabled.
3. Enter the four integration secrets in Render. Use Supabase's IPv4-compatible Session Pooler on port 5432, with the project-qualified username, rather than a direct IPv6 endpoint or the HTTPS Data API URL. Review your Supabase connection capacity for the requested maximum of 30 backend connections.
4. Retrieve the generated dashboard password from Render's environment settings. The frontend reaches the backend through Render's internal host, and the API token stays on the servers.
5. Verify `/health/ready`, inspect the first successful provider ingestions, verify source field contracts and bookmaker coverage, and confirm the dashboard's data times and HOLD/WATCH behavior before relying on it.
6. Add monitoring, backups, and provider account spending limits appropriate to your uptime requirement. Render's current entry compute pricing is approximately **USD 14/month for two services**, excluding Supabase and third-party accounts. Recheck pricing before deployment.

Docker images run as unprivileged users. A free sleeping web service is inappropriate for a 24/7 scheduler. Native Linux CI builds standalone Next.js output; Windows builds standard production output to avoid elevated symlink requirements.

## Calibration and post-game validation

The NHL final-score loop and available PandaScore completed-match results label genuine frozen snapshots and calculate Brier error. Wager settlement remains manual; a ticket and a model outcome are separate records.

From `backend`, after enough genuine records exist:

```text
python -m app.export_validation --sport NHL --output validation.json
python -m app.calibrate validation.json --sport NHL
python -m app.calibrate validation.json --sport NHL --approve
```

Dates are distinct America/Vancouver dates. With `a=floor(.60D)` and `b=floor(.80D)` using zero-based indices, train uses `[:a]`, calibration `[a+1:b]`, and test `[b+1:]`; dates `a` and `b` are embargoed. The initial deterministic weights are fixed rather than fitted on the training set. Platt calibration uses only the calibration partition, and final evaluation uses the untouched test partition. Approval requires beating a training-prevalence reference on test data. This is an initial validation criterion, not proof of profit or market efficiency.

The import rechecks source ages, the 30-minute horizon, exact vector reconstruction, baseline probability, sport consistency, and duplicate fixtures. Live recommendation gates also reject incompatible models, approval after the snapshot anchor, future test dates, and approvals older than 90 days. Missing samples remain HOLD. Repeatedly tuning against the same test set invalidates its holdout status; reserve new chronological test dates for model revisions.

## Verification

```text
python -m pytest backend/tests -q
pnpm --dir frontend test
pnpm --dir frontend build
python scripts/preflight.py
```

See `docs/QA_REPORT.md` for the exact checks performed and outstanding production verification. `backend/schema.sql` is a review reference; deploy through Alembic. `docs/ARCHITECTURE.md` records contracts, schedule, budgets, and fail-closed decisions.

## Primary references

- [The Odds API V4 contracts and quota costs](https://the-odds-api.com/liveapi/guides/v4/)
- [Documented PlayNow bookmaker key](https://the-odds-api.com/sports-odds-data/bookmaker-apis.html)
- [PandaScore endpoint access by plan](https://developers.pandascore.co/docs/plan-reference)
- [Supabase connection methods](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Render blueprint specification](https://render.com/docs/blueprint-spec) and [pricing](https://render.com/pricing)
- [B.C. Pacific time change in 2026](https://archive.news.gov.bc.ca/releases/news_releases_2024-2028/2026CITZ0009-001073.htm)

## Failed Render pre-deploy recovery

See [deployment recovery](docs/DEPLOYMENT_RECOVERY.md). The Alembic pre-deploy step is preserved; the connection validator now supports this project's Session Pooler without changing routes, scheduling, analytics, or the dashboard.
