import asyncio
from dataclasses import replace
from datetime import datetime,timedelta
from uuid import uuid4
import httpx
import pytest
from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from app import db,providers,manual_odds
from app.api import app
from app.clock import now,PACIFIC
from app.config import settings
from app.http import SafeHTTP
from app.limits import Limits,BudgetExceeded
from app.models import Base,Fixture,ProviderCall,MarketOdds,RuntimeLimit

HEADERS={'Authorization':'Bearer test-session-token-32-characters-long'}

async def test_api_root_redirects_to_dashboard_without_database():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        for method in ('GET','HEAD'):
            result=await client.request(method,'/')
            assert result.status_code==307 and result.headers['location']=='https://sports-intelligence-dashboard.onrender.com/'

async def test_five_attempts_rolling_across_midnight_and_restarts(database,monkeypatch):
    import app.limits as module
    at=datetime(2026,10,13,23,55,tzinfo=PACIFIC)
    monkeypatch.setattr(module,'now',lambda:at)
    for i in range(5):
        guard=Limits();ident=await guard.reserve('odds',3,identity=f'attempt:{i}');await guard.finish(ident,'SUCCEEDED')
    at+=timedelta(minutes=10)
    window=await Limits().odds_window()
    assert window['used']==5 and window['remaining']==0
    assert window['next_available_at']==datetime(2026,10,14,23,55,tzinfo=PACIFIC)
    with pytest.raises(BudgetExceeded):await Limits().reserve('odds',3,identity='sixth')
    assert not await Limits().attempted('odds','sixth')
    at=datetime(2026,10,14,23,55,tzinfo=PACIFIC)
    assert (await Limits().odds_window())['remaining']==5
    await Limits().reserve('odds',3,identity='after-24-hours')
    async with database() as session:assert await session.scalar(select(func.count()).select_from(ProviderCall))==6

async def setup_quotes(database,monkeypatch,fail=False):
    config=replace(settings,odds_key='test-only',active_sports=('NHL',),odds_daily_credits=15)
    monkeypatch.setattr(providers,'settings',config);monkeypatch.setattr(manual_odds,'settings',config)
    monkeypatch.setattr('app.limits.settings',config)
    start=now()+timedelta(hours=2)
    async with database.begin() as session:
        session.add(Fixture(id='nhl:manual',sport='NHL',home='Home',away='Away',commence_time=start))
    calls=[]
    def response(request):
        if request.url.path=='/v4/sports/':return httpx.Response(200,json=[{'key':'icehockey_nhl'}],headers={
            'x-requests-remaining':str(500-len(calls)*3),'x-requests-used':str(len(calls)*3),'x-requests-last':'0'})
        assert '/icehockey_nhl/odds/' in request.url.path
        calls.append(request)
        if fail:raise httpx.ReadTimeout('An uncertain provider response')
        return httpx.Response(200,json=[{'id':'external','commence_time':start.isoformat(),'home_team':'Home','away_team':'Away',
            'bookmakers':[{'key':'playnow_ca','last_update':now().isoformat(),'markets':[{'key':'h2h',
                'outcomes':[{'name':'Home','price':2},{'name':'Away','price':1.9}]}]}]}],headers={
            'x-requests-remaining':str(500-len(calls)*3),'x-requests-used':str(len(calls)*3),'x-requests-last':'3'})
    monkeypatch.setattr(providers,'http',SafeHTTP(Limits(),httpx.MockTransport(response)))
    return calls

async def test_manual_api_is_private_idempotent_and_can_refresh_twice_within_two_hours(database,monkeypatch):
    calls=await setup_quotes(database,monkeypatch)
    request_id=str(uuid4());url='/operations/odds-refresh'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        assert (await client.post(url,json={'request_id':request_id})).status_code==401
        assert (await client.get(f'{url}/{request_id}')).status_code==401
        for _ in range(2):
            result=await client.post(url,headers=HEADERS,json={'request_id':request_id})
            assert result.status_code==200,result.text
            assert result.json()['status']=='succeeded' and result.json()['credits_reserved']==3
        assert len(calls)==1
        assert (await client.get(f'{url}/{request_id}',headers=HEADERS)).json()['status']=='succeeded'
        assert (await client.post(url,headers=HEADERS,json={'request_id':str(uuid4())})).json()['status']=='succeeded'
        await client.get('/dashboard',headers=HEADERS);await client.get('/operations',headers=HEADERS)
        assert len(calls)==2
    async with database() as session:assert await session.scalar(select(func.count()).select_from(MarketOdds))>=2

