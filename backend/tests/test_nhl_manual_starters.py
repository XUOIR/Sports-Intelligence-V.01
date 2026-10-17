from datetime import timedelta
from uuid import uuid4
from copy import deepcopy
import httpx
import pytest
from sqlalchemy import select, func
from app.api import app
from app.clock import now, aware
from app.models import Fixture, Evidence, AuditLog, ProviderCall, Snapshot, JobLease
from app.nhl_starters import preview, MANUAL_CONTRACT

HEADERS={'Authorization':'Bearer test-session-token-32-characters-long'}

async def seed(database, at):
    f=Fixture(id='nhl:2026029999',sport='NHL',home='Home',away='Away',commence_time=at+timedelta(hours=1),
        metrics={'home_abbrev':'TOR','away_abbrev':'EDM','other_markets_verified':True,'opposing_case_verified':True,
            'confirmed_at':(at-timedelta(hours=1)).isoformat(),
            'nhl_goalie_comparison':{'observed_at':at.isoformat(),'sides':{
                'home':[{'player_id':'8480001','name':'Home Starter','season_appearances':5}],
                'away':[{'player_id':'8480002','name':'Away Starter','season_appearances':4}]}}},gates={})
    async with database.begin() as session:session.add(f)
    version=preview(f,None,at)['selection']['version']
    return f,{'request_id':str(uuid4()),'candidate_version':version,'home_player_id':'8480001','away_player_id':'8480002'}

async def test_one_manual_confirmation_saves_ids_time_and_provenance_without_provider_calls(database,monkeypatch):
    at=now();f,body=await seed(database,at)
    monkeypatch.setattr('main.now',lambda:at)
    async def forbidden(*args,**kwargs):raise AssertionError('Manual confirmation must not contact providers')
    monkeypatch.setattr('app.providers.http.request',forbidden)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        assert (await client.post(f'/fixtures/{f.id}/starting-goalies',json=body)).status_code==401
        response=await client.post(f'/fixtures/{f.id}/starting-goalies',json=body,headers=HEADERS)
        assert response.status_code==200,response.text
        metrics=response.json()['metrics']
        assert metrics['goalie_confirmations']=={'home':'Home Starter','away':'Away Starter'}
        assert metrics['starter_confirmation_method']=='manual_operator' and metrics['starter_source_url'] is None
        assert aware(metrics['confirmed_at'])==at and aware(metrics['review_confirmed_at'])==at-timedelta(hours=1)
        assert response.json()['dirty'] and not response.json()['gates'] and response.json()['probability'] is None
        again=await client.post(f'/fixtures/{f.id}/starting-goalies',json=body,headers=HEADERS)
        assert again.status_code==200
    async with database() as session:
        evidence=await session.scalar(select(Evidence).where(Evidence.kind=='nhl_starters'))
        assert evidence.payload['contract']==MANUAL_CONTRACT and evidence.payload['source_url'] is None
        assert evidence.payload['player_ids']=={'home':'8480001','away':'8480002'}
        assert aware(evidence.source_at)==aware(evidence.observed_at)==at
        assert await session.scalar(select(func.count()).select_from(Evidence))==1
        assert await session.scalar(select(func.count()).select_from(AuditLog))==1
        assert await session.scalar(select(func.count()).select_from(ProviderCall))==0
        saved=await session.get(Fixture,f.id)
        row=preview(saved,None,at)['sides']['home']
        assert row['confirmation_method']=='manual_operator' and row['confirmed_player_id']=='8480001'
        assert row['source_url'] is None

@pytest.mark.parametrize('change,status', [('swapped',422),('same',422),('stale',409),('rescheduled',409),('started',409),('backdated',422)])
async def test_manual_confirmation_rejects_wrong_team_stale_or_post_start_inputs(database,monkeypatch,change,status):
    at=now();f,body=await seed(database,at)
    monkeypatch.setattr('main.now',lambda:at)
    if change=='swapped':body.update(home_player_id='8480002',away_player_id='8480001')
    if change=='same':body['home_player_id']=body['away_player_id']
    if change=='backdated':body['source_at']=(at-timedelta(hours=1)).isoformat()
    if change in {'stale','rescheduled','started'}:
        async with database.begin() as session:
            saved=await session.get(Fixture,f.id)
            if change=='stale':
                info=deepcopy(saved.metrics);info['nhl_goalie_comparison']['observed_at']=(at-timedelta(hours=3)).isoformat();saved.metrics=info
            else:saved.commence_time=at+timedelta(hours=2) if change=='rescheduled' else at
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers=HEADERS) as client:
        response=await client.post(f'/fixtures/{f.id}/starting-goalies',json=body)
        assert response.status_code==status,response.text
    async with database() as session:
        assert await session.scalar(select(func.count()).select_from(Evidence))==0
        assert await session.scalar(select(func.count()).select_from(ProviderCall))==0

