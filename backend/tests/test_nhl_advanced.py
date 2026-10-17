from dataclasses import replace
from datetime import timedelta
import csv
import gzip
import io
import json
import zipfile
import httpx
import pytest
from sqlalchemy import select

from app import nhl_advanced as advanced
from app.clock import now
from app.config import settings
from app.models import ProviderState, RuntimeLimit, ProviderCall, Fixture, State

TEAMS = ['ANA','BOS','BUF','CAR','CBJ','CGY','CHI','COL','DAL','DET','EDM','FLA','LAK','MIN','MTL','NJD',
         'NSH','NYI','NYR','OTT','PHI','PIT','SEA','SJS','STL','TBL','TOR','UTA','VAN','VGK','WPG','WSH']


def source_files():
    day = now().date() - timedelta(days=1)
    team_rows, goalie_rows, games = [], [], []
    for i in range(16):
        gid = f'202602{i + 1:04}'
        home, away = TEAMS[i * 2:i * 2 + 2]
        for code, opponent, venue in ((home, away, 'HOME'), (away, home, 'AWAY')):
            for situation in ('all','5on5','5on4','4on5','other'):
                base = dict(gameId=gid,gameDate=day.strftime('%Y%m%d'),season='2026',playerTeam=code,
                    opposingTeam=opponent,home_or_away=venue,situation=situation)
                team_rows.append(dict(**base,xGoalsFor='1',xGoalsAgainst='1',goalsFor='1',goalsAgainst='1',
                    xGoalsPercentage='.5',iceTime='1800',playoffGame='0'))
                goalie_rows.append(dict(**base,playerId=str(8470000+TEAMS.index(code)),name=f'Test goalie {code}',
                    icetime='1800',xGoals='1',goals='1'))
        games.append(dict(id=int(gid),gameState='OFF',gameType=2,gameDate=day.isoformat(),
            gameOutcome={'lastPeriodType':'SO'},homeTeam={'abbrev':home,'score':2},awayTeam={'abbrev':away,'score':1}))
    def csv_body(rows):
        out = io.StringIO(newline=''); writer = csv.DictWriter(out,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows);return out.getvalue().encode()
    goalie_zip = io.BytesIO()
    with zipfile.ZipFile(goalie_zip,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('2026.csv',csv_body(goalie_rows))
    return csv_body(team_rows),goalie_zip.getvalue(),{'currentDate':day.isoformat(),'games':games}


class Body(httpx.AsyncByteStream):
    def __init__(self,data): self.data = data
    async def __aiter__(self):
        for start in range(0,len(self.data),73): yield self.data[start:start+73]


def transport_for(team,goalies,reference,calls):
    def respond(request):
        calls.append(str(request.url))
        headers = {'Last-Modified':(now()-timedelta(hours=8)).strftime('%a, %d %b %Y %H:%M:%S GMT')}
        if str(request.url)==advanced.TEAM_URL:
            data=gzip.compress(team);headers.update({'Content-Encoding':'gzip','Content-Length':str(len(data))})
        elif str(request.url)==advanced.GOALIE_URL:
            data=goalies;headers['Content-Length']=str(len(data))
        elif request.url.host=='api-web.nhle.com': data=json.dumps(reference).encode()
        else: raise AssertionError('Unexpected data-provider destination')
        return httpx.Response(200,headers=headers,stream=Body(data))
    return httpx.MockTransport(respond)


async def test_disabled_feature_never_calls_a_source(database,monkeypatch):
    monkeypatch.setattr(advanced,'settings',replace(settings,nhl_advanced_enabled=False))
    assert await advanced.sync(transport=httpx.MockTransport(lambda r:pytest.fail('Network attempted'))) == {'status':'disabled'}


async def test_one_daily_admission_and_monthly_byte_cap_survive_restarts(database,monkeypatch):
    monkeypatch.setattr(advanced,'settings',replace(settings,nhl_advanced_enabled=True))
    monthly,day=await advanced.reserve_batch()
    with pytest.raises(advanced.BudgetExceeded): await advanced.reserve_batch()
    async with database() as session:
        assert (await session.get(RuntimeLimit,f'moneypuck-batch:{day}')).used==1
        assert (await session.get(RuntimeLimit,monthly)).used==advanced.RESERVATION


async def test_monthly_cap_failure_does_not_consume_daily_slot(database,monkeypatch):
    monkeypatch.setattr(advanced,'settings',replace(settings,nhl_advanced_enabled=True,nhl_advanced_monthly_bytes=advanced.RESERVATION-1))
    with pytest.raises(advanced.BudgetExceeded): await advanced.reserve_batch()
    async with database() as session:
        assert await session.get(RuntimeLimit,f'moneypuck-batch:{now().date()}') is None


async def test_failed_request_keeps_previous_cache_and_never_retries(database,monkeypatch):
    monkeypatch.setattr(advanced,'settings',replace(settings,nhl_advanced_enabled=True))
    previous={'version':'previous valid data'}
    async with database.begin() as session:
        session.add(ProviderState(provider=advanced.CACHE_KEY,info=previous))
    calls=[]
    def failed(request): calls.append(request);return httpx.Response(503)
    result=await advanced.sync(transport=httpx.MockTransport(failed))
    assert result['status']=='failed' and len(calls)==1
    with pytest.raises(advanced.BudgetExceeded):await advanced.sync(transport=httpx.MockTransport(failed))
    async with database() as session:
        assert (await session.get(ProviderState,advanced.CACHE_KEY)).info==previous
        failure=(await session.get(ProviderState,advanced.STATUS_KEY)).info
        assert failure['stage']=='team_download'
        assert failure['reason']=='NHL file request failed; no retry'
        assert (await session.get(RuntimeLimit,f'moneypuck-wire:{now():%Y-%m}')).used==advanced.RESERVATION
        assert (await session.scalars(select(ProviderCall))).all()==[]


async def test_valid_batch_imports_atomically_without_approving_picks(database,monkeypatch):
    monkeypatch.setattr(advanced,'settings',replace(settings,nhl_advanced_enabled=True))
    team,goalies,reference=source_files();calls=[]
    result=await advanced.sync(transport=transport_for(team,goalies,reference,calls))
    assert result['status']=='succeeded' and len(calls)==3 and result['paid_credits']==0
    async with database() as session:
        row=await session.get(ProviderState,advanced.CACHE_KEY)
        assert row.info['team_games']==16 and len(row.info['teams'])==32
        assert row.info['model_approved_by_import'] is False
        assert row.info['starters_confirmed_by_import'] is False
        assert all(g['starter_confirmed'] is False for g in row.info['goalies'].values())
        assert all(g['status']=='insufficient_sample' and 'gsax' not in g for g in row.info['goalies'].values())
        assert (await session.get(RuntimeLimit,f'moneypuck-wire:{now():%Y-%m}')).used==result['wire_accounted']
        assert (await session.scalars(select(ProviderCall))).all()==[]


async def test_changed_coverage_retains_cache_and_reservation(database,monkeypatch):
    monkeypatch.setattr(advanced,'settings',replace(settings,nhl_advanced_enabled=True))
    team,goalies,reference=source_files();reference['games'][0]['homeTeam']['score']=9
    calls=[]
    result=await advanced.sync(transport=transport_for(team,goalies,reference,calls))
    assert result['status']=='failed'
    async with database() as session:
        assert await session.get(ProviderState,advanced.CACHE_KEY) is None
        assert (await session.get(ProviderState,advanced.STATUS_KEY)).info['stage']=='source_validation'
        assert (await session.get(RuntimeLimit,f'moneypuck-wire:{now():%Y-%m}')).used==advanced.RESERVATION


def test_import_diagnostics_never_publish_untrusted_exception_text():
    error=ValueError('upstream body https://example.com/?token=secret-do-not-publish')
    failure=advanced.import_failure(error,'team_download')
    assert failure['category']=='ValueError' and failure['stage']=='team_download'
    assert 'secret-do-not-publish' not in str(failure)
    assert failure['retained_previous_cache'] is True


async def test_bounded_probe_cannot_replace_cache_or_reset_imports(database,monkeypatch):
    monkeypatch.setattr(advanced,'settings',replace(settings,nhl_advanced_enabled=True))
    previous={'version':'prior valid cache'}
    async with database.begin() as session:
        session.add(ProviderState(provider=advanced.CACHE_KEY,info=previous))
    await advanced.reserve_batch()
    team,goalies,reference=source_files();calls=[]
    result=await advanced.probe_sources(transport=transport_for(team,goalies,reference,calls))
    assert result['status']=='complete' and result['paid_credits']==0
    assert calls==[advanced.TEAM_URL,advanced.GOALIE_URL]
    assert all(0<row['sample_bytes']<=advanced.PROBE_SAMPLE for row in result['sources'])
    with pytest.raises(advanced.BudgetExceeded):
        await advanced.probe_sources(transport=transport_for(team,goalies,reference,calls))
    assert len(calls)==2
    async with database() as session:
        assert (await session.get(ProviderState,advanced.CACHE_KEY)).info==previous
        assert (await session.get(RuntimeLimit,f'moneypuck-batch:{now().date()}')).used==1
        assert (await session.get(RuntimeLimit,f'moneypuck-probe:{now().date()}')).used==1
        assert (await session.get(RuntimeLimit,f'moneypuck-wire:{now():%Y-%m}')).used==advanced.RESERVATION+advanced.PROBE_RESERVATION
        assert (await session.scalars(select(ProviderCall))).all()==[]


async def test_probe_reports_http_failures_without_retry_or_body_exposure(database,monkeypatch):
    monkeypatch.setattr(advanced,'settings',replace(settings,nhl_advanced_enabled=True))
    calls=[]
    def failed(request):
        calls.append(str(request.url))
        return httpx.Response(403,text='untrusted body secret-token')
    result=await advanced.probe_sources(transport=httpx.MockTransport(failed))
    assert result['status']=='failed' and len(calls)==2
    assert all(row['http_status']==403 and row['reason']=='NHL file request failed; no retry' for row in result['sources'])
    assert 'secret-token' not in str(result)
    async with database() as session:
        assert await session.get(ProviderState,advanced.CACHE_KEY) is None


async def test_probe_monthly_admission_failure_consumes_no_daily_probe_slot(database,monkeypatch):
    monkeypatch.setattr(advanced,'settings',replace(settings,nhl_advanced_enabled=True,nhl_advanced_monthly_bytes=advanced.PROBE_RESERVATION-1))
    with pytest.raises(advanced.BudgetExceeded):await advanced.reserve_probe()
    async with database() as session:
        assert await session.get(RuntimeLimit,f'moneypuck-probe:{now().date()}') is None


async def test_probe_closes_each_source_after_a_single_small_chunk(database,monkeypatch):
    monkeypatch.setattr(advanced,'settings',replace(settings,nhl_advanced_enabled=True))
    yielded={advanced.TEAM_URL:0,advanced.GOALIE_URL:0}
    class LargeSource(httpx.AsyncByteStream):
        def __init__(self,url):self.url=url
        async def __aiter__(self):
            prefix=gzip.compress(b'x'*200000) if self.url==advanced.TEAM_URL else b'PK\x03\x04'
            for _ in range(100):
                yielded[self.url]+=1
                yield (prefix+b'0'*advanced.PROBE_SAMPLE)[:advanced.PROBE_SAMPLE]
    def respond(request):
        url=str(request.url)
        headers={'Last-Modified':(now()-timedelta(hours=1)).strftime('%a, %d %b %Y %H:%M:%S GMT'),
                 'Content-Length':str(100*advanced.PROBE_SAMPLE)}
        if url==advanced.TEAM_URL:headers['Content-Encoding']='gzip'
        return httpx.Response(200,headers=headers,stream=LargeSource(url))
    result=await advanced.probe_sources(transport=httpx.MockTransport(respond))
    assert result['status']=='complete'
    assert list(yielded.values())==[1,1]
    assert all(r['sample_bytes']==advanced.PROBE_SAMPLE for r in result['sources'])


async def test_probe_route_is_private_and_cannot_readmit_same_day(database,monkeypatch):
    import main
    config=replace(settings,nhl_advanced_enabled=True)
    monkeypatch.setattr(main,'settings',config);monkeypatch.setattr(advanced,'settings',config)
    admissions=[]
    async def fake_probe(**kwargs):admissions.append(kwargs['admission'])
    monkeypatch.setattr(advanced,'probe_sources',fake_probe)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://test') as client:
        assert (await client.post('/operations/nhl-statistics-probe')).status_code==401
        assert admissions==[]
        headers={'Authorization':'Bearer '+config.admin_token}
        first=await client.post('/operations/nhl-statistics-probe',headers=headers)
        assert first.status_code==202 and first.json()['paid_credits']==0
        assert len(admissions)==1
        assert (await client.post('/operations/nhl-statistics-probe',headers=headers)).status_code==429
        assert len(admissions)==1


async def test_detail_read_is_cache_only_truthfully_stale_and_does_not_modify_fixture(database,monkeypatch):
    monkeypatch.setattr(advanced,'settings',replace(settings,nhl_advanced_enabled=True))
    batch={'schema_version':1,'model_approved_by_import':False,'as_of_date':(now().date()-timedelta(days=1)).isoformat(),
        'verified_through':(now().date()-timedelta(days=2)).isoformat(),'teams':{'TOR':{'status':'available','sample_games':3}},
        'goalies':{'8470000':{'latest_team':'TOR','starter_confirmed':False}}}
    async with database.begin() as session:
        fixture=Fixture(id='qa:stats',sport='NHL',home='Edmonton Oilers',away='Toronto Maple Leafs',
            commence_time=now()+timedelta(hours=2),metrics={'home_abbrev':'EDM','away_abbrev':'TOR'},state=State.HOLD)
        session.add(fixture);session.add(ProviderState(provider=advanced.CACHE_KEY,info=batch,observed_at=now()-timedelta(hours=30)))
    async with database() as session:
        fixture=await session.get(Fixture,'qa:stats')
        result=await advanced.detail(session,fixture)
        assert result['status']=='stale' and result['sides']['away']['metrics']['sample_games']==3
        assert result['sides']['home']['metrics'] is None
        assert fixture.state==State.HOLD and fixture.metrics=={'home_abbrev':'EDM','away_abbrev':'TOR'}
        assert (await session.scalars(select(ProviderCall))).all()==[]


async def test_source_url_redirect_and_compression_budgets_are_enforced(monkeypatch,tmp_path):
    calls=[]
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:calls.append(r))) as client:
        with pytest.raises(ValueError):await advanced.download(client,'https://attacker.test/data',tmp_path/'x',compressed=True)
    assert calls==[]
    monkeypatch.setattr(advanced,'MAX_TEAM_DECODED',5)
    headers={'Content-Encoding':'gzip','Last-Modified':(now()-timedelta(hours=1)).strftime('%a, %d %b %Y %H:%M:%S GMT')}
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,headers=headers,stream=Body(gzip.compress(b'a'*1000))))) as client:
        with pytest.raises(ValueError):await advanced.download(client,advanced.TEAM_URL,tmp_path/'x',compressed=True)


