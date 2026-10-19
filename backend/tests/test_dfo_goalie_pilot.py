"""Bounded public-page parsing and durable shadow-feed integration tests."""
from copy import deepcopy
from datetime import timedelta
import gzip
import json

import httpx
import pytest
from sqlalchemy import select,func

from app.clock import now,aware
from app.dfo_public import parse_page,page_url,robots_allowed,SourceFormatError,ORIGIN,MAX_HTML
from app import nhl_goalie_pilot as pilot
from app.models import Fixture,ProviderState,RuntimeLimit,Evidence,ProviderCall,AuditLog,Snapshot
from app.limits import BudgetExceeded
from app.api import app

HEADERS={'Authorization':'Bearer test-session-token-32-characters-long'}


def source_row(at):
    row={'homeTeamName':'Montreal Canadiens','awayTeamName':'Toronto Maple Leafs',
        'date':str(at.date()),'dateGmt':(at+timedelta(hours=2)).isoformat()}
    for side,name in [('home','Home Starter'),('away','Away Starter')]:
        row.update({side+'GoalieName':name,side+'NewsStrengthName':'Confirmed',
            side+'NewsCreatedAt':(at-timedelta(minutes=15)).isoformat(),
            side+'NewsSourceUrl':'https://x.com/reporter/status/12345?s=20',
            side+'NewsDetails':'Do not copy this article prose',side+'GoalieOverallScore':100,
            side+'TeamMoneylinePointSpread':-200,side+'GoalieId':'not-an-nhl-player-id'})
    return row


def html(at,rows=None,**props):
    payload={'page':'/starting-goalies/[[...date]]','props':{'pageProps':{
        'date':str(at.date()),'data':[source_row(at)] if rows is None else rows,**props}}}
    return ('<html><script id="__NEXT_DATA__" type="application/json">'+json.dumps(payload)+'</script></html>').encode()


def test_public_factual_extraction_excludes_prose_ratings_bookmaker_and_dfo_player_ids():
    at=now();result=parse_page(html(at),at.date(),at)
    assert result['games'][0]['sides']['home']=={'name':'Home Starter','reported_status':'confirmed',
        'reported_at':(at-timedelta(minutes=15)).isoformat(),'reporter_url':'https://x.com/reporter/status/12345'}
    assert all(value not in json.dumps(result) for value in ('Do not copy','OverallScore','Moneyline','not-an-nhl-player-id'))


@pytest.mark.parametrize('change',['date','duplicate','future','no_source','no_name','credentials','private_ip','missing_script','oversized','unclosed_json'])
def test_changed_ambiguous_or_unsafe_public_page_fails_closed(change):
    at=now();row=source_row(at);body=None;props={};rows=[row]
    if change=='date':props['date']=str((at+timedelta(days=1)).date())
    if change=='duplicate':rows.append(deepcopy(row))
    if change=='future':row['homeNewsCreatedAt']=(at+timedelta(seconds=1)).isoformat()
    if change=='no_source':row['homeNewsSourceUrl']=None
    if change=='no_name':row['homeGoalieName']=None
    if change=='credentials':row['homeNewsSourceUrl']='https://user:secret@x.com/private'
    if change=='private_ip':row['homeNewsSourceUrl']='https://127.0.0.1/private'
    if change=='missing_script':body=b'<html><script>console.log(1)</script></html>'
    if change=='oversized':body=b'x'*(MAX_HTML+1)
    if change=='unclosed_json':body=b'<script id="__NEXT_DATA__">{bad}</script>'
    with pytest.raises(SourceFormatError):parse_page(body or html(at,rows,**props),at.date(),at)


@pytest.mark.parametrize('reported,expected',[('Likely','expected'),('Expected','expected'),('Unconfirmed','unconfirmed'),('Surprise','unknown'),(None,'unconfirmed')])
def test_expected_and_unknown_are_never_promoted_to_confirmed(reported,expected):
    at=now();row=source_row(at);row['homeNewsStrengthName']=reported
    assert parse_page(html(at,[row]),at.date(),at)['games'][0]['sides']['home']['reported_status']==expected


