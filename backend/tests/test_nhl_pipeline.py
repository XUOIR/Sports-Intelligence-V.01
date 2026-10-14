"""Isolated rehearsal: synthetic approvals never touch the live database."""
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from copy import deepcopy
import pytest
from sqlalchemy import select,delete,func
from app.clock import now
from app.models import Fixture,Snapshot,Evidence,ProviderState,MarketOdds,ModelValidation,JobLease,State,ProviderCall
from app.model_config import MODEL_VERSION,baseline_digest
from app.nhl_history import HISTORY_CONTRACT
from app import engine,ingestion
from app.ingestion import quote_identity
from app.verification import price_pair
from app.calibrate import validate


async def seed(database,at):
    start=at+timedelta(minutes=30);observed=at-timedelta(seconds=1)
    history=[{'contract':HISTORY_CONTRACT,'game_id':str(2026020000+i),'game_type':2,'season':20262027,
        'started_at':(start-timedelta(days=i)).isoformat(),'completion_observed_at':observed.isoformat(),'win':i%2==0} for i in range(1,7)]
    factors={key:.2 for key in ('goalie_personnel','expected_goals','rest_fatigue','venue_special_teams')}
    async with database.begin() as session:
        session.add(Fixture(id='nhl:2026020900',sport='NHL',home='Home',away='Away',commence_time=start,metrics={
            'nhl_season':20262027,'personnel_confirmed':True,'confirmed_at':observed.isoformat(),
            'other_markets_verified':True,'opposing_case_verified':True,'execution_source_present':True,'execution_verified_at':observed.isoformat()}))
        await session.flush()
        for kind,payload in [('schedule',{'start':start.isoformat()}),('standings',{'home':{'games':6,'points_pct':.5},'away':{'games':6,'points_pct':.5}}),
                ('history',{'contract':HISTORY_CONTRACT,'home':history,'away':history}),('model_factors',factors)]:
            session.add(Evidence(fixture_id='nhl:2026020900',kind=kind,source_at=observed,observed_at=observed,payload=payload))
        session.add(ModelValidation(version='isolated-test-approval',sport='NHL',approved=True,created_at=at-timedelta(days=1),parameters={'slope':1,'intercept':0},report={
            'baseline_version':MODEL_VERSION,'baseline_digest':baseline_digest('NHL'),'passing':True,'train_records':300,'calibration_records':100,'test_records':100,
            'test_brier':'.19','reference_brier':'.25','test_through':(at-timedelta(days=10)).isoformat()}))
        for side in ('Home','Away'):
            session.add(MarketOdds(fixture_id='nhl:2026020900',bookmaker='playnow',market='h2h',selection=side,line=None,
                decimal_odds=2,implied_probability='.5',source_at=observed,identity=quote_identity('playnow','h2h',side,None)))


async def test_freeze_forecast_price_expiry_and_result_label_work_together(database,monkeypatch):
    at=now();await seed(database,at)
    monkeypatch.setattr(engine,'now',lambda:at+timedelta(seconds=1))
    monkeypatch.setattr('app.readiness.now',lambda:at+timedelta(seconds=1))
    await engine.freeze('nhl:2026020900')
    calls=[]
    async def review(*args):
        calls.append(1)
        return {'opposing_case':'Isolated test review only','opposing_case_verified':True,'other_markets_verified':True,'veto_verified':True}
    monkeypatch.setattr(engine,'doublecheck',review)
    await engine.evaluate('nhl:2026020900')
    async with database() as session:
        f=await session.get(Fixture,'nhl:2026020900');s=await session.get(Snapshot,f.id)
        assert f.state==State.RECOMMEND and f.suggested_stake==Decimal('16.50')
        assert s.collected_at==at+timedelta(seconds=1) and len(s.evidence_ids)==4
        assert s.context['factor_source']['payload']==s.context['factors']
        probability=f.probability
    # Expiring prices removes the stake/edge, preserving the real saved forecast.
    monkeypatch.setattr(engine,'now',lambda:at+timedelta(minutes=6))
    async with database.begin() as session:await session.execute(delete(JobLease))
    await engine.evaluate('nhl:2026020900')
    async with database() as session:
        f=await session.get(Fixture,'nhl:2026020900')
        assert f.probability==probability and f.selection=='Home'
        assert f.edge is None and f.target_price is None and f.suggested_stake==0 and f.state!=State.RECOMMEND
    assert len(calls)==1
    # A saved final score supplies the outcome; no provider or AI call is needed.
    after=at+timedelta(hours=4);monkeypatch.setattr(ingestion,'now',lambda:after)
    monkeypatch.setattr('app.calibrate.now',lambda:after)
    async def forbidden(*args):pytest.fail('Saved finals must not consume a provider request')
    monkeypatch.setattr(ingestion.providers,'nhl_game',forbidden)
    async with database.begin() as session:
        session.add(ProviderState(provider=f'nhl-score:{(at+timedelta(minutes=30)).date()}',observed_at=after,info={'games':[{
            'id':'nhl:2026020900','home':'Home','away':'Away','commence_time':(at+timedelta(minutes=30)).isoformat(),
            'game_state':'OFF','home_score':3,'away_score':2}]}))
    counts=await ingestion.ingest_results()
    assert counts['from_cache']==1 and counts['requests']==0
    async with database() as session:
        f=await session.get(Fixture,'nhl:2026020900');s=await session.get(Snapshot,f.id)
        assert s.final_home_win is True and s.brier is not None
        record={'fixture_id':f.id,'sport':f.sport,'model_version':s.model_version,'vector':s.vector,'factors':s.context['factors'],
            'factor_source':s.context['factor_source'],'result_source':s.context['result_source'],'sources':s.context['sources'],'commence_time':f.commence_time.isoformat(),
            'anchor_at':s.anchor_at.isoformat(),'collected_at':s.collected_at.isoformat(),'probability':str(s.baseline_home_probability),'outcome':1}
        validate([record])
        bad=deepcopy(record);bad['factor_source']['observed_at']=(at+timedelta(seconds=1)).isoformat()
        with pytest.raises(ValueError,match='provenance'):validate([bad])
        bad=deepcopy(record);bad['result_source']['game_id']='nhl:wrong'
        with pytest.raises(ValueError,match='final score'):validate([bad])
        bad=deepcopy(record);bad['outcome']=0
        with pytest.raises(ValueError,match='final score'):validate([bad])
        assert await session.scalar(select(func.count()).select_from(ProviderCall))==0


