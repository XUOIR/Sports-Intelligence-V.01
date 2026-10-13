import ssl
import re
from pathlib import Path
from urllib.parse import quote, unquote
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from .config import settings

engine = None
Session = None

def direct_database_url(raw: str):
    """Accept this project's direct endpoint or IPv4 Session Pooler.

    Keep the existing function name for migration and preflight callers.
    Transaction pooling is deliberately excluded because session timezone
    settings and prepared statements must remain supported.
    """
    try:
        scheme, separator, remainder = raw.partition("://")
        if not separator or scheme not in {"postgres", "postgresql", "postgresql+asyncpg"}:
            raise ValueError()
        userinfo, at, server = remainder.rpartition("@")
        username, colon, password = userinfo.partition(":")
        if not at or not colon or not password:
            raise ValueError()
        # Normalize once: raw ! becomes %21; already encoded %21 stays %21.
        encoded_password = quote(unquote(password, errors="strict"), safe="")
        target = make_url(f"{scheme}://{username}:{encoded_password}@{server}")
        project_ref = settings.direct_db_host.split(".")[1]
        is_direct = target.host == settings.direct_db_host and username == "postgres"
        is_session_pooler = (
            re.fullmatch(r"[a-z0-9-]+\.pooler\.supabase\.com", target.host or "") is not None
            and username == f"postgres.{project_ref}"
        )
        if not (is_direct or is_session_pooler) or target.port != 5432 or target.database != "postgres":
            raise ValueError()
        return target.set(drivername="postgresql+asyncpg").difference_update_query(["sslmode", "ssl", "pgbouncer"])
    except Exception:
        raise ValueError("Use this project's Supabase direct connection or Session Pooler on port 5432 with a URL-encoded password") from None

def configure_database(url: str | None = None):
    global engine, Session
    target = direct_database_url(url or settings.db_url)
    ssl_context = ssl.create_default_context()
    # Supabase's database/pooler chain uses its published root CA.
    # Add it to the default trust store while retaining hostname verification.
    ssl_context.load_verify_locations(cafile=str(Path(__file__).resolve().parents[1] / "certs" / "supabase-ca.crt"))
    engine = create_async_engine(target, pool_size=10, max_overflow=20, pool_recycle=1800,
        pool_pre_ping=True, pool_timeout=15, connect_args={"ssl": ssl_context,
        "timeout": 15, "command_timeout": 20,
        "server_settings": {"timezone": "America/Vancouver", "statement_timeout": "20000"}})
    Session = async_sessionmaker(engine, expire_on_commit=False)
    return engine

async def session():
    if Session is None:
        raise RuntimeError("Database not configured")
    async with Session() as db:
        yield db
