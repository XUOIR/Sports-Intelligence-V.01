"""Read balances only; never generates AI text or requests metered odds.

Credentials stay in memory. Only whitelisted balance fields reach the report.
No redirects or retries. The app/scheduler/database are never imported.
"""
import concurrent.futures
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from dotenv import dotenv_values


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("Account-check redirect rejected")


def main():
    root = Path(__file__).resolve().parents[1]
    values = dotenv_values(root / ".env")
    checks = [
        ("odds", "https://api.the-odds-api.com/v4/sports/?" + urlencode({"apiKey": values.get("THE_ODDS_API_KEY", "")}), {}),
        ("openrouter_key", "https://openrouter.ai/api/v1/key", {"Authorization": "Bearer " + values.get("OPENROUTER_API_KEY", "")}),
        ("openrouter_wallet", "https://openrouter.ai/api/v1/credits", {"Authorization": "Bearer " + values.get("OPENROUTER_API_KEY", "")}),
    ]

    def check(item):
        label, url, headers = item
        report = {"provider": label, "checked_at": datetime.now(timezone.utc).isoformat(), "attempts": 1}
        try:
            with build_opener(NoRedirect()).open(Request(url, headers=headers), timeout=15) as response:
                body = response.read(1_000_001)
                if len(body) > 1_000_000:
                    raise ValueError("Response cap exceeded")
                data = json.loads(body)
                report["status"] = response.status
                if label == "odds":
                    report.update({k: int(response.headers["x-requests-" + k]) for k in ("remaining", "used", "last")})
                elif label == "openrouter_key":
                    report.update({k: data["data"].get(k) for k in ("limit", "limit_remaining", "limit_reset", "usage", "usage_daily", "usage_monthly")})
                else:
                    report.update({k: data["data"].get(k) for k in ("total_credits", "total_usage")})
        except Exception as exc:
            # Exception strings can contain a secret URL; emit the class only.
            report["error"] = type(exc).__name__
        return report

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        result = list(pool.map(check, checks))
    output = root / "artifacts/overnight-usage-2026-10-14"
    output.mkdir(parents=True, exist_ok=True)
    (output / "provider-checks.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if all(r.get("status") == 200 for r in result) else 1


if __name__ == "__main__":
    raise SystemExit(main())
