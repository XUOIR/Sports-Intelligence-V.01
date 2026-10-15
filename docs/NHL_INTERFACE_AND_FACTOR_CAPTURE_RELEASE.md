# NHL interface and factor capture — October 14, 2026

Work began after the user's requested 7:06 PM Pacific reset, through the one-time 7:08 PM continuation. Only XUOIR/Sports-Intelligence-V.01 was used.

## Interface

Model Performance uses title case, no terminal period and the established cyan/blue/violet gradient. Daily Matchups, Today's Matches, Prediction History, Bankroll, connection headings and verification headings follow the same treatment. The theme and existing statistics are preserved.

The sidebar reads official NHL abbreviations/logos and the latest saved PlayNow two-sided moneyline pair. Prices are decimal and explicitly labeled expired after five minutes. Reads never request odds. The main status now distinguishes saved/expired odds, no saved odds and a connection failure. Reload saved data still performs database reads only. A newer partial, invalid or future quote cannot revive an older complete price pair.

The user authorized clearer badge names. Canonical database states and gates remain unchanged:

| Internal state | Display | Meaning |
| --- | --- | --- |
| WATCH | AWAITING REVIEW | Monitoring without an executable verified decision |
| HOLD | NEEDS VERIFICATION | Missing, expired or conflicting checks; the reason lists what is needed |
| PASS | NO QUALIFYING EDGE | Validated edge below the three percentage-point minimum |
| RECOMMEND | VERIFIED PLAY | All eight verification and risk gates passed |

Sidebar reasons are visible, and raw gate names are translated into readable missing requirements. LIVE/Final/schedule labels are separate from decision badges.

The point-cloud hologram has separate basketball grooves, tapered football panels/laces, a continuous red baseball stitch path, and flat puck disks with side-wall texture. Clicks use a view-space cursor origin, a bounded radial wave, smooth return and soft edge fading. Hidden-tab, inactivity and reduced-motion protections remain.

## Tracking

Bankroll supports manual PENDING/WIN/LOSS/PUSH/VOID reconciliation, including corrections. An isolated browser check changed a test ticket from loss to win: capital changed CAD 1,090 to CAD 1,110; the separate saved model's result remained incorrect with Brier 0.3844. No production ticket was created or edited.

Brier is a probability scoring rule, not an unfinished caption. A defect excluding saved 50/50 forecasts was fixed: they now contribute to saved/resolved counts and Brier, while receiving no directional correctness claim. Sport scoping and manual-ticket/model separation remain covered by tests. Production still has zero genuine forecasts; no accuracy or model ROI is invented.

## Prospective research inputs

The existing admitted MoneyPuck download now retains rolling strength rates, home/away venue splits and goalie exposure. No extra download, API, schedule, daily admission or bandwidth allowance was added. Rebuilding the already downloaded October 14 files offline produced an 84,281-byte cache, below the unchanged 200,000-byte limit, with 32 team contexts, 113 eligible strength/venue windows and 44 goalies with exposure.

Starter confirmations and retractions are also stored as immutable observed evidence. Existing operator records are not backdated. At future exact T−30 checkpoints, the latest pre-anchor confirmation may support a separate versioned research factor record. Missing inputs produce an explicit blocked reason; raw snapshots still capture when otherwise eligible.

`nhl-factor-research-v1` specifies home-minus-away inputs, clamped to −1…+1. It uses confirmed same-team goalie GSAx/60 differences (scale one goal/60), 5v5 xG-share differences (scale 0.20), rest differences capped at four days (scale three days), and the mean of venue xG differential and matchup power-play/penalty-kill rate differences (scales two/four goals per 60). All contributing windows require at least three eligible prior regular-season games, no target-day outcomes, current genuinely observed source data and unambiguous confirmed goalies. These scales are research choices fixed before evaluation, not proven predictive coefficients. Raw values, contract and starter provenance are retained.

**Research factors do not populate the approved forecast, betting edge, existing manual model-factor evidence, verification gates, stake or AI admissions.** Model approval still requires the existing genuine chronological 300/100/100 partitions, date embargoes and reference-beating untouched-test Brier. Historical downloaded files cannot be relabeled as observations made before old games. Six live input snapshots, zero baseline records, zero forecasts and zero approved models were independently observed before rollout. Promoting a reproducible normalization contract into an approved model remains unfinished; the interface work does not claim otherwise.

## Checks and usage

The full isolated backend suite passed 214 checks, and the additional strength-window test plus affected suites passed afterward (215 backend checks total). All 21 frontend checks passed; the production frontend build and type checking passed. Desktop and 390-pixel mobile checks found no horizontal overflow and confirmed readable badge names, prices, logos and gradient headings. Browser graphics reported no errors. All provider calls in tests are mocked or disabled.

At 7:22:59 PM Pacific, free provider metadata reported Odds API 9 used / 491 remaining, and OpenRouter US$0 daily/monthly/all-time usage, US$3 remaining with monthly reset and US$10 wallet balance. No AI generation or metered odds refresh was performed. A live database read independently showed zero AI admissions and three odds request records. Existing caps, latches, manual-refresh policy, secrets and login remain unchanged.

Live rollout evidence is appended after deployment verification.
