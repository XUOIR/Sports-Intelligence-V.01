from datetime import timedelta
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from . import db
from .clock import now, aware
from .models import RuntimeLimit, JobLease, EvaluationCycle
from .config import settings
from .model_config import MAX_LLM_RETRIES

class BudgetExceeded(RuntimeError):
    pass

class Limits:
    async def reserve(self, provider: str, cost: int = 1):
        caps = {"odds": settings.odds_daily_credits, "pandascore": settings.pandascore_daily_requests,
            "openrouter": settings.llm_daily_requests, "nhl": settings.nhl_daily_requests}
        key = f"{provider}:{now().date()}"
        async with db.Session.begin() as session:
            await session.execute(insert(RuntimeLimit).values(key=key, used=0).on_conflict_do_nothing())
            result = await session.execute(update(RuntimeLimit).where(RuntimeLimit.key == key,
                RuntimeLimit.used + cost <= caps[provider]).values(used=RuntimeLimit.used + cost).returning(RuntimeLimit.key))
            if result.scalar_one_or_none() is None:
                raise BudgetExceeded(f"{provider} daily limit reached")

    async def blocked(self, provider: str):
        async with db.Session() as session:
            row = await session.get(RuntimeLimit, f"circuit:{provider}")
            return bool(row and row.blocked_until and aware(row.blocked_until) > now())

    async def trip(self, provider: str, seconds=900):
        async with db.Session.begin() as session:
            stmt = insert(RuntimeLimit).values(key=f"circuit:{provider}", used=0, blocked_until=now()+timedelta(seconds=seconds))
            await session.execute(stmt.on_conflict_do_update(index_elements=[RuntimeLimit.key], set_={"blocked_until": stmt.excluded.blocked_until}))

    async def llm_attempt(self, cycle_id: str):
        async with db.Session.begin() as session:
            result = await session.execute(update(EvaluationCycle).where(EvaluationCycle.id == cycle_id,
                EvaluationCycle.llm_attempts < MAX_LLM_RETRIES).values(llm_attempts=EvaluationCycle.llm_attempts+1).returning(EvaluationCycle.id))
            if result.scalar_one_or_none() is None:
                raise BudgetExceeded("Fixture evaluation attempt cap reached")

    async def lease(self, key: str, seconds=300) -> bool:
        async with db.Session.begin() as session:
            stmt = insert(JobLease).values(key=key, expires_at=now()+timedelta(seconds=seconds))
            result = await session.execute(stmt.on_conflict_do_update(index_elements=[JobLease.key],
                set_={"expires_at": stmt.excluded.expires_at}, where=JobLease.expires_at < now()).returning(JobLease.key))
            return result.scalar_one_or_none() is not None

limits = Limits()