@pytest.mark.parametrize('text,allowed',[
    ('User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /cms/',True),
    ('User-agent: *\nAllow: /\nDisallow: /starting-goalies',False),
    ('User-agent: *\nDisallow: /\nAllow: /starting-goalies/',True),
    ('User-agent: *\nAllow: /\nUser-agent: GSportsIntelligence\nDisallow: /',False),
    ('User-agent: *\nDisallow: /starting-goalies/*\nAllow: /starting-goalies/*',True),
])
def test_robots_uses_specific_rules_and_equal_length_allow_tie(text,allowed):
    assert robots_allowed(text.encode(),page_url(now().date())) is allowed


def test_slower_source_crawl_policy_stops_the_pilot():
    with pytest.raises(SourceFormatError):robots_allowed(b'User-agent: *\nCrawl-delay: 1200',page_url(now().date()))


async def seed(database,at):
    fixture=Fixture(id='nhl:2026029999',sport='NHL',home='Montréal Canadiens',away='Toronto Maple Leafs',
        commence_time=at+timedelta(hours=2),metrics={'home_abbrev':'MTL','away_abbrev':'TOR',
            'nhl_goalie_comparison':{'observed_at':at.isoformat(),'sides':{
                'home':[{'player_id':'8480001','name':'Home Starter','season_appearances':3}],
                'away':[{'player_id':'8480002','name':'Away Starter','season_appearances':4}]}},
            'personnel_confirmed':True,'confirmed_at':at.isoformat(),'starter_confirmation_method':'manual_operator',
            'goalie_confirmations':{'home':'Different Starter','away':'Away Starter'}},gates={},dirty=False,revision=2)
    async with database.begin() as session:session.add(fixture)
    return fixture


def transport(at,calls,*,status=200,body=None,robots=b'User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /cms/',etag='"page-v1"'):
    def respond(request):
        calls.append(request)
        if request.url.path=='/robots.txt':
            return httpx.Response(200,headers={'content-type':'text/plain'},stream=httpx.ByteStream(robots))
        assert request.url.path==f'/starting-goalies/{at.date()}'
        data=gzip.compress(body or html(at))
        return httpx.Response(status,headers={'content-type':'text/html','content-encoding':'gzip','etag':etag,
            'location':'https://must-not-follow.test/private?secret=1'},stream=httpx.ByteStream(data))
    return httpx.MockTransport(respond)


async def test_shadow_collect_maps_players_and_exposes_conflict_without_changing_manual_or_forecast(database,monkeypatch):
    at=now();fixture=await seed(database,at);calls=[]
    monkeypatch.setattr(pilot,'now',lambda:at)
    await pilot.control('start')
    result=await pilot.collect(manual=True,transport=transport(at,calls))
    assert result['status']=='succeeded' and result['matched_games']==1 and len(calls)==2
    async with database() as session:
        saved=await session.get(Fixture,fixture.id)
        assert saved.metrics==fixture.metrics and saved.gates=={} and saved.dirty is False and saved.revision==2
        assert saved.probability is None and await session.get(Snapshot,fixture.id) is None
        report=await pilot.detail(session,saved)
        assert report['sides']['home']['comparison']=='conflicts_manual'
        assert report['sides']['away']['comparison']=='matches_manual'
        assert report['sides']['home']['player_id']=='8480001'
        evidence=await session.scalar(select(Evidence))
        assert evidence.kind=='nhl_goalie_report' and aware(evidence.observed_at)==at
        assert evidence.payload['report']['sides']['home']['reported_at']!=(evidence.observed_at.isoformat())
        assert await session.scalar(select(func.count()).select_from(ProviderCall))==0
        assert (await session.get(RuntimeLimit,f'dfo-requests:{at.date()}')).used==2
        assert 0<(await session.get(RuntimeLimit,f'dfo-wire-day:{at.date()}')).used<10000
    with pytest.raises(BudgetExceeded):await pilot.collect(manual=True,transport=transport(at,calls))
    assert len(calls)==2


