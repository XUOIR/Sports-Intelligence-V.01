from copy import deepcopy
from datetime import timedelta
import json
from types import SimpleNamespace
import httpx
import pytest
from sqlalchemy import select,func
from app import nhl_starter_validation as check
from app.clock import now
from app.models import Fixture,Evidence,ProviderState,RuntimeLimit,ProviderCall


def fixture(at):
    return SimpleNamespace(id='nhl:2026020101',home='Home Team',away='Away Team',
        commence_time=at,metrics={'home_abbrev':'MTL','away_abbrev':'TOR'})


def payload(f):
    return {'id':2026020101,'gameState':'OFF','gameType':2,'startTimeUTC':f.commence_time.isoformat(),
        'homeTeam':{'abbrev':'MTL'},'awayTeam':{'abbrev':'TOR'},'playerByGameStats':{
            side+'Team':{'goalies':[{'playerId':8480001+i,'name':{'default':side+' Starter'},'starter':True,'toi':'01:00'},
                {'playerId':8480003+i,'name':{'default':'Relief Goalie'},'starter':False,'toi':'59:00'}]}
            for i,side in enumerate(('home','away'))}}


def report(at,start,home='8480001',status='confirmed'):
    return {'id':1,'observed_at':at.isoformat(),'payload':{'contract':'dfo-public-goalie-report-v1',
        'fixture_start_at':start.isoformat(),'report':{'sides':{side:{'player_id':home if side=='home' else '8480002',
            'name':side+' report','reported_status':status,'reported_at':(at-timedelta(minutes=2)).isoformat()}
            for side in ('home','away')}}}}


def test_explicit_official_flag_wins_over_time_played():
    f=fixture(now());p=payload(f)
    assert check.official_starters(p,f)['home']['player_id']=='8480001'
    for row in p['playerByGameStats']['homeTeam']['goalies']:row.pop('starter')
    with pytest.raises(ValueError):check.official_starters(p,f)


@pytest.mark.parametrize('change',['wrong_game','wrong_start','live','team','duplicate'])
def test_ambiguous_or_nonfinal_official_truth_is_rejected(change):
    f=fixture(now());p=payload(f)
    if change=='wrong_game':p['id']+=1
    if change=='wrong_start':p['startTimeUTC']=(now()+timedelta(minutes=1)).isoformat()
    if change=='live':p['gameState']='LIVE'
    if change=='team':p['homeTeam']['abbrev']='BOS'
    if change=='duplicate':p['playerByGameStats']['homeTeam']['goalies'][1]['starter']=True
    with pytest.raises(ValueError):check.official_starters(p,f)


def test_late_corrected_report_cannot_rewrite_pregame_or_t30_grade():
    start=now();truth={'start_at':start.isoformat(),'sides':{'home':{'player_id':'8480001'},'away':{'player_id':'8480002'}}}
    before=report(start-timedelta(minutes=2),start,home='8489999')
    late=report(start+timedelta(seconds=1),start)
    # A post-start observation stays late even if its source news timestamp is old.
    late['payload']['report']['sides']['home']['reported_at']=(start-timedelta(hours=2)).isoformat()
    assert check.grade([before,late],truth,start)['home']['status']=='mismatched'
    assert check.grade([before,late],truth,start-timedelta(minutes=30))['home']['status']=='not_observed_before_cutoff'


def test_expected_is_scored_separately_and_stale_reports_have_no_accuracy_credit():
    start=now();truth={'start_at':start.isoformat(),'sides':{'home':{'player_id':'8480001'},'away':{'player_id':'8480002'}}}
    r=report(start-timedelta(minutes=10),start,status='expected')
    graded=check.grade([r],truth,start)
    assert graded['home']['status']=='matched' and graded['home']['report_status']=='expected'
    assert check.grade([r],truth,start+timedelta(minutes=11))['home']['status']=='stale'


def test_removal_receipt_overrides_an_earlier_confirmed_report():
    start=now();truth={'start_at':start.isoformat(),'sides':{'home':{'player_id':'8480001'},'away':{'player_id':'8480002'}}}
    previous=report(start-timedelta(minutes=10),start)
    removed={'id':2,'observed_at':(start-timedelta(minutes=1)).isoformat(),'payload':{
        'contract':'dfo-public-goalie-report-v1','fixture_start_at':start.isoformat(),'missing_from_page':True}}
    assert check.grade([previous,removed],truth,start)['home']['status']=='source_removed'


async def seed(database):
    f=fixture(now()-timedelta(hours=5))
    async with database.begin() as s:
        s.add(Fixture(id=f.id,sport='NHL',home=f.home,away=f.away,commence_time=f.commence_time,
            metrics=f.metrics,final_home_win=True))
        r=report(f.commence_time-timedelta(minutes=1),f.commence_time)
        s.add(Evidence(fixture_id=f.id,kind='nhl_goalie_report',source_at=f.commence_time-timedelta(minutes=1),
            observed_at=f.commence_time-timedelta(minutes=1),payload=r['payload']))
    return f


@pytest.mark.asyncio
async def test_one_free_postgame_check_is_durable_and_does_not_confirm_pregame(database):
    f=await seed(database);calls=[]
    def handle(request):
        calls.append(str(request.url))
        return httpx.Response(200,headers={'content-type':'application/json'},stream=httpx.ByteStream(json.dumps(payload(f)).encode()))
    transport=httpx.MockTransport(handle)
    assert (await check.verify_fixture(f.id,transport=transport))['status']=='verified'
    assert (await check.verify_fixture(f.id,transport=transport))['status']=='already_attempted'
    assert len(calls)==1
    async with database() as s:
        result=await check.summary(s)
        assert result['last_pregame']['correct']==2 and result['at_t30']['graded_sides']==0
        assert await s.scalar(select(func.count()).select_from(ProviderCall))==0
        saved=await s.get(Fixture,f.id)
        assert saved.metrics==f.metrics and saved.probability is None and saved.suggested_stake==0


@pytest.mark.asyncio
async def test_access_failure_is_not_retried_and_keeps_its_budget(database):
    f=await seed(database);calls=[]
    def handle(request):calls.append(1);return httpx.Response(403)
    transport=httpx.MockTransport(handle)
    assert (await check.verify_fixture(f.id,transport=transport))['status']=='unavailable'
    assert (await check.verify_fixture(f.id,transport=transport))['status']=='already_attempted'
    async with database() as s:
        assert (await s.get(RuntimeLimit,f'nhl-starter-wire:{now():%Y-%m}')).used==check.MAX_BYTES
    assert len(calls)==1


@pytest.mark.asyncio
async def test_completely_missing_source_games_still_enter_pilot_coverage_audit(database,monkeypatch):
    at=now()
    async with database.begin() as s:
        s.add(ProviderState(provider='nhl-goalie-pilot',observed_at=at-timedelta(hours=1),
            info={'expires_at':(at+timedelta(hours=71)).isoformat()}))
        for gid,offset in [('nhl:2026020001',timedelta(minutes=30)),('nhl:2026020002',timedelta(days=2))]:
            s.add(Fixture(id=gid,sport='NHL',home='Home',away='Away',commence_time=at-offset,final_home_win=True))
    calls=[]
    async def record(fixture_id):calls.append(fixture_id)
    monkeypatch.setattr(check,'verify_fixture',record)
    await check.cycle()
    assert calls==['nhl:2026020001']
