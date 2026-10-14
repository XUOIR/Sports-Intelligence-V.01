# Overnight usage audit — October 14, 2026

Checked around 11:42 AM Pacific. Active project: XUOIR/Sports-Intelligence-V.01. The reviewed idle interval starts at October 13, 10:38:51 PM Pacific (October 14, 05:38:51 UTC). Read-only database queries and provider account endpoints were used; no metered odds request or AI generation was sent.

| Provider | Verified result | Conclusion |
| --- | --- | --- |
| The Odds API | Fresh headers: 497 remaining, 3 used, last request cost 0. App monthly reservation remains 3. | Unchanged from the previous evening. No overnight credit drain. |
| OpenRouter | Fresh key endpoint: US$0 total/daily/monthly use, US$3 remaining with monthly reset. Wallet: US$10 credit, US$0 usage. | No AI spending. Provider-side budget intact. |
| PandaScore | No app data-call records; NHL-only configuration and esports ingestion remain disabled. One recorded metadata check occurred October 13. | No app-generated overnight esports usage. No new PandaScore data query was necessary. |
| NHL public API | App ledger at audit: 140/1,500 score requests and 80/300 statistical requests on October 14. | Free-source calls remained within protective app limits. These are not vendor quotas. |
| Render | Billing UI: 50 MB/5 GB bandwidth, 10/500 pipeline minutes, US$0 pipeline charges. Extra pipeline spending limit remains US$0. Both existing services deployed. | No usage overage shown. US$0.39 accrued service charges are ordinary paid hosting. |
| Supabase | Organization UI: Free plan, 0.11/5 GB egress, 29/500 MB database size, 0/1 GB file storage. | Within displayed free allowances. Logical SQL database size was 13,498,035 bytes; it differs from the dashboard's billing/storage measure. |

The complete `provider_calls` ledger contains only the existing successful three-credit odds batch from October 13, 5:42 PM Pacific. No metered call was recorded during the idle interval. The app ledger cannot establish unrelated activity through other credentials/apps; fresh Odds API and OpenRouter balances independently corroborate this result for the configured keys.

Balance observations are saved in ignored `artifacts/overnight-usage-2026-10-14/provider-checks.json`. No keys, passwords, payment details or full environment configuration appear in this report. Temporary local browser testing used disposable credentials and cleared live provider/database keys.

## Post-release confirmation

Read-only account metadata was checked again at **12:51:51 PM Pacific** after deploying the tested NHL statistics adapter. The balances remain **497 remaining/3 used Odds API credits** and **US$0 OpenRouter usage**, with US$3 remaining under the monthly-reset key cap. The wallet still reports US$10 credit and US$0 usage. No paid provider call was recorded after the idle interval began.

The initial live MoneyPuck import succeeded in about 21 seconds. PostgreSQL records one October 14 admission and **33,419,228 bytes** accounted against its 1,500,000,000-byte monthly transfer safeguard. These source transfers do not use odds or AI credits. Render and Supabase dashboard allowances above describe the initial audit observation, not a refreshed hosting invoice after deployment.
