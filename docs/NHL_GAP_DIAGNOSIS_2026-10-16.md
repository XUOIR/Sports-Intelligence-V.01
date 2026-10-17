# NHL gap diagnosis — October 16, 2026

The owner asked whether another paid odds refresh would be worthwhile and
authorized fixing the remaining gaps. The existing three-credit batch already
captured paired prices for both current forecasts and one genuine simulated
position. Another batch cannot resolve an absent approved production model or
a failed advanced-statistics import, so no new paid refresh was issued.

## Bounded production-source diagnostic

The previous import failure retained only `ValueError`. Local HEAD responses
cannot establish what the Render service received. A private, once-per-day
source diagnostic now uses the same allowlisted URLs, user agent and header
validation as the real importer. It reads one raw chunk of at most 8 KiB from
each source, checks the gzip/ZIP sample, then closes the response. This is a
transport test, not a complete-file import or proof of reconciliation.

The diagnostic reserves 2 MB against the existing monthly transfer budget to
cover HTTP/TCP read-ahead. This conservative reservation is retained even on
success. The durable `moneypuck-probe:<Pacific date>` counter admits at most
one two-source check per day, independent of the unchanged one-import daily
counter. Neither failed/uncertain diagnostics nor reloads can readmit it.
The operation cannot reset import admission, change cached statistics, confirm
starters, create probabilities, approve a model or use odds/AI credits.

The authenticated POST queues bounded background work; subsequent UI polling
reads saved results only. Redirects remain disabled, upstream response bodies
are never displayed, and error text is restricted to fixed validation messages.
Settings shows per-source HTTP/sample results separately from import readiness.
Normal data reads do not initiate this diagnostic.

All 247 backend tests and the production frontend build/type checks passed.
New tests cover private-route access, durable duplicate rejection, monthly-cap
rollback, one-chunk termination, unchanged import/cache state and untrusted
body redaction. Existing model and spending tests remain intact. No frozen
paper inference/collection source file or fitted model bundle changed.

## Verified production result

Commit `f4559bc` is live on both Render services. The single admitted check at
17:04:38 Pacific returned HTTP 302 for the team file and HTTP 403 for the goalie
file. Neither source passed the import transport contract. The old 09:00 failure
did not preserve its response details, so this establishes the present failure
without claiming the exact earlier response is known. Local HEAD requests for
the identical public URLs returned HTTP 200 and current publication headers.

The probe reservation brought October's protected transfer total to 114,785,063
bytes. The regular daily import remains consumed at one; the diagnostic is also
consumed at one. No odds or AI request was issued. The current advanced cache
remains October 15, verified through October 14. A successful small diagnostic
would not have been a full import; this one did not succeed even at transport.

## Tested manual recovery fallback

`app.nhl_statistics_recovery` is an operator command, not a scheduled or web
fallback. It runs the same official public downloads, header/byte/time limits,
full-file parser and NHL result reconciliation from the operator's computer.
It does not follow redirects, change user agents, use a proxy or alternate
source, bypass access controls, approve a model, confirm a starter or call a
paid provider. A source denial still stops the attempt.

Admission requires today's consumed failed import, a failed source diagnostic
no more than one hour old that actually recorded a redirect/access denial, no
current-day cache, and available transfer capacity. It reserves another full
45,943,040 bytes against the existing monthly limit before downloading anything.
The separately audited `moneypuck-manual-recovery:<Pacific date>` limit permits
only one explicit recovery per day, including failures. It does not clear the
original daily admission. Successful complete validation releases only known
unused capacity, exactly as the normal importer does; uncertain failures retain
the full reservation. Successful data records `operator_public_download` as
its acquisition method, with genuine source observation/publication timestamps.

All 253 backend tests pass. The six recovery tests cover prerequisite/freshness
checks, one-attempt enforcement, shared-cap rollback, unchanged daily admission,
complete reconciliation, paid-call absence, failed-cache retention and provenance.
The frozen paper model/collector/bundle remain unchanged.

Before running recovery, a read-only local database check failed authentication
(`InvalidPasswordError`). No recovery was admitted or download issued. The user
was asked to update only the local ignored `.env` database URL from the working
Render configuration, without sharing secrets in chat. This is a required local
credential repair, not a request to increase any allowance.

After that repair, run from `backend/` in PowerShell:

```powershell
$env:ENABLE_NHL_ADVANCED_STATS='true'
..\.venv\Scripts\python.exe -m app.nhl_statistics_recovery --run
```

The command refuses a stale diagnostic rather than bypassing its guard. If the
one-hour prerequisite has expired, wait for the next day's available diagnostic
or resolve provider access; do not reset counters. An unattended long-term fix
still requires MoneyPuck to support this hosting network or an explicitly
approved reliable data source. The manual recovery is a temporary operational
fallback, not a claim that Render source access has been repaired.

## Other gaps that fresh odds cannot repair

The odds-independent paper model has genuinely saved forecasts and today's
paired price observations already produced one simulated position. Production
model approval remains absent. Restoring descriptive xG/GSAx does not validate
that different production model, manufacture historical inputs, approve an AI
audit or transform paper results into real betting recommendations. The next
scientific step remains collecting and evaluating the frozen forward cohort;
there is no honest instant code change that establishes an edge over sportsbooks.