async def test_refresh_route_authentication_and_daily_repeat_guard(database,monkeypatch):
    import main
    config=replace(settings,nhl_advanced_enabled=True)
    monkeypatch.setattr(main,'settings',config);monkeypatch.setattr(advanced,'settings',config)
    admissions=[]
    async def fake_sync(**kwargs):admissions.append(kwargs['admission']);return {'status':'succeeded'}
    monkeypatch.setattr(advanced,'sync',fake_sync)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://test') as client:
        response=await client.post('/operations/nhl-statistics-refresh')
        assert response.status_code==401 and admissions==[]
        headers={'Authorization':'Bearer '+config.admin_token}
        response=await client.post('/operations/nhl-statistics-refresh',headers=headers)
        assert response.status_code==202 and response.json()['paid_credits']==0 and len(admissions)==1
        assert (await client.post('/operations/nhl-statistics-refresh',headers=headers)).status_code==429
        assert len(admissions)==1


async def test_pre_anchor_statistics_cannot_be_backdated_or_replaced_in_saved_context(database,monkeypatch):
    monkeypatch.setattr(advanced,'settings',replace(settings,nhl_advanced_enabled=True))
    anchor=now()
    before=anchor-timedelta(seconds=1)
    batch={'schema_version':1,'as_of_date':anchor.date().isoformat(),'verified_through':(anchor.date()-timedelta(days=1)).isoformat(),
        'model_approved_by_import':False,'sources':{'team':{'observed_at':before.isoformat()},'goalie':{'observed_at':before.isoformat()}},
        'teams':{'TOR':{'xg_share':'.4'},'EDM':{'xg_share':'.6'}},'goalies':{}}
    async with database.begin() as session:
        session.add(ProviderState(provider=advanced.CACHE_KEY,info=batch,observed_at=before))
        session.add(Fixture(id='qa:anchor-stats',sport='NHL',home='EDM',away='TOR',commence_time=anchor+timedelta(minutes=30),
            metrics={'home_abbrev':'EDM','away_abbrev':'TOR'}))
    async with database() as session:
        fixture=await session.get(Fixture,'qa:anchor-stats')
        saved=await advanced.frozen_context(session,fixture,anchor)
        assert saved['classification']=='observed_pre_anchor_descriptive_statistics'
        assert saved['model_approved_by_import'] is False and saved['teams']['away']['xg_share']=='.4'
    async with database.begin() as session:
        cache=await session.get(ProviderState,advanced.CACHE_KEY)
        cache.observed_at=anchor+timedelta(seconds=1)
        cache.info={**batch,'teams':{'TOR':{'xg_share':'.9'},'EDM':{'xg_share':'.1'}}}
    async with database() as session:
        fixture=await session.get(Fixture,'qa:anchor-stats')
        assert await advanced.frozen_context(session,fixture,anchor) is None
        assert saved['teams']['away']['xg_share']=='.4'


