from copy import deepcopy
from datetime import timedelta
from dataclasses import replace
import httpx
import pytest
from sqlalchemy import select,func
from app import matches
from app.clock import now
from app.models import Fixture,State,ProviderState,ProviderCall,RuntimeLimit
from app.http import SafeHTTP,ProviderError
from app.limits import Limits,BudgetExceeded
from app.config import settings
from main import app
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from app import db
from app.models import Base
import asyncio

def payload(state='LIVE',gid=2026020102):
    return {'currentDate':str(now().date()),'games':[{'id':gid,'gameDate':str(now().date()),
        'startTimeUTC':(now()+timedelta(hours=2)).isoformat(),'gameState':state,'gameScheduleState':'OK',
        'awayTeam':{'name':{'default':'QA Away'},'abbrev':'QAA','score':1},
        'homeTeam':{'name':{'default':'QA Home'},'abbrev':'QAH','score':3},
        'periodDescriptor':{'number':2,'periodType':'REG'},'clock':{'timeRemaining':'14:21','inIntermission':False}}]}

def test_official_score_contract_zero_scores_and_schedule():
    p=payload();p['games'][0]['awayTeam']['score']=0
    games=matches.parse_scores(p,now().date())
    assert games[0]['away_score']==0 and games[0]['home_score']==3 and games[0]['clock']=='14:21'
    assert matches.interval(games,now().date())==30
    assert matches.parse_scores(payload('FUT'),now().date())[0]['home_score'] is None

@pytest.mark.parametrize('change',[lambda p:p.update(currentDate='2020-01-01'),lambda p:p['games'].append(p['games'][0]),
    lambda p:p['games'][0].update(gameState='mystery'),lambda p:p['games'][0]['homeTeam'].update(score=True),
    lambda p:p['games'][0]['homeTeam'].pop('score')])
def test_changed_scores_fail_closed(change):
    p=payload();change(p)
    with pytest.raises(ProviderError):matches.parse_scores(p,now().date())

def test_date_window_strict():
    assert matches.selected_date(str(now().date()))==now().date()
    for date in ['2026-2-01','2026-02-30','x',str(now().date()+timedelta(days=8))]:
        with pytest.raises(ValueError):matches.selected_date(date)

def test_request_duration_does_not_skip_next_scheduler_tick(monkeypatch):
    at=now();monkeypatch.setattr(matches,'now',lambda:at)
    assert matches.due((at+timedelta(seconds=.5)).isoformat())
    assert not matches.due((at+timedelta(seconds=25)).isoformat())

@pytest.mark.asyncio
async def test_cache_refresh_deadline_is_request_start_not_completion(database,monkeypatch):
    at=now();monkeypatch.setattr(matches,'now',lambda:at)
    class SlowResponse:
        async def request(self,*args,**kwargs):
            nonlocal at
            at+=timedelta(seconds=5)
            return payload()
    monkeypatch.setattr(matches,'http',SlowResponse())
    start=at;await matches.refresh_day(at.date())
    async with database() as session:
        cached=await session.get(ProviderState,f'nhl-score:{at.date()}')
        assert matches.aware(cached.info['next_at'])==start+timedelta(seconds=30)

@pytest.mark.asyncio
async def test_consecutive_ticks_tolerate_database_lease_jitter(database,monkeypatch):
    import app.limits as module
    start=now();at=start;calls=[]
    monkeypatch.setattr(matches,'now',lambda:at)
    monkeypatch.setattr(module,'now',lambda:at)
    class DelayedLease(Limits):
        async def lease(self,key,seconds=300):
            nonlocal at
            at+=timedelta(seconds=1.5)
            return await super().lease(key,seconds)
    class Response:
        async def request(self,*args,**kwargs):calls.append(at);return payload()
    monkeypatch.setattr(matches,'limits',DelayedLease())
    monkeypatch.setattr(matches,'http',Response())
    for offset in (0,30,60):
        at=start+timedelta(seconds=offset)
        await matches.refresh_day(at.date())
    assert len(calls)==3

@pytest.mark.asyncio
async def test_shared_cache_many_readers_cannot_use_paid_credits(database,monkeypatch):
    calls=[]
    def mock(request):calls.append(request);return httpx.Response(200,json=payload())
    monkeypatch.setattr(matches,'http',SafeHTTP(Limits(),httpx.MockTransport(mock)))
    await matches.refresh_day(now().date());await matches.refresh_day(now().date())
    for _ in range(5):
        async with database() as session:assert len((await matches.feed(session,now().date()))['games'])==1
        await matches.enqueue(now().date())
    await matches.tick()
    assert len(calls)==1
    async with database() as session:
        assert await session.scalar(select(func.count()).select_from(ProviderCall))==0
        assert (await session.get(RuntimeLimit,f'nhl_scores:{now().date()}')).used==1
        assert await session.scalar(select(func.count()).select_from(ProviderState).where(ProviderState.provider.like('nhl-request:%')))==1

