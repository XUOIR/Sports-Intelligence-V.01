import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, reset_tzpath
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
# Use the pinned IANA wheel, not potentially outdated container / host timezone data.
reset_tzpath(())
PACIFIC = ZoneInfo("America/Vancouver")

def bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(os.getenv(name, str(default)))))

@dataclass(frozen=True)
class Settings:
    direct_db_host: str = "db.lagwnyxitcfrdfnuafea.supabase.co"
    db_url: str = os.getenv("SUPABASE_DB_URL", "")
    odds_key: str = os.getenv("THE_ODDS_API_KEY", "")
    esports_key: str = os.getenv("ESPORTS_API_KEY", "")
    router_key: str = os.getenv("OPENROUTER_API_KEY", "")
    admin_token: str = os.getenv("ADMIN_API_TOKEN", "")
    scheduler: bool = os.getenv("ENABLE_SCHEDULER", "false").lower() == "true"
    max_response_bytes: int = bounded_int("MAX_RESPONSE_BYTES", 1_000_000, 1024, 2_000_000)
    odds_daily_credits: int = bounded_int("ODDS_DAILY_CREDITS", 120, 1, 1000)
    pandascore_daily_requests: int = bounded_int("PANDASCORE_DAILY_REQUESTS", 120, 1, 1000)
    llm_daily_requests: int = bounded_int("LLM_DAILY_REQUESTS", 12, 1, 100)
    nhl_daily_requests: int = bounded_int("NHL_DAILY_REQUESTS", 100, 1, 500)
    allowed_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

settings = Settings()
