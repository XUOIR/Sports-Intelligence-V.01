# NHL Team History — Read-Only Inventory

October 15, 2026. Active repository: XUOIR/Sports-Intelligence-V.01. This is an offline source inventory to inform the release interview and a proposed team-only experiment. No network/provider request, database access, model fit, approval or production change occurred.

## Verified local inputs

Both files are under `artifacts/nhl-low-cost-provider-research/moneypuck-offline-test/compressed-2026-10-14/` in this repository:

| File | Bytes | SHA256 |
| --- | ---: | --- |
| `all_teams.csv` | 127,056,736 | `78ebaf1ab1b51fbb734978001d0ee1101de2c3703836a201af82765c99de9483` |
| `goalies/goalies.zip` | 48,168 | `08521e87b92a5e64f755c63f913718e010f7fe60118fc5f71ebc75832ce31eda` |

The team file has 233,270 rows across season labels 2008–2026. The goalie archive has one member, `2026.csv`, 228,791 uncompressed bytes, containing 1,115 rows and 105 game IDs dated September 29–October 13, 2026. This goalie archive does not establish historical goalie coverage.

## Regular-season team inventory

The counts below use `situation=all` and regular-season game IDs. A structurally clean pair has two team rows with reciprocal opponents, opposite home/away flags, matching dates and reciprocal scores. This is not a complete audit against the official schedule, an assessment of feature availability before games or a model validation corpus.

| Season label | Regular game IDs | Structurally clean pairs | Dates in file | Clean pairs with tied scores |
| --- | ---: | ---: | --- | ---: |
| 2008 | 1,227 | 1,227 | 2008-10-04–2009-04-12 | 159 |
| 2009 | 1,229 | 1,229 | 2009-10-01–2010-04-11 | 183 |
| 2010 | 1,230 | 1,230 | 2010-10-07–2011-04-10 | 149 |
| 2011 | 1,230 | 1,189 | 2011-10-06–2012-04-07 | 175 |
| 2012 | 720 | 696 | 2013-01-19–2013-04-28 | 94 |
| 2013 | 1,230 | 1,189 | 2013-10-01–2014-04-13 | 172 |
| 2014 | 1,230 | 1,230 | 2014-10-08–2015-04-11 | 170 |
| 2015 | 1,230 | 1,230 | 2015-10-07–2016-04-10 | 107 |
| 2016 | 1,230 | 1,230 | 2016-10-12–2017-04-09 | 99 |
| 2017 | 1,271 | 1,271 | 2017-10-04–2018-04-08 | 103 |
| 2018 | 1,271 | 1,271 | 2018-10-03–2019-04-06 | 87 |
| 2019 | 1,082 | 1,082 | 2019-10-02–2020-03-11 | 87 |
| 2020 | 868 | 868 | 2021-01-13–2021-05-19 | 65 |
| 2021 | 1,312 | 1,312 | 2021-10-12–2022-05-01 | 102 |
| 2022 | 1,312 | 1,312 | 2022-10-07–2023-04-14 | 95 |
| 2023 | 1,312 | 1,312 | 2023-10-10–2024-04-18 | 82 |
| 2024 | 1,312 | 1,312 | 2024-10-04–2025-04-17 | 77 |
| 2025 | 1,312 | 1,312 | 2025-10-07–2026-04-16 | 119 |
| 2026 | 105 | 105 | 2026-09-29–2026-10-13 | 7 |
| **Total** | **21,713** | **21,607** | | **2,132** |

## Findings that affect the experiment

**Final-winner labels need reconciliation.** Headers contain game ID, season, team/opponent, home/away, game date, goals for/against, playoff flag, xG, shots and manpower situations. They do not include an explicit final winner, shootout winner, final-state flag or exact start/end timestamps. A simple score comparison cannot label the 2,132 clean tied-score pairs for the agreed final-winner target. They must not be silently assigned a winner or discarded without a declared policy and bias assessment.

The existing `backend/app/nhl_data.py` reconciliation accounts for MoneyPuck omitting the shootout winner's score bonus. Rechecking the 16 already-cached official October 13 finals reconciled them successfully, including two explicitly marked shootouts. That verifies the interpretation on this cached sample, not all historical tied-score games. Matching official historical final results is the next labeling requirement; no additional source fetch was made for this audit.

**Identity problems are present in older rows.** The audit reproduced 575 malformed rows across 2011–2013: 250, 120 and 205. They affect 106 regular-season games and nine playoff games. For example, game `2011020475` includes an `ARI` versus `ARI` row and conflicting venue identity. No repair was inferred. A declared exclusion policy or a trustworthy repair source is needed, and official season completeness remains unverified.

**Historical xG provenance remains unresolved.** Current files do not establish when each historical xG value was calculated, its original pregame availability or whether a later model revision used future training data. A first results/team-only experiment can omit xG rather than importing that uncertainty into its features. It still needs outcome and identity checks.

**A team-only research experiment has a different evidence contract.** Earlier completed games can support date-grouped historical reconstruction, with appropriate embargoes and final-result reconciliation. Historical data downloaded today remains reconstructed research, not an originally saved live forecast. Archived pregame starter announcements are not intrinsic inputs to a model deliberately specified to forecast under lineup uncertainty.

The existing goalie-dependent implementation does require that evidence in `nhl_factors.py`, `engine.py`, `calibrate.py` and `readiness.py`. Its approvals, weighted factors and frozen snapshot contract cannot be inherited by a different model or bypassed through a false confirmation flag.

## Meaning of the earlier 105-game audit

The earlier `artifacts/nhl-evidence-audit/forecast-corpus-audit.json` and `docs/NHL_FORECAST_CAPTURE_RELEASE.md` examined current-season overlap with the available goalie archive: 105 games, only 20 with five earlier games for both teams. That was a current-season goalie-contract inventory. It did not establish that only 105 historical team games exist.

## Consequence

There is a substantial cached starting point for a free team-strength experiment. It is not yet a fully qualified training/evaluation dataset. Next work is explicit target-label reconciliation, completeness/identity handling and a separately specified chronological experiment. No new paid data subscription is justified by this inventory alone, and no predictive edge or deployment readiness has been established.
