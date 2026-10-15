from datetime import timedelta
from decimal import Decimal
from sqlalchemy import select,delete
from app.clock import now
from app.models import Fixture,Evidence,Snapshot,MarketOdds,ModelValidation,JobLease,State
from app.engine import freeze,evaluate
from app.ingestion import quote_identity
from app.model_config import MODEL_VERSION,baseline_digest

async def test_exact_anchor_freezes_only_pre_cutoff_evidence(database,monkeypatch):
    anchor=now();start=anchor+timedelta(minutes=30)
    source_time=anchor-timedelta(seconds=1)
    history=[{'started_at':(start-timedelta(days=i+2)).isoformat(),'ended_at':(start-timedelta(days=i+2)+timedelta(hours=3)).isoformat(),'win':True} for i in range(5)]
    async with database.begin() as session:
        session.add(Fixture(id='nhl:freeze',sport='NHL',home='Home',away='Away',commence_time=start));await session.flush()
        for kind,payload in [('schedule',{'start':start.isoformat()}),('standings',{'home':{'games':5,'points_pct':.5},'away':{'games':5,'points_pct':.5}}),
            ('history',{'home':history,'away':history}),('model_factors',{'goalie_personnel':0,'expected_goals':0,'rest_fatigue':0,'venue_special_teams':0})]:
            session.add(Evidence(fixture_id='nhl:freeze',kind=kind,source_at=source_time,observed_at=source_time,payload=payload))
    monkeypatch.setattr('app.engine.now',lambda:anchor+timedelta(seconds=1))
    await freeze('nhl:freeze')
    async with database() as session:
        snapshot=await session.get(Snapshot,'nhl:freeze')
        assert snapshot and len(snapshot.vector)==15 and snapshot.baseline_home_probability is None
        assert len(snapshot.context['sources'])==3
        original=snapshot.vector
    await freeze('nhl:freeze')
    async with database() as session:
        assert (await session.get(Snapshot,'nhl:freeze')).vector==original

async def test_missed_anchor_cannot_be_backfilled(database,monkeypatch):
    anchor=now()
    async with database.begin() as session:
        session.add(Fixture(id='nhl:late',sport='NHL',home='Home',away='Away',commence_time=anchor+timedelta(minutes=30)))
    monkeypatch.setattr('app.engine.now',lambda:anchor+timedelta(seconds=6))
    await freeze('nhl:late')
    async with database() as session:
        assert await session.get(Snapshot,'nhl:late') is None
        assert (await session.get(Fixture,'nhl:late')).state==State.HOLD

async def seed_recommendation(database):
    current=now();start=current+timedelta(minutes=20);anchor=start-timedelta(minutes=30)
    async with database.begin() as session:
        session.add(Fixture(id='nhl:recommend',sport='NHL',home='Home',away='Away',commence_time=start,metrics={
            'personnel_confirmed':True,'confirmed_at':current.isoformat(),'goalie_confirmations':{'home':'Home Starter','away':'Away Starter'},'other_markets_verified':True,'opposing_case_verified':True,
            'execution_source_present':True,'execution_verified_at':current.isoformat()},revision=1))
        await session.flush()
        session.add(Snapshot(fixture_id='nhl:recommend',anchor_at=anchor,collected_at=anchor+timedelta(seconds=1),game_date=start.date(),
            vector=[.5,.5,0,10,10,.5,.5,0,5,5,1,1,0,0,0],evidence_ids=[],model_version=MODEL_VERSION,baseline_home_probability=Decimal('.7'),context={'baseline_digest':baseline_digest('NHL'),'research_factors':{'starter_evidence':{'payload':{'home':'Home Starter','away':'Away Starter'}}}}))
        session.add(ModelValidation(version='approved',sport='NHL',parameters={'slope':1,'intercept':0},approved=True,
            created_at=current-timedelta(days=1),report={'baseline_version':MODEL_VERSION,'baseline_digest':baseline_digest('NHL'),
                'passing':True,'train_records':300,'calibration_records':100,'test_records':100,'test_brier':'.19','reference_brier':'.25',
                'test_through':(current-timedelta(days=10)).isoformat()}))
        for selection in ('Home','Away'):
            session.add(MarketOdds(fixture_id='nhl:recommend',bookmaker='playnow',market='h2h',selection=selection,line=None,
                decimal_odds=2,implied_probability=Decimal('.5'),source_at=current,identity=quote_identity('playnow','h2h',selection,None)))

async def test_all_gates_recommend_and_assessment_is_reused(database,monkeypatch):
    await seed_recommendation(database);calls=[]
    async def review(*args):
        calls.append(1)
        return {'opposing_case':'Verified adverse case for isolated test','risks':[],'opposing_case_verified':True,'other_markets_verified':True,'veto_verified':True,'veto_reason':''}
    monkeypatch.setattr('app.engine.doublecheck',review)
    await evaluate('nhl:recommend')
    async with database() as session:
        fixture=await session.get(Fixture,'nhl:recommend')
        assert fixture.state==State.RECOMMEND and fixture.suggested_stake==Decimal('16.50')
        assert all(fixture.gates.values())
    async with database.begin() as session:
        await session.execute(delete(JobLease))
    await evaluate('nhl:recommend')
    assert len(calls)==1

async def test_evidence_change_during_llm_review_revokes_approval(database,monkeypatch):
    await seed_recommendation(database)
    async def changed(*args):
        async with database.begin() as session:
            fixture=await session.get(Fixture,'nhl:recommend')
            fixture.revision+=1
        return {'opposing_case':'Verified adverse case for isolated test','risks':[],'opposing_case_verified':True,'other_markets_verified':True,'veto_verified':True,'veto_reason':''}
    monkeypatch.setattr('app.engine.doublecheck',changed)
    await evaluate('nhl:recommend')
    async with database() as session:
        fixture=await session.get(Fixture,'nhl:recommend')
        assert fixture.state==State.HOLD and fixture.dirty and fixture.suggested_stake==0