async def test_daily_cards_share_saved_stats_without_network_admissions_or_probabilities(database,monkeypatch):
    import main
    at = now()
    monkeypatch.setattr(advanced, 'settings', replace(settings, nhl_advanced_enabled=True))
    batch = {'schema_version':1, 'model_approved_by_import':False, 'as_of_date':at.date().isoformat(),
             'verified_through':(at.date()-timedelta(days=1)).isoformat(), 'teams':{
                 'TOR':{'status':'available','sample_games':6,'latest_game_date':(at.date()-timedelta(days=1)).isoformat(),'xg_share':'.549'},
                 'EDM':{'status':'available','sample_games':6,'latest_game_date':(at.date()-timedelta(days=1)).isoformat(),'xg_share':'.506'}}}
    async with database.begin() as session:
        session.add(ProviderState(provider=advanced.CACHE_KEY,info=batch,observed_at=at-timedelta(hours=1)))
        for index in range(2):
            session.add(Fixture(id=f'qa:daily-stats-{index}',sport='NHL',home='Edmonton Oilers',away='Toronto Maple Leafs',
                commence_time=at+timedelta(hours=2+index),metrics={'home_abbrev':'EDM','away_abbrev':'TOR'}))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://test') as client:
        assert (await client.get('/dashboard')).status_code==401
        response=await client.get('/dashboard',headers={'Authorization':'Bearer '+settings.admin_token})
        assert response.status_code==200
        data=response.json()
        for fixture in data['fixtures']:
            assert fixture['probability'] is None and fixture['edge'] is None
            comparison=data['nhl_team_statistics'][fixture['id']]
            assert comparison['status']=='available'
            assert comparison['sides']['away']['metrics']['xg_share']=='.549'
            assert comparison['sides']['home']['metrics']['xg_share']=='.506'
    async with database() as session:
        assert (await session.scalars(select(ProviderCall))).all()==[]
        assert (await session.scalars(select(RuntimeLimit))).all()==[]


