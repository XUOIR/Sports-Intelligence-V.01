import ssl
from urllib.parse import quote, unquote
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from .config import settings

engine = None
Session = None

def direct_database_url(raw: str):
    try:
        scheme, separator, remainder = raw.partition("://")
        if not separator or scheme not in {"postgres", "postgresql", "postgresql+asyncpg"}:
            raise ValueError()
        userinfo, at, server = remainder.rpartition("@")
        username, colon, password = userinfo.partition(":")
        if not at or not colon or username != "postgres" or not password:
            raise ValueError()
        # Normalize once: raw ! becomes %21; already encoded %21 stays %21.
        encoded_password = quote(unquote(password, errors="strict"), safe="")
        target = make_url(f"{scheme}://{username}:{encoded_password}@{server}")
        if target.host != settings.direct_db_host or target.port != 5432 or target.database != "postgres":
            raise ValueError()
        return target.set(drivername="postgresql+asyncpg").difference_update_query(["sslmode", "ssl", "pgbouncer"])
    except Exception:
        raise ValueError("Use the configured direct Supabase PostgreSQL host on port 5432 with a URL-encoded password") from None

def configure_database(url: str | None = None):
    global engine, Session
    target = direct_database_url(url or settings.db_url)
    engine = create_async_engine(target, pool_size=10, max_overflow=20, pool_recycle=1800,
        pool_pre_ping=True, pool_timeout=15, connect_args={"ssl": ssl.create_default_context(),
        "timeout": 15, "command_timeout": 20,
        "server_settings": {"timezone": "America/Vancouver", "statement_timeout": "20000"}})
    Session = async_sessionmaker(engine, expire_on_commit=False)
    return engine

async def session():
    if Session is None:
        raise RuntimeError("Database not configured")
    async with Session() as db:
        yield db
