import os
os.environ["SUPABASE_DB_URL"] = ""
os.environ["THE_ODDS_API_KEY"] = ""
os.environ["ESPORTS_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["ADMIN_API_TOKEN"] = "test-session-token-32-characters-long"

import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app import db
from app.models import Base, Account

@pytest_asyncio.fixture
async def database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    previous = db.Session
    db.Session = async_sessionmaker(engine,expire_on_commit=False)
    async with db.Session.begin() as session:
        session.add(Account(id=1,initial_bankroll=1100))
    yield db.Session
    db.Session = previous
    await engine.dispose()
