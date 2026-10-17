# MoneyPuck access request — ready to send

Prepared for the owner; not sent by the agent. The recipient was verified on
the [official download page](https://moneypuck.com/data.htm) on October 16, 2026.
The outbound ranges were read from this service's Render Connect → Outbound
panel. They are shared regional ranges, not dedicated addresses.

To: moneypuck.com@gmail.com

Subject: Permission and supported download access for a private NHL analytics dashboard

Hello Peter / MoneyPuck team,

I'm building a private, password-protected NHL dashboard for personal research
and betting analysis. It currently has no paying subscribers or public dataset
distribution. I would like to cache your published team and goalie game-level
files once daily, with clear MoneyPuck attribution, to display historical 5v5
expected-goals statistics and goalie GSAx and evaluate my own prediction models.

Could you confirm whether that use, including model development and retaining
historical research observations, is permitted under your download terms? If
it needs a separate licence, please let me know the terms and cost.

The files are linked on your data page:

- https://moneypuck.com/moneypuck/playerData/careers/gameByGame/all_teams.csv
- https://peter-tanner.com/moneypuck/downloads/seasonPlayersSummary/goalies/2026.zip

Our Render backend in Oregon received HTTP 302 for the team file and HTTP 403
for the goalie file in a single diagnostic at 00:04:38 UTC on October 17
(17:04 Pacific on October 16). The identical files downloaded normally from my
computer. We have not established why the responses differ and do not want to
work around your access controls.

Is there a supported server-to-server download route, required request format,
or access arrangement we should use? If allowlisting is appropriate, Render
currently lists these shared outbound ranges for the service:

- 74.220.48.0/24
- 74.220.56.0/24

The client identifies itself as `G-Sports-private-statistics/0.1`, requests gzip
for the team CSV, and accepts the goalie ZIP directly. It downloads at most one
scheduled batch daily, stops on failures, enforces transfer limits, and does
not repeatedly retry denied requests. Normal dashboard views read our saved
cache. We are not requesting permission to scrape your other website pages.

Thank you for your work and for clarifying the appropriate access method.

## What this request unblocks

A clear answer on our actual use and automated access. A provider reply may
identify a supported endpoint, explain the redirect/denial, require a licence,
or decline the use. No supported access, approval or price is assumed yet.
Do not send credentials, database URLs or API keys with this message.
