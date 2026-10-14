import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, reset_tzpath
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
# Use the pinned IANA wheel, not potentially outdated container / host timezone data.
reset_tzpath(())
PACIFIC = ZoneInfo("America/Vancouver")

def bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(os.getenv(name, str(default)))))

def dollar_limit(name: str, default: str = '0') -> Decimal:
    value = Decimal(os.getenv(name, default))
    if not value.is_finite() or not 0 <= value <= 1000 or value != value.quantize(Decimal('.000001')):
        raise ValueError(f'{name} must be a finite USD amount from 0 to 1000 with at most six decimals')
    return value

def active_sports() -> tuple[str, ...]:
    values = tuple(dict.fromkeys(s.strip().upper() for s in os.getenv('ACTIVE_SPORTS', 'NHL').split(',') if s.strip()))
    if not values or any(s not in {'NHL','NBA','MLB','NFL','CS2','VAL','LOL'} for s in values):
        raise ValueError('ACTIVE_SPORTS contains an unsupported sport')
    return values

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
    active_sports: tuple[str, ...] = active_sports()
    odds_daily_credits: int = bounded_int("ODDS_DAILY_CREDITS", 15, 0, 1000)
    odds_monthly_credits: int = bounded_int('ODDS_MONTHLY_CREDITS', 500, 0, 100000)
    pandascore_daily_requests: int = bounded_int("PANDASCORE_DAILY_REQUESTS", 0, 0, 1000)
    llm_daily_requests: int = bounded_int("LLM_DAILY_REQUESTS", 12, 0, 100)
    llm_daily_usd: Decimal = dollar_limit('LLM_DAILY_USD')
    llm_monthly_usd: Decimal = dollar_limit('LLM_MONTHLY_USD')
    llm_request_usd: Decimal = dollar_limit('LLM_REQUEST_USD', '.01')
    nhl_daily_requests: int = bounded_int("NHL_DAILY_REQUESTS", 300, 0, 500)
    nhl_score_daily_requests: int = bounded_int('NHL_SCORE_DAILY_REQUESTS', 1500, 0, 2000)
    nhl_advanced_enabled: bool = os.getenv('ENABLE_NHL_ADVANCED_STATS', 'false').lower() == 'true'
    nhl_advanced_monthly_bytes: int = bounded_int('NHL_ADVANCED_MONTHLY_BYTES', 1_500_000_000, 0, 1_500_000_000)
    allowed_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    dashboard_url: str = 'https://sports-intelligence-dashboard.onrender.com/'
    odds_refreshes_24h: int = bounded_int('ODDS_REFRESHES_24H',5,0,5)

    @property
    def llm_enabled(self):
        return bool(self.router_key and self.llm_daily_requests and self.llm_request_usd and self.llm_daily_usd and self.llm_monthly_usd)

settings = Settings()
