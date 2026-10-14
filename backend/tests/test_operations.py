from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
import httpx
import pytest
from sqlalchemy import select,func
from app.api import app
from app.clock import now
from app.config import settings
from app.limits import Limits
from app.models import Fixture,ProviderCall,ModelValidation
from app.model_config import GATE_NAMES,MODEL_VERSION,baseline_digest
from app.readiness import fresh_recommendation,validated_model
from app import providers,allowances
from app.http import SafeHTTP

HEADERS={'Authorization':'Bearer test-session-token-32-characters-long'}
FACTORS={'goalie_personnel':'.1','expected_goals':'.2','rest_fatigue':'-.1','venue_special_teams':'0'}

async def test_operations_are_private_and_reading_never_calls_a_provider(database,monkeypatch):
    async def forbidden(*args,**kwargs):raise AssertionError('Read endpoint called an external provider')
    monkeypatch.setattr('app.http.http.request',forbidden)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        assert (await client.get('/operations')).status_code==401
        assert (await client.post('/operations/allowances')).status_code==401
        status=await client.get('/operations',headers=HEADERS)
        assert status.status_code==200 and status.json()['active_sports']==['NHL']
        assert status.json()['ai_monthly_cap_usd']=='0'
        assert (await client.patch('/operations/pause',headers=HEADERS,json={'paused':'true'})).status_code==422
        assert (await client.patch('/operations/pause',headers=HEADERS,json={'paused':True})).json()['paid_paused']
        assert await Limits().blocked('odds')
        assert (await client.post('/operations/resume',headers=HEADERS,json={'provider':'invalid'})).status_code==422

async def test_evidence_requires_real_source_complete_factors_and_named_starters(database):
    async with database.begin() as session:
        session.add(Fixture(id='nhl:evidence',sport='NHL',home='Home',away='Away',commence_time=now()+timedelta(hours=2)))
    body={'source_at':now().isoformat(),'source_reference':'https://example.com/verified-lineup',
        'factors':FACTORS,'personnel_confirmed':True,'other_markets_verified':False,'opposing_case_verified':False}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers=HEADERS) as client:
        url='/fixtures/nhl:evidence/evidence'
        assert (await client.post(url,json=body)).status_code==422
        body.update(home_goalie='Home Starter',away_goalie='Away Starter')
        for source in ['http://example.com/lineup','https://user:secret@example.com/lineup','https://example.com/lineup?api_key=private']:
            assert (await client.post(url,json={**body,'source_reference':source})).status_code==422
        assert (await client.post(url,json={**body,'factors':{}})).status_code==422
        assert (await client.post(url,json={**body,'source_at':(now()-timedelta(minutes=31)).isoformat()})).status_code==422
        assert (await client.post(url,json=body)).status_code==200
        async with database.begin() as session:
            fixture=await session.get(Fixture,'nhl:evidence');fixture.commence_time=now()+timedelta(minutes=20)
        assert (await client.post(url,json={**body,'factors':{**FACTORS,'expected_goals':'.3'}})).status_code==409
        assert (await client.post(url,json=body)).status_code==200

def test_unrelated_update_cannot_make_old_recommendation_fresh():
    at=now()
    fixture=SimpleNamespace(sport='NHL',dirty=False,commence_time=at+timedelta(minutes=20),gates=dict.fromkeys(GATE_NAMES,True),
        updated_at=at,metrics={'recommendation_baseline_digest':baseline_digest('NHL'),'recommendation_verified_at':at.isoformat(),
            'recommended_quote_source_at':(at-timedelta(minutes=6)).isoformat(),'confirmed_at':at.isoformat()})
    assert not fresh_recommendation(fixture)
    fixture.metrics['recommended_quote_source_at']=at.isoformat()
    assert fresh_recommendation(fixture)
    fixture.metrics['recommendation_baseline_digest']='old-configuration'
    assert not fresh_recommendation(fixture)

def test_corrupt_or_incompatible_model_approval_is_rejected():
    at=now()
    model=SimpleNamespace(sport='NHL',approved=True,created_at=at-timedelta(days=1),parameters={'slope':1,'intercept':0},
        report={'baseline_version':MODEL_VERSION,'baseline_digest':baseline_digest('NHL'),'passing':True,
            'train_records':300,'calibration_records':100,'test_records':100,'test_brier':'.19','reference_brier':'.25',
            'test_through':(at-timedelta(days=10)).isoformat()})
    assert validated_model(model)
    model.report['baseline_digest']='another-model'
    assert not validated_model(model)
    model.report['baseline_digest']=baseline_digest('NHL');model.parameters['slope']=float('nan')
    assert not validated_model(model)

