"""Disposable local browser QA. No live databases, providers, or scheduler."""
import os
for key in ("SUPABASE_DB_URL","THE_ODDS_API_KEY","ESPORTS_API_KEY","OPENROUTER_API_KEY"):
    os.environ[key] = ""
os.environ["ENABLE_SCHEDULER"] = "false"

from contextlib import asynccontextmanager
from datetime import timedelta
from uuid import uuid4
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from app.api import app
from app import db
from app.models import Base,Account,Fixture,State,PersonalBet,Outcome
from app.model_config import GATE_NAMES
from app.clock import now

@asynccontextmanager
async def lifespan(application):
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    db.Session=async_sessionmaker(engine,expire_on_commit=False)
    async with db.Session.begin() as session:
        session.add(Account(id=1,initial_bankroll=1100))
        if os.getenv("QA_FIXTURE") == "true":
            session.add(Fixture(id="qa:fixture",sport="NHL",home="QA Home",away="QA Away",commence_time=now()+timedelta(hours=3),
                state=State.HOLD,reason="Disposable browser test. No real match or price.",metrics={},
                probability='.72',edge='.06',gates={gate:True for gate in GATE_NAMES[:4]}))
            await session.flush()
            if os.getenv("QA_PERFORMANCE") == "true":
                for outcome,stake,profit,days in [(Outcome.WIN,25,25,2),(Outcome.LOSS,10,-10,1),(Outcome.PUSH,10,0,0)]:
                    session.add(PersonalBet(request_id=str(uuid4()),fixture_id="qa:fixture",selection="QA Home",
                        odds_taken=2,stake_cad=stake,unit_size_at_execution=100,outcome=outcome,profit_cad=profit,
                        updated_at=now()-timedelta(days=days)))
    yield
    await engine.dispose()

app.router.lifespan_context=lifespan
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8001)