def test_new_partial_or_future_quote_cannot_reuse_an_older_opposite_side():
    at=now();f=SimpleNamespace(home='Home',away='Away')
    def q(side,seconds):return SimpleNamespace(bookmaker='playnow',market='h2h',line=None,selection=side,decimal_odds=Decimal(2),source_at=at+timedelta(seconds=seconds))
    previous=[q('Home',-20),q('Away',-20)]
    assert price_pair(previous,f,at)
    assert price_pair(previous+[q('Home',-10)],f,at) is None
    assert price_pair(previous+[q('Home',1)],f,at) is None


@pytest.mark.parametrize('home,away',[(True,2),('3',2),(-1,2),(3,3),(10000,2)])
def test_malformed_or_tied_finals_cannot_label_training(home,away):
    with pytest.raises(ValueError):ingestion.final_scores(home,away)


async def test_outcome_is_recovered_for_snapshot_without_a_baseline_or_new_requests(database,monkeypatch):
    at=now();start=at-timedelta(hours=4)
    async with database.begin() as session:
        session.add(Fixture(id='nhl:2026020901',sport='NHL',home='Home',away='Away',commence_time=start,final_home_win=False))
        await session.flush()
        session.add(Snapshot(fixture_id='nhl:2026020901',anchor_at=start-timedelta(minutes=30),game_date=start.date(),
            vector=[0]*15,evidence_ids=[],model_version=MODEL_VERSION,baseline_home_probability=None))
    async def forbidden(*args):pytest.fail('Outcome already exists')
    monkeypatch.setattr(ingestion.providers,'nhl_game',forbidden)
    result=await ingestion.ingest_results()
    assert result['labeled']==1 and result['requests']==0
    async with database() as session:
        s=await session.get(Snapshot,'nhl:2026020901')
        assert s.final_home_win is False and s.brier is None and s.prediction_home_probability is None


async def test_cached_checkpoints_are_registered_before_a_failed_startup_refresh(monkeypatch):
    from app import scheduler
    from app.limits import BudgetExceeded
    calls=[]
    async def register():calls.append('cached checkpoints')
    async def unavailable():
        calls.append('refresh');raise BudgetExceeded('Free API cap')
    monkeypatch.setattr(scheduler,'anchors',register)
    monkeypatch.setattr(scheduler,'daily_nhl',unavailable)
    with pytest.raises(BudgetExceeded):await scheduler.recover_startup()
    assert calls==['cached checkpoints','refresh']


@pytest.mark.parametrize('change',[
    {},{'id':2026020911},{'startTimeUTC':'broken'},
    {'homeTeam':{'abbrev':'WRONG','score':3}}, {'homeTeam':{'abbrev':'TOR','score':True}}])
async def test_only_matching_official_final_game_can_create_an_outcome(database,monkeypatch,change):
    start=now()-timedelta(hours=4)
    async with database.begin() as session:
        session.add(Fixture(id='nhl:2026020910',sport='NHL',home='Home',away='Away',commence_time=start,
            metrics={'home_abbrev':'TOR','away_abbrev':'EDM'}))
    payload={'id':2026020910,'startTimeUTC':start.isoformat(),'gameState':'OFF',
        'homeTeam':{'abbrev':'TOR','score':3},'awayTeam':{'abbrev':'EDM','score':2},**change}
    calls=[]
    async def official(game_id):calls.append(game_id);return payload
    monkeypatch.setattr(ingestion.providers,'nhl_game',official)
    result=await ingestion.ingest_results()
    assert result['requests']==1 and calls==['2026020910']
    async with database() as session:
        f=await session.get(Fixture,'nhl:2026020910')
        assert f.final_home_win is (None if change else True)


async def test_a_free_api_failure_does_not_discard_already_recovered_outcomes(database,monkeypatch):
    from app.limits import BudgetExceeded
    start=now()-timedelta(hours=4)
    async with database.begin() as session:
        session.add(Fixture(id='nhl:2026020910',sport='NHL',home='Home',away='Away',commence_time=start,final_home_win=True))
        session.add(Fixture(id='nhl:2026020911',sport='NHL',home='Other',away='Other away',commence_time=start+timedelta(minutes=1)))
        await session.flush()
        session.add(Snapshot(fixture_id='nhl:2026020910',anchor_at=start-timedelta(minutes=30),game_date=start.date(),
            vector=[0]*15,evidence_ids=[],model_version=MODEL_VERSION))
    async def exhausted(*args):raise BudgetExceeded('Free cap reached')
    monkeypatch.setattr(ingestion.providers,'nhl_game',exhausted)
    result=await ingestion.ingest_results()
    assert result['labeled']==1 and result['requests']==1
    async with database() as session:
        assert (await session.get(Snapshot,'nhl:2026020910')).final_home_win is True