async def test_missing_official_confirmation_does_not_erase_manual_attestation(database,monkeypatch):
    from app.ingestion import ingest_nhl_personnel
    at=now();f,body=await seed(database,at)
    monkeypatch.setattr('main.now',lambda:at)
    monkeypatch.setattr('app.ingestion.now',lambda:at)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers=HEADERS) as client:
        assert (await client.post(f'/fixtures/{f.id}/starting-goalies',json=body)).status_code==200
    async def no_confirmation(*args):return {}
    monkeypatch.setattr('app.providers.nhl_game',no_confirmation)
    await ingest_nhl_personnel()
    async with database() as session:
        saved=await session.get(Fixture,f.id)
        assert saved.metrics['personnel_confirmed'] is True
        assert saved.metrics['goalie_confirmations']['home']=='Home Starter'
        assert preview(saved,None,at+timedelta(minutes=31))['sides']['home']['status']=='unknown'


def test_fresh_saved_history_populates_selections_without_claiming_season_or_roster_facts():
    at=now()
    f=Fixture(id='nhl:history',sport='NHL',home='Home',away='Away',commence_time=at+timedelta(hours=20),
        metrics={'home_abbrev':'TOR','away_abbrev':'EDM'})
    stats={'status':'available','observed_at':at.isoformat(),'sides':{
        'home':{'goalies':[{'player_id':'8480001','name':'Home Starter','latest_team':'TOR'}]},
        'away':{'goalies':[{'player_id':'8480002','name':'Away Starter','latest_team':'EDM'}]}}}
    result=preview(f,stats,at)
    assert result['selection']['sides']['home'][0]['candidate_source']=='saved_team_history'
    assert result['sides']['home']['status']=='unknown'
    assert result['sides']['home']['candidates']==[]
    assert preview(f,stats,at+timedelta(hours=27))['selection']['sides']['home']==[]


async def test_fresh_starter_time_cannot_refresh_an_expired_review_or_call_ai(database,monkeypatch):
    from test_engine import seed_recommendation
    from app.engine import evaluate
    await seed_recommendation(database)
    async with database.begin() as session:
        f=await session.get(Fixture,'nhl:recommend')
        f.metrics={**f.metrics,'review_confirmed_at':(now()-timedelta(hours=1)).isoformat()}
    async def forbidden(*args,**kwargs):raise AssertionError('Expired reviews must block paid AI')
    monkeypatch.setattr('app.engine.doublecheck',forbidden)
    await evaluate('nhl:recommend')
    async with database() as session:
        f=await session.get(Fixture,'nhl:recommend')
        assert f.gates['personnel'] is True
        assert f.gates['other_markets'] is False and f.gates['opposing_case'] is False
        assert f.suggested_stake==0 and await session.scalar(select(func.count()).select_from(ProviderCall))==0

async def test_manual_selection_keeps_an_existing_frozen_snapshot_unchanged(database,monkeypatch):
    at=now();f,body=await seed(database,at)
    monkeypatch.setattr('main.now',lambda:at)
    async with database.begin() as session:
        current=await session.get(Fixture,f.id)
        current.commence_time=at+timedelta(minutes=20)
        body['candidate_version']=preview(current,None,at)['selection']['version']
        session.add(Snapshot(fixture_id=f.id,anchor_at=at-timedelta(minutes=10),game_date=at.date(),
            collected_at=at-timedelta(minutes=10),vector=[0]*15,evidence_ids=[],model_version='frozen-test',
            context={'research_factors':{'starter_evidence':{'payload':{'home':'Prior Home','away':'Prior Away'}}}}))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers=HEADERS) as client:
        assert (await client.post(f'/fixtures/{f.id}/starting-goalies',json=body)).status_code==200
    async with database() as session:
        frozen=await session.get(Snapshot,f.id)
        assert frozen.context['research_factors']['starter_evidence']['payload']['home']=='Prior Home'
        assert aware(frozen.anchor_at)==at-timedelta(minutes=10)
