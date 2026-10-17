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

Runtime production results and any resulting corrective change will be recorded
after the guarded diagnostic completes. No full-file retry or successful import
is claimed by these preparation checks.