async def test_sixth_click_never_reaches_provider(database,monkeypatch):
    calls=await setup_quotes(database,monkeypatch)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers=HEADERS) as client:
        for _ in range(5):assert (await client.post('/operations/odds-refresh',json={'request_id':str(uuid4())})).json()['status']=='succeeded'
        denied=await client.post('/operations/odds-refresh',json={'request_id':str(uuid4())})
        assert denied.status_code==429 and len(calls)==5
        window=(await client.get('/operations')).json()['odds_refresh']
        assert window['used']==5 and window['remaining']==0 and window['next_available_at']

async def test_failed_refresh_is_not_repeated_and_keeps_its_slot(database,monkeypatch):
    calls=await setup_quotes(database,monkeypatch,fail=True)
    request_id=str(uuid4())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers=HEADERS) as client:
        assert (await client.post('/operations/odds-refresh',json={'request_id':request_id})).status_code==503
        result=await client.post('/operations/odds-refresh',json={'request_id':request_id})
        assert result.json()['status']=='unknown' and len(calls)==1
    assert (await Limits().odds_window())['used']==1 and await Limits().blocked('odds')

async def test_no_games_does_not_use_refresh_slot(database,monkeypatch):
    monkeypatch.setattr(manual_odds,'settings',replace(settings,odds_key='test-only'))
    async def forbidden(*args,**kwargs):raise AssertionError('No games must not call a provider')
    monkeypatch.setattr(manual_odds,'ingest_odds',forbidden)
    result=await manual_odds.refresh(uuid4())
    assert result['status']=='skipped' and (await Limits().odds_window())['used']==0

async def test_interrupted_call_blocks_new_id_until_explicit_resume_without_refund(database,monkeypatch):
    import app.limits as module
    at=now();monkeypatch.setattr(module,'now',lambda:at)
    ident=await Limits().reserve('odds',3,identity='interrupted',fixture_id=f'odds-refresh:{uuid4()}')
    at+=timedelta(seconds=61)
    assert (await Limits().odds_window())['needs_resume']
    with pytest.raises(BudgetExceeded):await Limits().reserve('odds',3,identity='new')
    await Limits().resume('odds')
    assert not (await Limits().odds_window())['needs_resume']
    assert (await Limits().odds_window())['used']==1
    async with database() as session:assert (await session.get(ProviderCall,ident)).status=='UNKNOWN'
    with pytest.raises(BudgetExceeded):await Limits().reserve('odds',3,identity='interrupted')
    await Limits().reserve('odds',3,identity='new')

async def test_concurrent_distinct_requests_cannot_exceed_five(tmp_path,monkeypatch):
    engine=create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "manual.sqlite"}')
    async with engine.begin() as connection:await connection.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(db,'Session',async_sessionmaker(engine,expire_on_commit=False))
    def response(request):return httpx.Response(200,json=[],headers={'x-requests-remaining':'490','x-requests-used':'10','x-requests-last':'3'})
    async def request(i):
        try:await SafeHTTP(Limits(),httpx.MockTransport(response)).request('odds','GET','https://example.test',cost=3,identity=f'distinct:{i}');return True
        except BudgetExceeded:return False
    try:
        results=await asyncio.gather(*(request(i) for i in range(9)))
        # In-progress protection can reject additional overlapping requests too.
        assert 1<=sum(results)<=5 and (await Limits().odds_window())['used']==sum(results)
    finally:await engine.dispose()

def test_scheduler_has_no_automatic_or_startup_odds_job(monkeypatch):
    import app.scheduler as module
    class Scheduler:
        jobs=[]
        def add_job(self,*args,**kwargs):self.jobs.append(kwargs['id'])
        def start(self):pass
    scheduled=Scheduler();monkeypatch.setattr(module,'scheduler',scheduled)
    module.start()
    assert 'gates' in scheduled.jobs and 'startup' in scheduled.jobs
    assert not any('odds' in job for job in scheduled.jobs)