@pytest.mark.asyncio
async def test_failure_keeps_good_scores_and_observation_time(database,monkeypatch):
    at=now()-timedelta(minutes=5)
    async with database.begin() as session:session.add(ProviderState(provider=f'nhl-score:{now().date()}',observed_at=at,
        info={'games':matches.parse_scores(payload(),now().date()),'next_at':at.isoformat(),'interval_seconds':30}))
    count=[]
    def fail(request):count.append(request);return httpx.Response(500)
    monkeypatch.setattr(matches,'http',SafeHTTP(Limits(),httpx.MockTransport(fail)))
    await matches.refresh_day(now().date());await matches.tick()
    async with database() as session:
        feed=await matches.feed(session,now().date())
        assert feed['observed_at']==at and feed['games'][0]['home_score']==3 and feed['stale'] and feed['paused']
    assert len(count)==1

@pytest.mark.asyncio
async def test_rate_limit_no_retry_and_respects_long_retry_after(database):
    calls=[]
    def response(request):calls.append(request);return httpx.Response(429,headers={'Retry-After':'3600'})
    with pytest.raises(ProviderError):await SafeHTTP(Limits(),httpx.MockTransport(response)).request('nhl_scores','GET','https://api-web.nhle.com/v1/score/now')
    async with database() as session:
        block=await session.get(RuntimeLimit,'circuit:nhl_scores')
        assert (block.blocked_until-now()).total_seconds()>3500
    assert len(calls)==1

@pytest.mark.asyncio
async def test_score_daily_cap_independent_of_odds_and_pause(database,monkeypatch):
    import app.limits as module
    monkeypatch.setattr(module,'settings',replace(settings,nhl_score_daily_requests=2))
    guard=Limits();await guard.pause(True)
    await guard.reserve('nhl_scores');await guard.reserve('nhl_scores')
    with pytest.raises(BudgetExceeded):await guard.reserve('nhl_scores')
    assert (await guard.odds_window())['used']==0

@pytest.mark.asyncio
async def test_feed_orders_live_future_final_and_downgrades_unverified_play(database):
    games=[]
    for state,gid in [('OFF',1),('FUT',2),('LIVE',3)]:games+=matches.parse_scores(payload(state,gid),now().date())
    await Limits().observe(f'nhl-score:{now().date()}',{'games':games,'next_at':(now()+timedelta(seconds=30)).isoformat(),'interval_seconds':30})
    async with database.begin() as session:session.add(Fixture(id='nhl:2',sport='NHL',home='QA Home',away='QA Away',commence_time=now()+timedelta(hours=2),state=State.RECOMMEND,dirty=False,metrics={},gates={}))
    async with database() as session:
        feed=await matches.feed(session,now().date())
        assert [g['game_state'] for g in feed['games']]==['LIVE','FUT','OFF']
        assert feed['games'][1]['decision']=='HOLD' and not feed['games'][1]['verified_play']

@pytest.mark.asyncio
async def test_match_endpoints_auth_dates_and_read_only(database,monkeypatch):
    async def forbidden(*args,**kwargs):raise AssertionError('Browser endpoints must never request a provider')
    monkeypatch.setattr(matches.http,'request',forbidden)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        assert (await client.get('/matches')).status_code==401
        assert (await client.post('/matches/sync',json={'date':str(now().date())})).status_code==401
        client.headers['Authorization']='Bearer '+settings.admin_token
        assert (await client.get('/matches?date=bad')).status_code==422
        assert (await client.get('/matches')).status_code==200
        assert (await client.post('/matches/sync',json={'date':str(now().date())})).json()['paid_credits']==0

@pytest.mark.asyncio
async def test_distinct_worker_instances_share_one_score_attempt(tmp_path,monkeypatch):
    engine=create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "score-cache.sqlite"}')
    async with engine.begin() as connection:await connection.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(db,'Session',async_sessionmaker(engine,expire_on_commit=False))
    calls=[]
    async def response(request):
        calls.append(request)
        await asyncio.sleep(.03)
        return httpx.Response(200,json=payload())
    monkeypatch.setattr(matches,'http',SafeHTTP(Limits(),httpx.MockTransport(response)))
    try:
        await asyncio.gather(*(matches.refresh_day(now().date()) for _ in range(6)))
        assert len(calls)==1
    finally:await engine.dispose()