async def test_account_check_is_cached_and_never_uses_paid_endpoints(database,monkeypatch):
    monkeypatch.setattr(allowances,'settings',replace(settings,odds_key='test-only',router_key='test-only',esports_key='test-only'))
    calls=[]
    async def metadata(provider,method,url,**kwargs):
        calls.append(provider);assert method=='GET' and provider not in {'odds','openrouter','pandascore'}
        if provider=='odds_meta':await Limits().observe('odds',{'used':123,'remaining':19877,'last':0});return []
        if provider=='openrouter_meta':return {'data':{'limit':10,'limit_remaining':9,'limit_reset':'monthly','usage':1,'usage_monthly':1}}
        if provider=='openrouter_wallet':return {'data':{'total_credits':20,'total_usage':1}}
        assert url.endswith('/csgo/matches/upcoming') and kwargs['params']['page[size]']==1
        await Limits().observe('pandascore',{'hourly_limit':1000,'hourly_remaining':999});return []
    monkeypatch.setattr(allowances.http,'request',metadata)
    first=await allowances.provider_allowances();second=await allowances.provider_allowances()
    assert first==second and len(calls)==4
    assert first[0]['period_allowance']==20000 and first[1]['wallet_remaining_usd']=='19'
    assert first[2]['hourly_limit']==1000
    async with database() as session:assert await session.scalar(select(func.count()).select_from(ProviderCall))==0

async def test_nhl_history_cache_preserves_source_age_and_disables_esports(database,monkeypatch):
    calls=[]
    async def data(provider,method,url,**kwargs):calls.append(url);return {'games':[{'id':1}]}
    monkeypatch.setattr(providers.http,'request',data)
    assert await providers.nhl_history('TOR',20262027)==[{'id':1}]
    observation=await Limits().observation('nhl-history:TOR:20262027',max_age=14400)
    assert await providers.nhl_history('TOR',20262027)==[{'id':1}]
    assert (await Limits().observation('nhl-history:TOR:20262027',max_age=14400))['source_at']==observation['source_at']
    assert await providers.esports_matches('CS2')==[]
    assert len(calls)==1

async def test_pandascore_allowance_is_verified_from_used_and_remaining_headers(database):
    client=SafeHTTP(Limits(),httpx.MockTransport(lambda request:httpx.Response(200,json=[],
        headers={'X-Rate-Limit-Remaining':'999','X-Rate-Limit-Used':'1'})))
    await client.request('pandascore_meta','GET','https://example.test')
    quota=await Limits().observation('pandascore')
    assert quota=={'hourly_remaining':999,'hourly_used':1,'hourly_limit':1000}

async def test_ai_key_preflight_rejects_unlimited_key_without_generation(database,monkeypatch):
    config=replace(settings,router_key='test-only',llm_daily_usd=Decimal('.3'),llm_monthly_usd=Decimal('10'))
    monkeypatch.setattr(providers,'settings',config)
    calls=[]
    async def data(provider,*args,**kwargs):calls.append(provider);return {'data':{'limit':None,'limit_remaining':None,'limit_reset':None}}
    monkeypatch.setattr(providers.http,'request',data)
    fixture=SimpleNamespace(id='nhl:test',sport='NHL',home='Home',away='Away',commence_time=now()+timedelta(hours=2),metrics={})
    quote=SimpleNamespace(selection='Home',decimal_odds=2)
    with pytest.raises(providers.ProviderError):await providers.doublecheck(fixture,Decimal('.6'),quote,'test-cycle',{})
    assert calls==['openrouter_meta'] and await Limits().blocked('openrouter')

@pytest.mark.parametrize('finish_reason',['stop','length'])
async def test_ai_json_review_is_bounded_and_truncation_never_retries(database,monkeypatch,finish_reason):
    import json
    config=replace(settings,router_key='test-only',llm_daily_usd=Decimal('.3'),llm_monthly_usd=Decimal('10'))
    monkeypatch.setattr(providers,'settings',config)
    await Limits().observe('openrouter',{'limit':'10','remaining':'10','reset':'monthly'})
    sent=[]
    report={'opposing_case':'The opponent has a stronger recent trend.','risks':[],
        'opposing_case_verified':False,'other_markets_verified':False,'veto_verified':False,'veto_reason':'Missing evidence'}
    async def response(provider,method,url,**kwargs):
        sent.append(kwargs['json'])
        return {'choices':[{'finish_reason':finish_reason,'message':{'content':json.dumps(report)}}]}
    monkeypatch.setattr(providers.http,'request',response)
    fixture=SimpleNamespace(id='nhl:test',sport='NHL',home='Home',away='Away',commence_time=now()+timedelta(hours=2),metrics={})
    quote=SimpleNamespace(selection='Home',decimal_odds=2)
    if finish_reason=='stop':assert await providers.doublecheck(fixture,Decimal('.6'),quote,'test-cycle',{})==report
    else:
        with pytest.raises(providers.ProviderError):await providers.doublecheck(fixture,Decimal('.6'),quote,'test-cycle',{})
        assert await Limits().blocked('openrouter')
    assert len(sent)==1 and sent[0]['max_tokens']==600 and sent[0]['response_format']['type']=='json_object'
    assert not sent[0]['provider']['allow_fallbacks']
