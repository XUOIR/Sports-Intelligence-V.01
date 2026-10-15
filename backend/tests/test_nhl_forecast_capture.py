from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
import httpx
import pytest
from sqlalchemy import select
from app.clock import now
from app.models import Fixture, Evidence, ProviderState, Snapshot
from app.nhl_factors import normalized_factors
from app.nhl_starters import comparison, preview
from app.model_config import baseline_digest
from app.engine import freeze
from app.nhl_advanced import CACHE_KEY
from app.nhl_history import HISTORY_CONTRACT
from test_nhl_factors import inputs
from app.models import ModelValidation, JobLease, ProviderCall
from sqlalchemy import delete, func


def fixture(at):
    return Fixture(id='nhl:2026029999',sport='NHL',home='Home',away='Away',commence_time=at+timedelta(minutes=30),
        metrics={'home_abbrev':'TOR','away_abbrev':'EDM','nhl_season':20262027},gates={})


def landing():
    return {'id':2026029999,**{side+'Team':{'abbrev':code} for side,code in [('home','TOR'),('away','EDM')]},
        'matchup':{'goalieComparison':{side+'Team':{'leaders':[
            {'playerId':8480001,'gamesPlayed':8,'firstName':{'default':'Lead'},'lastName':{'default':'Goalie'}},
            {'playerId':8480002,'gamesPlayed':2,'firstName':{'default':'Other'},'lastName':{'default':'Goalie'}}]}
            for side in ('home','away')}}}


def test_projection_is_bounded_unconfirmed_and_cannot_invent_a_start_percentage():
    at=now();f=fixture(at)
    f.metrics['nhl_goalie_comparison']=comparison(landing(),f,at)
    stats={'status':'available','sides':{side:{'goalies':[
        {'player_id':'8480001','sample_games':8,'latest_game_date':str((at-timedelta(days=3)).date())},
        {'player_id':'8480002','sample_games':2,'latest_game_date':str((at-timedelta(days=6)).date())}]}
        for side in ('home','away')}}
    result=preview(f,stats,at)
    assert result['sides']['home']['status']=='projected'
    assert result['sides']['home']['projected_name']=='Lead Goalie'
    assert result['grants_verification'] is False and result['paid_credits']==0
    assert f.gates=={} and 'personnel_confirmed' not in f.metrics
    assert 'probability' not in str(result)
    stats['sides']['home']['goalies'][0]['latest_game_date']=str((at-timedelta(days=1)).date())
    assert preview(f,stats,at)['sides']['home']['projected_name']=='Other Goalie'
    assert preview(f,stats,at+timedelta(hours=3))['sides']['home']['status']=='unknown'
    assert comparison({**landing(),'id':2026021111},f,at) is None
    f.metrics.update(personnel_confirmed=True,confirmed_at=at.isoformat(),goalie_confirmations={'home':'Confirmed Home','away':'Confirmed Away'})
    assert preview(f,stats,at)['sides']['home']['confirmed_name']=='Confirmed Home'