@pytest.mark.parametrize('code',[302,403,429,500])
async def test_access_failure_halts_without_retry_or_refund_across_restart_and_resume(database,monkeypatch,code):
    at=now();await seed(database,at);calls=[]
    monkeypatch.setattr(pilot,'now',lambda:at)
    await pilot.control('start')
    assert (await pilot.collect(manual=True,transport=transport(at,calls,status=code)))['status']=='failed'
    async with database() as session:
        state=await pilot.status(session)
        assert state['phase']=='halted' and state['bytes_reserved_today']==2*pilot.MAX_WIRE
        assert 'must-not-follow' not in json.dumps(state) and 'secret' not in json.dumps(state)
        assert await session.scalar(select(func.count()).select_from(Evidence))==0
    with pytest.raises(BudgetExceeded):await pilot.collect(manual=True,transport=transport(at,calls))
    await pilot.control('resume')
    with pytest.raises(BudgetExceeded):await pilot.collect(manual=True,transport=transport(at,calls))
    assert len(calls)==2


async def test_limits_are_atomic_and_start_pause_resume_cannot_extend_or_reset_them(database,monkeypatch):
    at=now();await seed(database,at)
    monkeypatch.setattr(pilot,'now',lambda:at)
    await pilot.control('start')
    async with database.begin() as session:
        session.add(RuntimeLimit(key=f'dfo-requests:{at.date()}',used=pilot.DAILY_REQUESTS-1))
    with pytest.raises(BudgetExceeded):await pilot.reserve()
    await pilot.control('pause')
    with pytest.raises(BudgetExceeded):await pilot.control('start')
    await pilot.control('resume')
    async with database() as session:
        state=await pilot.status(session)
        assert state['expires_at']==(at+timedelta(hours=72)).isoformat()
        assert state['requests_reserved_today']==pilot.DAILY_REQUESTS-1
        assert await session.get(RuntimeLimit,f'dfo-wire-day:{at.date()}') is None
    monkeypatch.setattr(pilot,'now',lambda:at+timedelta(hours=72))
    with pytest.raises(BudgetExceeded):await pilot.reserve()
    with pytest.raises(BudgetExceeded):await pilot.control('resume')


async def test_etag_304_reuses_valid_facts_and_deduplicates_evidence(database,monkeypatch):
    at=now();fixture=await seed(database,at);calls=[]
    monkeypatch.setattr(pilot,'now',lambda:at)
    await pilot.control('start')
    await pilot.collect(manual=True,transport=transport(at,calls))
    monkeypatch.setattr(pilot,'now',lambda:at+timedelta(minutes=11))
    def unchanged(request):
        calls.append(request)
        assert request.headers['if-none-match']=='"page-v1"' and request.url.path!='/robots.txt'
        return httpx.Response(304,stream=httpx.ByteStream(b''))
    assert (await pilot.collect(manual=True,transport=httpx.MockTransport(unchanged)))['status']=='succeeded'
    async with database() as session:
        report=await session.get(ProviderState,'dfo:'+fixture.id)
        assert aware(report.observed_at)==at+timedelta(minutes=11) and aware(report.info['first_observed_at'])==at
        assert await session.scalar(select(func.count()).select_from(Evidence))==1
        assert (await pilot.status(session))['requests_reserved_today']==3


async def test_retraction_and_missing_report_remain_visible_without_rewriting_manual_selection(database,monkeypatch):
    at=now();fixture=await seed(database,at);calls=[]
    monkeypatch.setattr(pilot,'now',lambda:at)
    await pilot.control('start')
    await pilot.collect(manual=True,transport=transport(at,calls))
    monkeypatch.setattr(pilot,'now',lambda:at+timedelta(minutes=11))
    row=source_row(at);row['homeNewsStrengthName']='Expected'
    await pilot.collect(manual=True,transport=transport(at,calls,body=html(at,[row])))
    async with database() as session:
        saved=await session.get(Fixture,fixture.id)
        assert saved.metrics['goalie_confirmations']['home']=='Different Starter'
        assert (await pilot.detail(session,saved))['sides']['home']['comparison']=='source_unconfirmed'
        assert await session.scalar(select(func.count()).select_from(Evidence))==2
    monkeypatch.setattr(pilot,'now',lambda:at+timedelta(minutes=22))
    await pilot.collect(manual=True,transport=transport(at,calls,body=html(at,[])))
    async with database() as session:
        report=await pilot.detail(session,await session.get(Fixture,fixture.id))
        assert report['status']=='stale' and report['missing_from_page'] is True


