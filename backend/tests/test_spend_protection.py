import asyncio
from dataclasses import replace
from decimal import Decimal
from datetime import datetime,timedelta
from app.clock import now,PACIFIC
import httpx
import pytest
from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from app import db
from app.config import settings
from app.limits import Limits,BudgetExceeded
from app.http import SafeHTTP,ProviderError
from app.models import Base,ProviderCall,RuntimeLimit,Fixture,EvaluationCycle

def ai_settings(monkeypatch,**overrides):
    value=replace(settings,router_key='not-a-real-key',llm_daily_usd=Decimal('.02'),llm_monthly_usd=Decimal('.03'),llm_request_usd=Decimal('.01'),**overrides)
    monkeypatch.setattr('app.limits.settings',value)
    monkeypatch.setattr('app.providers.settings',value)
    return value

async def seed_cycles(database,count=4):
    async with database.begin() as session:
        session.add(Fixture(id='nhl:spend',sport='NHL',home='Home',away='Away',commence_time=now()+timedelta(hours=3)))
        await session.flush()
        session.add_all([EvaluationCycle(id=f'cycle:{i}',fixture_id='nhl:spend') for i in range(count)])

async def test_paid_identity_survives_new_clients_resume_and_failures(database):
    requests=[]
    def outage(request):requests.append(request);return httpx.Response(503)
    guard=Limits();client=SafeHTTP(guard,httpx.MockTransport(outage))
    with pytest.raises(ProviderError):await client.request('odds','GET','https://example.test',cost=3,identity='period:1')
    assert len(requests)==1 and await Limits().blocked('odds')
    await guard.resume('odds')
    with pytest.raises(BudgetExceeded):await SafeHTTP(Limits(),httpx.MockTransport(outage)).request('odds','GET','https://example.test',cost=3,identity='period:1')
    async with database() as session:
        row=await session.scalar(select(ProviderCall))
        assert row.status=='FAILED' and row.units==3
        assert await session.scalar(select(func.count()).select_from(ProviderCall))==1
    assert len(requests)==1

async def test_daily_and_monthly_usd_caps_roll_back_failed_admissions(database,monkeypatch):
    import app.limits as module
    timestamp=datetime(2026,10,13,12,tzinfo=PACIFIC)
    monkeypatch.setattr(module,'now',lambda:timestamp)
    ai_settings(monkeypatch);await seed_cycles(database)
    guard=Limits()
    for i in range(2):await guard.reserve('openrouter',identity=f'cycle:{i}',cycle_id=f'cycle:{i}',fixture_id='nhl:spend',usd=Decimal('.01'))
    with pytest.raises(BudgetExceeded):await guard.reserve('openrouter',identity='cycle:2',cycle_id='cycle:2',fixture_id='nhl:spend',usd=Decimal('.01'))
    async with database() as session:
        assert await session.scalar(select(func.count()).select_from(ProviderCall))==2
        assert (await session.get(EvaluationCycle,'cycle:2')).llm_attempts==0
    # The monthly cap also applies after changing the daily date.
    monkeypatch.setattr(module,'now',lambda:timestamp+timedelta(days=1))
    await guard.reserve('openrouter',identity='cycle:2',cycle_id='cycle:2',fixture_id='nhl:spend',usd=Decimal('.01'))
    with pytest.raises(BudgetExceeded):await guard.reserve('openrouter',identity='cycle:3',cycle_id='cycle:3',fixture_id='nhl:spend',usd=Decimal('.01'))

async def test_no_budget_or_identity_no_paid_admission(database):
    guard=Limits()
    with pytest.raises(BudgetExceeded):await guard.reserve('openrouter',identity='review',fixture_id='nhl:x',cycle_id='review',usd=Decimal('.01'))
    for cost in [0,-1,True,1.5]:
        with pytest.raises(BudgetExceeded):await guard.reserve('odds',cost,identity='invalid')
    with pytest.raises(BudgetExceeded):await guard.reserve('odds',3)
    with pytest.raises(BudgetExceeded):await guard.reserve('pandascore',identity='disabled')
    async with database() as session:assert await session.scalar(select(func.count()).select_from(ProviderCall))==0

