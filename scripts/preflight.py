"""Report secret presence without printing values or contacting paid providers."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from app.config import settings
from app.db import direct_database_url

for name,value in (("SUPABASE_DB_URL",settings.db_url),("THE_ODDS_API_KEY",settings.odds_key),
    ("ESPORTS_API_KEY",settings.esports_key),("OPENROUTER_API_KEY",settings.router_key),
    ("ADMIN_API_TOKEN",settings.admin_token)):
    print(f"{name}: {'configured' if value else 'missing'}")
if settings.db_url:
    try:
        direct_database_url(settings.db_url)
        print("Database connection mode: supported Supabase direct/Session Pooler on port 5432")
    except Exception:
        print('Database connection mode: invalid URL (redacted)')
print(f"Scheduler: {'enabled' if settings.scheduler else 'disabled'}")
