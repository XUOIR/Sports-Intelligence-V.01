# Render pre-deploy connection recovery

The active repository is `XUOIR/Sports-Intelligence-V.01`. Baseline `main` was independently verified against GitHub at commit `ace51a2e9d9af3ac6c7193cf6f3ef7b88f0e2fc4` before editing.

## Verified cause path and minimum fix

`render.yaml` runs `python -m alembic upgrade head` before starting the API. `backend/migrations/env.py` obtains an engine from `backend/app/db.py`, opens a connection, and then runs the schema migration. The supplied `OSError: [Errno 101] Network is unreachable` is consistent with an unreachable direct IPv6 endpoint; live Render logs must establish the actual endpoint used.

The original validator accepted only `db.lagwnyxitcfrdfnuafea.supabase.co` and username `postgres`. Merely replacing the Render secret with a pooler URI would therefore be rejected by the application. The fix also accepts an official `*.pooler.supabase.com` host with username `postgres.lagwnyxitcfrdfnuafea`, port 5432, and database `postgres`. Direct connections remain supported.

TLS certificate verification, async pool limits, connection recycling, Pacific session settings, and migration locking are preserved. Port 6543, other project usernames, and lookalike domains remain rejected. A raw `!` becomes `%21`; an existing `%21` is not double-encoded. No credential values are committed or printed.

Live verification on October 13, 2026 confirmed the original Render pre-deploy network failure and the direct URI in the backend's private configuration. Supabase's Connect panel supplied `aws-1-ca-central-1.pooler.supabase.com:5432`. Updating the URI and deploying `4ee8ce8` cleared the network error, but exposed a second failure: `SSLCertVerificationError: self-signed certificate in certificate chain`. The backend now adds Supabase's official public root CA from `backend/certs/supabase-ca.crt` to its default trust store, retaining certificate-chain and hostname verification. The Docker image already copies the complete backend directory, including this certificate.

## Private configuration and deployment sequence

1. Open Supabase project `lagwnyxitcfrdfnuafea`, choose **Connect → Session pooler**, and copy its exact host and username. Do not guess the pooler host from the Render region. Session mode uses port **5432**.
2. Construct the URI privately with the existing database password, percent-encoded. Its shape is `postgresql://postgres.lagwnyxitcfrdfnuafea:[ENCODED-PASSWORD]@[EXACT-POOLER-HOST]:5432/postgres`. Bracketed fields are descriptive placeholders, not literal connection values. Never paste the populated URI into a public issue or commit.
3. After the tested code is pushed, update **only** `SUPABASE_DB_URL` on the existing Render backend `sports-intelligence-api`. Preserve all other environment secrets, generated tokens, plans, and service settings. Save without deploying an older commit if that option is offered.
4. Deploy the backend from the updated repository commit. Keep the Alembic pre-deploy command enabled. If pre-deploy fails, inspect the specific new error before trying again; do not disable TLS or skip migrations as a workaround.
5. Verify successful pre-deploy completion and read `SELECT version_num FROM public.alembic_version;` through an authorized database connection. The current repository's migration revision is `0001`.
6. Using the backend's actual URL from Render, verify `/health/live` and `/health/ready` return HTTP 200. Readiness also checks table access and backend authentication configuration.
7. Deploy the existing frontend `sports-intelligence-dashboard`. Its backend host and API token are already configured through Blueprint service references. Verify the root page, authenticated dashboard reads, and the existing ledger. Avoid inserting artificial wagers into the production ledger for smoke testing.

## Verification recorded for the fix

The local backend suite passed **72 tests**. Added cases cover session-pooler usernames, all accepted PostgreSQL URI schemes, raw/encoded exclamation marks, rejection of transaction pooling/wrong projects/lookalike hosts, and unchanged pool settings. The full existing route, scheduler-related, analytics, cost-control, and ledger tests passed. No frontend or migration implementation was modified.

The database configuration tests also verify that the actual SSL context requires certificate validation, checks hostnames, and trusts the bundled Supabase root CA.

After the user corrected the private database password, Render successfully deployed `bd0bba1`; pre-deploy completed, both backend health endpoints returned HTTP 200, and Supabase confirmed revision `0001` with CAD 1,100.00 initial capital. Resuming the existing Blueprint created and deployed the dashboard on the configured plan. Its root returned HTTP 200, unauthenticated data requests returned HTTP 401, and login loaded the bankroll and empty wager ledger.

The first NHL startup sync stopped at a separate `ProviderError`: the official `/v1/standings/now` and `/v1/club-schedule-season/TOR/now` endpoints returned HTTP 307 redirects to dated/season-specific URLs. The HTTP client now permits bounded public NHL GET redirects only to HTTPS `api-web.nhle.com`, default port, no URL user information, and the `/v1/` path. Every hop consumes the existing request budget and three-request/total-time caps. Paid API redirects and NHL non-GET redirects remain rejected. Tests cover valid absolute/relative redirects, external/lookalike hosts, HTTPS downgrade, alternate ports, user information, unexpected paths, missing locations, loops, and paid API safeguards.

The full backend suite, including the NHL redirect fix, passed **86 tests**. Redirect tests use mocked responses and make no paid upstream requests.

This local result does not prove that Render's private environment was updated or that a cloud deployment succeeded. Record the actual deployed commit, pre-deploy result, migration revision, and health results after cloud verification.

## Primary documentation

- [Supabase connection methods and Session Pooler URI](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Supabase database CA and SSL verification](https://supabase.com/docs/guides/platform/ssl-enforcement)
- [Render pre-deploy commands](https://render.com/docs/deploys#pre-deploy-command)
