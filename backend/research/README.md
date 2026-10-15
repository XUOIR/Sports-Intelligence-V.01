# Offline NHL team research

This package is isolated from the application. No production imports it, and it does not read application configuration, credentials, Supabase or provider clients. It cannot approve a production model or change a bankroll.

The v1 experiment is frozen research. Its measured results and known limits are in `docs/NHL_TEAM_MODEL_EXPERIMENT_RESULTS_2026-10-15.md` at the repository root. Changing the model after viewing those test scores creates a new research version; it does not preserve an untouched final test.

## Dependencies

Python 3.12 and `numpy==2.3.5` are sufficient. The experiment used the existing bundled Python/NumPy runtime; no packages were installed. `research/requirements.txt` is an optional offline dependency file. Production requirements remain unchanged. Tests use the standard-library `unittest` runner.

From `backend`:

```powershell
python -m unittest discover -s research/tests -v
```

Use the Python executable containing the pinned NumPy package. The application's separate environment can run its existing tests with `python -m pytest tests -q`.

## Source acquisition, explicit and bounded

`nhl_history_fetch.py` is the only module here with network access. It allows only the public official NHL `game`, `game/meta` and `team` routes on `https://api.nhle.com/stats/rest/en/`. It has no API-key support, retries, redirects, paid hosts or scheduler.

The local SQLite admission ledger reserves an attempt and the maximum byte exposure before access. Successful cache reads verify the hash and issue no request. Failed, crashed or uncertain attempts remain consumed and cannot silently retry. Limits are ten total requests per experiment cache, 12 MB per request and 48 MB aggregate reserved/reconciled bytes. These are additional research safeguards; this collector does not change any application's live limits. Do not create fresh caches to evade exhausted admissions.

This run used four requests, 3,378,935 bytes, zero paid requests:

1. A two-row 2025-season schema check.
2. The first 10,000 regular-season game rows for `season>=20152016 and season<=20252026 and gameType=2`, sorted by ID.
3. A 62-row team-ID reference.
4. The remaining 3,512 game rows.

The three full/reference sources and their hashes are in the run manifest; the schema probe is also retained in the ledger. No web API per-game requests were needed. Acquiring different source coverage is a separate explicit decision, not part of the model runner.

## Reproduce the frozen local experiment

The existing cache lives under the ignored `artifacts/nhl-team-model-experiment/sources/nhl` folder. The MoneyPuck archive remains the already-downloaded source; it is used for identity/date reconciliation, not model features or winner labels.

Run from `backend`, with a **new** output directory:

```powershell
python -m research.nhl_experiment --plan research/plans/nhl-team-v1.json --nhl-cache ../artifacts/nhl-team-model-experiment/sources/nhl --teams ../artifacts/nhl-low-cost-provider-research/moneypuck-offline-test/compressed-2026-10-14/all_teams.csv --output ../artifacts/nhl-team-model-experiment/new-reproduction
```

The runner has no network access. It verifies cached source hashes, official final states, complete cached pagination, identities/dates and the input contract. It writes an immutable pre-evaluation manifest before fitting/selection, then fits only on earlier partitions. Elo/recent game history updates after each completed calendar date; parameters and calibration never refit on the final test. Same-day outcomes cannot inform same-day features.

Outputs:

- `pre_evaluation_manifest.json`: declared plan, source and executable-code hashes, acquisition accounting and environment.
- `prepared_games.json`: reconstructed official outcomes, including explicit shootout handling.
- `fitted_before_test.json`: selected configurations, fitted coefficients/calibration and development scores.
- `heldout_predictions.csv`: the predeclared final-test probabilities, outcomes and latest input dates.
- `report.json`: coverage, scores, reliability, uncertainty, limitations and explicit false production/market-edge flags.

The original run and a second identical run produced byte-identical prepared data, fitted parameters and prediction CSVs. Independent CSV metric verification and additional season diagnostics are saved in `run-v1/post_evaluation_diagnostics.json`. These additional diagnostics are explicitly post-evaluation; they are not newly invented passing criteria.

## Known limits

The final winner target comes from official NHL results, not a guessed winner of tied MoneyPuck scores. Five archived games have other goal-count discrepancies; they are inventoried and never used to replace official results. There is no xG version leakage in model features because xG is excluded.

This v1 keys history by NHL team ID. Utah Hockey Club (59) and Utah Mammoth (68) share franchise 40; the rename therefore restarts history in v1. This is a known continuity limitation, disclosed alongside both first-ten-game exclusions. Preserve this benchmark; address continuity in a new version before paper deployment and do not describe a revised score on the same test seasons as a fresh untouched test.

There are no matched historical PlayNow prices, injury/lineup archives or live forecasts in these results. Winner accuracy is not a bet win rate or profit estimate. A promising aggregate score cannot override weak recent-season results or establish a sportsbook edge. The research outputs are deliberately incompatible with the current production approval contract.