@pytest.mark.parametrize('latest,observed_hours,start_hours,expected',[
    ('previous',-1,2,'available'), ('same_day',-1,2,'not_pre_game'),
    (None,-1,2,'not_pre_game'), ('bad-date',-1,2,'not_pre_game'),
    ('2026-02-30',-1,2,'not_pre_game'), ('previous',-1,-2,'not_pre_game'),
    ('previous',-1,-.75,'not_pre_game')])
async def test_daily_card_stats_require_known_dates_and_a_genuine_pre_anchor_cache(database,monkeypatch,latest,observed_hours,start_hours,expected):
    at=now();monkeypatch.setattr(advanced,'now',lambda:at)
    monkeypatch.setattr(advanced,'settings',replace(settings,nhl_advanced_enabled=True))
    game_date=(at.date()-timedelta(days=1)).isoformat() if latest=='previous' else at.date().isoformat() if latest=='same_day' else latest
    batch={'schema_version':1,'model_approved_by_import':False,'as_of_date':at.date().isoformat(),'teams':{
        'EDM':{'status':'available','sample_games':6,'latest_game_date':game_date,'xg_share':'.6'}}}
    async with database.begin() as session:
        session.add(ProviderState(provider=advanced.CACHE_KEY,info=batch,observed_at=at+timedelta(hours=observed_hours)))
        session.add(Fixture(id='qa:time-stats',sport='NHL',home='Edmonton Oilers',away='Toronto Maple Leafs',
            commence_time=at+timedelta(hours=start_hours),metrics={'home_abbrev':'EDM','away_abbrev':'TOR'}))
    async with database() as session:
        fixture=await session.get(Fixture,'qa:time-stats')
        result=await advanced.matchup_teams(session,[fixture])
        assert result[fixture.id]['sides']['home']['metrics']['status']==expected
        assert result[fixture.id]['sides']['away']['metrics'] is None
        assert fixture.probability is None and fixture.metrics=={'home_abbrev':'EDM','away_abbrev':'TOR'}