async def test_future_capture_derives_baseline_only_from_preanchor_confirmed_facts(database,monkeypatch):
    context,starters,form,anchor=inputs()
    f=fixture(anchor)
    history=[{'contract':HISTORY_CONTRACT,'game_id':str(2026021000+i),'game_type':2,'season':20262027,
        'started_at':(f.commence_time-timedelta(days=i+2)).isoformat(),
        'completion_observed_at':(anchor-timedelta(minutes=1)).isoformat(),'win':True} for i in range(6)]
    for index,g in enumerate(context['goalie_candidates']):g['player_id']=str(8480001+index)
    batch={'schema_version':1,'model_approved_by_import':False,'as_of_date':str(anchor.date()),'verified_through':str(anchor.date()-timedelta(days=1)),
        'sources':context['sources'],'teams':{r['team']:r for r in context['teams'].values()},
        'team_context':{context['teams'][side]['team']:context['team_context'][side] for side in ('home','away')},
        'goalies':{r['player_id']:r for r in context['goalie_candidates']}}
    async with database.begin() as session:
        session.add(f);await session.flush()
        session.add(ProviderState(provider=CACHE_KEY,observed_at=anchor-timedelta(minutes=2),info=batch))
        for kind,payload in [('schedule',{'start':f.commence_time.isoformat()}),
            ('standings',{'home':{'games':6,'points_pct':'.5'},'away':{'games':6,'points_pct':'.5'}}),
            ('history',{'contract':HISTORY_CONTRACT,'home':history,'away':history}),('nhl_starters',starters['payload'])]:
            session.add(Evidence(fixture_id=f.id,kind=kind,payload=payload,source_at=anchor-timedelta(minutes=2),observed_at=anchor-timedelta(minutes=1)))
    monkeypatch.setattr('app.engine.now',lambda:anchor+timedelta(seconds=1))
    from dataclasses import replace
    from app.config import settings
    monkeypatch.setattr('app.nhl_advanced.settings',replace(settings,nhl_advanced_enabled=True))
    await freeze(f.id)
    async with database() as session:
        snapshot=await session.get(Snapshot,f.id)
        assert snapshot.baseline_home_probability==Decimal('.5')
        assert snapshot.prediction_home_probability is None
        assert snapshot.context['factor_source']['mode']=='derived'
        assert snapshot.context['baseline_digest']==baseline_digest('NHL')
        assert snapshot.context['research_factors']['approved_for_prediction'] is False
        assert (await session.get(Fixture,f.id)).probability is None
        from app.calibrate import validate
        record={'fixture_id':f.id,'sport':'NHL','model_version':snapshot.model_version,'vector':snapshot.vector,
            'probability':str(snapshot.baseline_home_probability),'outcome':1,'commence_time':f.commence_time.isoformat(),
            'anchor_at':snapshot.anchor_at.isoformat(),'collected_at':snapshot.collected_at.isoformat(),
            **{key:snapshot.context[key] for key in ('sources','factors','factor_source','baseline_digest','nhl_statistics')},
            'starter_evidence':snapshot.context['research_factors']['starter_evidence'],
            'result_source':{'game_id':f.id,'home_score':3,'away_score':2,'observed_at':f.commence_time.isoformat()}}
        monkeypatch.setattr('app.calibrate.now',lambda:f.commence_time+timedelta(hours=3))
        validate([record])
        altered=deepcopy(record);altered['nhl_statistics']['teams']['home']['xg_share']='.8'
        with pytest.raises(ValueError,match='normalization'):validate([altered])


async def test_original_publication_is_kept_separate_from_fresh_recheck(database,monkeypatch):
    from app.api import app
    at=now();f=fixture(at)
    async with database.begin() as session:session.add(f)
    monkeypatch.setattr('main.now',lambda:at)
    body={'source_at':at.isoformat(),'starter_reported_at':(at-timedelta(hours=6)).isoformat(),
        'source_reference':'https://www.nhl.com/news/confirmed-starters','personnel_confirmed':True,
        'home_goalie':'Confirmed Home','away_goalie':'Confirmed Away','other_markets_verified':False,'opposing_case_verified':False}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'Authorization':'Bearer test-session-token-32-characters-long'}) as client:
        response=await client.post(f'/fixtures/{f.id}/evidence',json=body)
        assert response.status_code==200,response.text
        assert response.json()['metrics']['starter_reported_at']==body['starter_reported_at']
        body['starter_reported_at']=(at+timedelta(minutes=1)).isoformat()
        assert (await client.post(f'/fixtures/{f.id}/evidence',json=body)).status_code==422


@pytest.mark.parametrize('change',['starter','calibration'])
async def test_changed_pairing_or_calibration_cannot_rewrite_a_saved_forecast(database,monkeypatch,change):
    from test_engine import seed_recommendation
    from app.engine import evaluate
    await seed_recommendation(database)
    calls=[]
    async def review(*args):
        calls.append(1)
        return {'opposing_case_verified':True,'other_markets_verified':True,'veto_verified':True}
    monkeypatch.setattr('app.engine.doublecheck',review)
    await evaluate('nhl:recommend')
    async with database.begin() as session:
        original=(await session.get(Snapshot,'nhl:recommend')).prediction_home_probability
        await session.execute(delete(JobLease))
        if change=='starter':
            f=await session.get(Fixture,'nhl:recommend')
            f.metrics={**f.metrics,'goalie_confirmations':{'home':'Different Starter','away':'Away Starter'}}
        else:
            m=await session.get(ModelValidation,'approved')
            m.parameters={'slope':2,'intercept':0}
    await evaluate('nhl:recommend')
    async with database() as session:
        f=await session.get(Fixture,'nhl:recommend');s=await session.get(Snapshot,f.id)
        assert f.gates['probability'] is False and f.suggested_stake==0
        assert s.prediction_home_probability==original and s.context['forecast_model_version']=='approved'
        assert len(calls)==1
        assert await session.scalar(select(func.count()).select_from(ProviderCall))==0