async def test_pause_persists_and_does_not_reset_spend(database):
    guard=Limits();await guard.reserve('odds',3,identity='first')
    await guard.pause(True)
    with pytest.raises(BudgetExceeded):await Limits().reserve('odds',3,identity='second')
    await Limits().pause(False)
    with pytest.raises(BudgetExceeded):await guard.reserve('odds',3,identity='first')
    await guard.reserve('odds',3,identity='second')
    async with database() as session:assert sum((await session.scalars(select(ProviderCall.units))).all())==6

@pytest.mark.parametrize('status',[429,500,503,401,403])
async def test_paid_errors_never_retry(database,status):
    requests=[]
    def fail(request):requests.append(request);return httpx.Response(status,headers={'Retry-After':'0'})
    with pytest.raises(ProviderError):await SafeHTTP(Limits(),httpx.MockTransport(fail)).request('odds','GET','https://example.test',cost=3,identity='paid')
    assert len(requests)==1 and await Limits().blocked('odds')

async def test_timeout_is_unknown_and_keeps_reserved_budget(database):
    def timeout(request):raise httpx.ReadTimeout('Do not print credentials from this exception')
    guard=Limits()
    with pytest.raises(ProviderError):await SafeHTTP(guard,httpx.MockTransport(timeout)).request('odds','GET','https://example.test',cost=3,identity='unknown')
    async with database() as session:
        row=await session.scalar(select(ProviderCall))
        assert row.status=='UNKNOWN' and row.units==3
    await guard.resume('odds')
    with pytest.raises(BudgetExceeded):await guard.reserve('odds',3,identity='unknown')

async def test_concurrent_instances_send_one_request(tmp_path,monkeypatch):
    engine=create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "spend.sqlite"}')
    async with engine.begin() as connection:await connection.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(db,'Session',async_sessionmaker(engine,expire_on_commit=False))
    sent=[]
    def reply(request):
        sent.append(request)
        return httpx.Response(200,json=[],headers={'x-requests-remaining':'97','x-requests-used':'3','x-requests-last':'3'})
    async def request():
        try:await SafeHTTP(Limits(),httpx.MockTransport(reply)).request('odds','GET','https://example.test',cost=3,identity='one-period');return 'sent'
        except BudgetExceeded:return 'blocked'
    try:
        results=await asyncio.gather(*(request() for _ in range(5)))
        assert results.count('sent')==1 and len(sent)==1
        async with db.Session() as session:assert await session.scalar(select(func.count()).select_from(ProviderCall))==1
    finally:await engine.dispose()

async def test_fixture_lifetime_cap_cannot_be_reset_by_new_cycles(database,monkeypatch):
    ai_settings(monkeypatch,llm_daily_requests=100)
    import app.limits as module
    monkeypatch.setattr(module,'settings',replace(module.settings,llm_daily_usd=Decimal('1'),llm_monthly_usd=Decimal('1')))
    await seed_cycles(database)
    for i in range(3):await Limits().reserve('openrouter',identity=f'cycle:{i}',fixture_id='nhl:spend',cycle_id=f'cycle:{i}',usd=Decimal('.01'))
    with pytest.raises(BudgetExceeded):await Limits().reserve('openrouter',identity='cycle:3',fixture_id='nhl:spend',cycle_id='cycle:3',usd=Decimal('.01'))

async def test_odds_monthly_cap_cannot_be_exceeded_or_consume_rejected_identity(database,monkeypatch):
    import app.limits as module
    monkeypatch.setattr(module,'settings',replace(settings,odds_daily_credits=12,odds_monthly_credits=5))
    await Limits().reserve('odds',3,identity='allowed')
    with pytest.raises(BudgetExceeded):await Limits().reserve('odds',3,identity='rejected')
    assert not await Limits().attempted('odds','rejected')
    async with database() as session:
        row=await session.get(RuntimeLimit,f'odds:{now().date()}')
        assert row.used==3