async def test_old_card_stats_are_labeled_stale_and_future_cache_is_unavailable(database,monkeypatch):
    at=now();monkeypatch.setattr(advanced,'now',lambda:at)
    monkeypatch.setattr(advanced,'settings',replace(settings,nhl_advanced_enabled=True))
    batch={'schema_version':1,'model_approved_by_import':False,'as_of_date':at.date().isoformat(),'teams':{
        'EDM':{'status':'available','sample_games':6,'latest_game_date':(at.date()-timedelta(days=1)).isoformat(),'xg_share':'.6'}}}
    async with database.begin() as session:
        session.add(ProviderState(provider=advanced.CACHE_KEY,info=batch,observed_at=at-timedelta(hours=30)))
        session.add(Fixture(id='qa:stale-stats',sport='NHL',home='Edmonton Oilers',away='Toronto Maple Leafs',
            commence_time=at+timedelta(hours=2),metrics={'home_abbrev':'EDM','away_abbrev':'TOR'}))
    async with database() as session:
        fixture=await session.get(Fixture,'qa:stale-stats')
        result=(await advanced.matchup_teams(session,[fixture]))[fixture.id]
        assert result['status']=='stale' and result['sides']['home']['metrics']['xg_share']=='.6'
    async with database.begin() as session:
        cache=await session.get(ProviderState,advanced.CACHE_KEY)
        cache.observed_at=at+timedelta(minutes=1)
    async with database() as session:
        fixture=await session.get(Fixture,'qa:stale-stats')
        assert (await advanced.matchup_teams(session,[fixture]))[fixture.id]['status']=='unavailable'
        assert (await session.scalars(select(ProviderCall))).all()==[]