async def test_policy_denial_stops_before_requesting_the_source_page(database,monkeypatch):
    at=now();await seed(database,at);calls=[]
    monkeypatch.setattr(pilot,'now',lambda:at)
    await pilot.control('start')
    result=await pilot.collect(manual=True,transport=transport(at,calls,robots=b'User-agent: *\nAllow: /\nDisallow: /starting-goalies'))
    assert result['status']=='failed' and len(calls)==1
    async with database() as session:assert (await pilot.status(session))['phase']=='halted'


async def test_compressed_oversize_payload_is_bounded_and_failed_budget_retained(database,monkeypatch):
    at=now();await seed(database,at);calls=[]
    monkeypatch.setattr(pilot,'now',lambda:at)
    await pilot.control('start')
    result=await pilot.collect(manual=True,transport=transport(at,calls,body=b'x'*(MAX_HTML+1)))
    assert result['status']=='failed' and result['reason']=='Source decoded-byte limit exceeded'
    async with database() as session:assert (await pilot.status(session))['bytes_reserved_today']==2*pilot.MAX_WIRE


async def test_private_status_and_match_reads_never_fetch_source_and_controls_require_auth(database,monkeypatch):
    at=now();fixture=await seed(database,at)
    async def forbidden(*args,**kwargs):raise AssertionError('Read endpoints must use saved state only')
    monkeypatch.setattr(pilot,'collect',forbidden)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        assert (await client.post('/operations/nhl-goalie-pilot',json={'action':'start'})).status_code==401
        result=(await client.get('/operations',headers=HEADERS)).json()
        assert result['nhl_goalie_pilot']['phase']=='not_started'
        result=(await client.get(f'/fixtures/{fixture.id}',headers=HEADERS)).json()
        assert result['nhl_goalie_report']['status']=='missing'
        assert (await client.post('/operations/nhl-goalie-pilot',headers=HEADERS,json={'action':'arbitrary-url'})).status_code==422

async def test_official_ids_remain_identity_references_without_renewing_stale_statistics(database,monkeypatch):
    from app.nhl_advanced import CACHE_KEY
    at=now();fixture=await seed(database,at)
    async with database.begin() as session:
        saved=await session.get(Fixture,fixture.id)
        saved.metrics={**saved.metrics,'nhl_goalie_comparison':{}}
        session.add(ProviderState(provider=CACHE_KEY,observed_at=at-timedelta(days=3),info={
            'schema_version':1,'model_approved_by_import':False,'goalies':{
                '8480001':{'player_id':'8480001','name':'Home Starter','latest_team':'MTL'},
                '8480002':{'player_id':'8480002','name':'Away Starter','latest_team':'TOR'}}}))
    monkeypatch.setattr(pilot,'now',lambda:at)
    await pilot.control('start')
    await pilot.collect(manual=True,transport=transport(at,[]))
    async with database() as session:
        saved=await session.get(Fixture,fixture.id)
        report=await pilot.detail(session,saved)
        assert report['sides']['home']['player_id']=='8480001'
        assert report['sides']['home']['identity_source']=='saved_goalie_history'
        assert aware((await session.get(ProviderState,CACHE_KEY)).observed_at)==at-timedelta(days=3)
        assert saved.gates=={} and saved.metrics=={**fixture.metrics,'nhl_goalie_comparison':{}}


async def test_scheduled_collection_is_idle_after_start_and_postgame_manual_observations_stay_review_only(database,monkeypatch):
    at=now();fixture=await seed(database,at)
    monkeypatch.setattr(pilot,'now',lambda:at)
    await pilot.control('start')
    later=at+timedelta(hours=3)
    monkeypatch.setattr(pilot,'now',lambda:later)
    calls=[]
    assert (await pilot.collect(transport=transport(at,calls)))['status']=='idle' and not calls
    assert (await pilot.collect(manual=True,transport=transport(at,calls)))['status']=='succeeded'
    async with database() as session:
        saved=await session.get(Fixture,fixture.id)
        assert (await pilot.detail(session,saved))['pregame'] is False
        row=await session.scalar(select(Evidence))
        assert aware(row.observed_at)==later and aware(row.source_at)==later
        assert saved.probability is None and await session.get(Snapshot,fixture.id) is None


