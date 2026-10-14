import asyncio
import logging
import hashlib
from datetime import timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, text, delete
from . import db
from .clock import now, aware
from .config import PACIFIC,settings
from .models import Fixture, Snapshot, MarketOdds, Evidence, EvaluationCycle, RuntimeLimit, AuditLog
from .limits import limits,BudgetExceeded
from .ingestion import ingest_nhl, ingest_esports, ingest_results, ingest_nhl_personnel
from .engine import freeze, evaluate

log = logging.getLogger("scheduler")
scheduler = AsyncIOScheduler(timezone=PACIFIC, job_defaults={"coalesce":True,"max_instances":1,"misfire_grace_time":5})

async def guarded(key, operation, seconds=600):
    if not await limits.lease(key, seconds):
        return
    try:
        async with asyncio.timeout(seconds-5):
            await operation()
    except BudgetExceeded:
        log.info('Job %s skipped by its budget or duplicate-request safeguard',key)
    except Exception as exc:
        # Log category only: HTTP exceptions can contain API-key query strings.
        log.error("Job %s stopped safely (%s)", key, type(exc).__name__)

async def refresh_nhl():
    await ingest_nhl(history=False)
    await ingest_nhl_personnel()
    await anchors()

async def daily_nhl():
    await ingest_nhl(history=True)
    await anchors()

async def recover_startup():
    # Existing fixtures must retain their exact checkpoint even if refresh is
    # unavailable or the free-data budget is exhausted during this restart.
    await anchors()
    await daily_nhl()

async def prepare_anchors():
    async with db.Session() as session:
        upcoming=(await session.execute(select(Fixture.id,Fixture.commence_time).where(Fixture.sport=='NHL',
            Fixture.commence_time>now()+timedelta(minutes=35),Fixture.commence_time<=now()+timedelta(minutes=45)))).all()
    if not upcoming:return
    key=hashlib.sha256(str(sorted((fid,aware(start).isoformat()) for fid,start in upcoming)).encode()).hexdigest()
    if await limits.lease(f'nhl-pre-anchor:{key}',7200):
        await ingest_nhl(history=True)
        await ingest_nhl_personnel()
        await anchors()

async def anchors():
    async with db.Session() as session:
        fixtures = (await session.scalars(select(Fixture).where(Fixture.sport.in_(settings.active_sports),Fixture.commence_time > now(),
            Fixture.commence_time < now()+timedelta(days=3)).limit(300))).all()
        for fixture in fixtures:
            anchor = aware(fixture.commence_time)-timedelta(minutes=30)
            job_id = f"anchor:{fixture.id}"
            if not await session.get(Snapshot, fixture.id) and anchor > now():
                scheduler.add_job(freeze, "date", run_date=anchor, args=[fixture.id], id=job_id, replace_existing=True)

async def gates_cycle():
    async with db.Session() as session:
        ids = (await session.scalars(select(Fixture.id).where(Fixture.sport.in_(settings.active_sports),Fixture.commence_time > now(),
            Fixture.commence_time <= now()+timedelta(minutes=30)).limit(60))).all()
    for fid in ids:
        await evaluate(fid)

async def pulse():
    async with db.Session() as session:
        await session.execute(text("SELECT 1"))

async def retain():
    async with db.Session.begin() as session:
        cutoff = now()-timedelta(days=7)
        await session.execute(delete(MarketOdds).where(MarketOdds.created_at < cutoff))
        await session.execute(delete(Evidence).where(Evidence.observed_at < cutoff))
        # Preserve snapshots/bets/audit history; attempt caps survive for fixture lifetime.

def start():
    from .matches import tick as scores_tick
    scheduler.add_job(scores_tick,'interval',seconds=30,next_run_time=now(),id='nhl-scores')
    scheduler.add_job(guarded, CronTrigger(hour=4, minute=0, timezone=PACIFIC), args=["nhl-daily",daily_nhl,1800], id="nhl-daily")
    scheduler.add_job(guarded, "interval", hours=1, args=["nhl-refresh",refresh_nhl], id="nhl-refresh")
    if settings.nhl_advanced_enabled:
        from .nhl_advanced import sync as advanced_sync
        scheduler.add_job(guarded, CronTrigger(hour=9, minute=0, timezone=PACIFIC),
                          args=['nhl-advanced-daily',advanced_sync,240], id='nhl-advanced-daily')
    if set(settings.active_sports)&{'CS2','VAL','LOL'} and settings.pandascore_daily_requests:
        scheduler.add_job(guarded, "interval", hours=2, args=["esports",ingest_esports,1800], id="esports")
    # Odds are requested only through the authenticated manual refresh endpoint.
    scheduler.add_job(guarded, "interval", minutes=1, args=["nhl-preparation",prepare_anchors,55], id="nhl-preparation")
    scheduler.add_job(guarded, "interval", minutes=1, args=["gates",gates_cycle,55], id="gates")
    scheduler.add_job(guarded, "interval", hours=4, args=["results",ingest_results], id="results")
    scheduler.add_job(guarded, "interval", hours=48, args=["pulse",pulse], id="pulse")
    scheduler.add_job(guarded, "interval", days=1, args=["retention",retain], id="retention")
    scheduler.start()
    # Bounded startup recovery; no catch-up of missed paid cron runs.
    scheduler.add_job(guarded, "date", args=["startup",recover_startup,1800], run_date=now()+timedelta(seconds=2), id="startup")