async def test_ambiguous_game_and_player_identity_are_never_guessed(database,monkeypatch):
    at=now();fixture=await seed(database,at)
    async with database.begin() as session:
        saved=await session.get(Fixture,fixture.id)
        changed=deepcopy(saved.metrics)
        changed['nhl_goalie_comparison']['sides']['home'].append({'player_id':'8480003','name':'Home Starter','season_appearances':3})
        saved.metrics=changed
    monkeypatch.setattr(pilot,'now',lambda:at)
    await pilot.control('start')
    await pilot.collect(manual=True,transport=transport(at,[]))
    async with database() as session:
        report=await pilot.detail(session,await session.get(Fixture,fixture.id))
        assert report['sides']['home']['player_id'] is None
    async with database.begin() as session:
        session.add(Fixture(id='nhl:2026029998',sport='NHL',home=fixture.home,away=fixture.away,
            commence_time=fixture.commence_time,metrics={},gates={}))
    monkeypatch.setattr(pilot,'now',lambda:at+timedelta(minutes=11))
    result=await pilot.collect(manual=True,transport=transport(at,[]))
    assert result['matched_games']==0
    async with database() as session:
        report=await pilot.detail(session,await session.get(Fixture,fixture.id))
        assert report['missing_from_page'] and report['status']=='stale'


async def test_interrupted_attempt_does_not_restart_automatically_and_reservations_survive(database,monkeypatch):
    at=now();await seed(database,at)
    monkeypatch.setattr(pilot,'now',lambda:at)
    await pilot.control('start')
    await pilot.reserve()
    monkeypatch.setattr(pilot,'now',lambda:at+timedelta(minutes=11))
    with pytest.raises(BudgetExceeded):await pilot.reserve()
    async with database() as session:
        state=await pilot.status(session)
        assert state['phase']=='halted' and state['requests_reserved_today']==2
        assert state['bytes_reserved_today']==2*pilot.MAX_WIRE
    await pilot.control('resume')
    admission=await pilot.reserve()
    assert admission['reserved']==2*pilot.MAX_WIRE
    async with database() as session:assert (await pilot.status(session))['requests_reserved_today']==4

async def test_cached_robots_policy_is_rechecked_for_the_next_date_without_a_network_call(database,monkeypatch):
    from datetime import datetime,time
    from app.config import PACIFIC
    at=now();await seed(database,at)
    monkeypatch.setattr(pilot,'now',lambda:at)
    await pilot.control('start')
    next_day=at.date()+timedelta(days=1)
    text=f'User-agent: *\nAllow: /\nDisallow: /starting-goalies/{next_day}'
    async with database.begin() as session:
        session.add(ProviderState(provider=pilot.ROBOTS,observed_at=at,info={'allowed':True,'policy_text':text}))
    monkeypatch.setattr(pilot,'now',lambda:datetime.combine(next_day,time(0,5),PACIFIC))
    with pytest.raises(BudgetExceeded,match='crawler policy'):await pilot.reserve()
    async with database() as session:
        assert await session.scalar(select(func.count()).select_from(RuntimeLimit))==0

async def test_authenticated_control_queues_one_shared_source_read_and_rejects_early_repeat(database,monkeypatch):
    at=now();fixture=await seed(database,at);calls=[]
    monkeypatch.setattr(pilot,'now',lambda:at)
    original=pilot.collect
    async def mock_collect(**kwargs):return await original(**kwargs,transport=transport(at,calls))
    monkeypatch.setattr(pilot,'collect',mock_collect)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers=HEADERS) as client:
        response=await client.post('/operations/nhl-goalie-pilot',json={'action':'start'})
        assert response.status_code==202 and response.json()['mode']=='shadow'
        assert len(calls)==2
        assert (await client.post('/operations/nhl-goalie-pilot',json={'action':'check'})).status_code==429
        assert len(calls)==2
        assert (await client.get(f'/fixtures/{fixture.id}')).json()['nhl_goalie_report']['status']=='fresh'
        assert (await client.post('/operations/nhl-goalie-pilot',json={'action':'pause'})).status_code==202
        assert (await client.get('/operations')).json()['nhl_goalie_pilot']['phase']=='paused'
        assert len(calls)==2
