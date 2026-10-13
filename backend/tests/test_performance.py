from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
import httpx
from app.api import app
from app.clock import now
from app.models import Fixture, PersonalBet, Outcome, Snapshot

HEADERS={'Authorization':'Bearer test-session-token-32-characters-long'}

async def overview():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers=HEADERS) as client:
        response=await client.get('/dashboard')
        assert response.status_code==200,response.text
        return response.json()['performance']

async def test_no_results_are_unknown_not_invented(database):
    result=await overview()
    assert result['wins']==result['settled']==0
    assert result['win_rate'] is None and result['roi'] is None
    assert result['curve']==[] and result['model']['accuracy'] is None

async def test_all_history_push_void_pending_and_model_results(database):
    timestamp=now()
    async with database.begin() as session:
        session.add_all([Fixture(id=f'nhl:{i}',sport='NHL',home='Home',away='Away',commence_time=timestamp) for i in range(3)])
        await session.flush()
        for i in range(101):
            session.add(PersonalBet(request_id=str(uuid4()),fixture_id='nhl:0',selection='Home',odds_taken=2,
                stake_cad=10,unit_size_at_execution=100,outcome=Outcome.WIN,profit_cad=10,updated_at=timestamp-timedelta(days=2)))
        for outcome,profit,days in [(Outcome.LOSS,-10,1),(Outcome.PUSH,0,1),(Outcome.VOID,0,0),(Outcome.PENDING,0,0)]:
            session.add(PersonalBet(request_id=str(uuid4()),fixture_id='nhl:0',selection='Home',odds_taken=2,
                stake_cad=10,unit_size_at_execution=100,outcome=outcome,profit_cad=profit,updated_at=timestamp-timedelta(days=days)))
        for i,p,actual in [(0,Decimal('.8'),True),(1,Decimal('.2'),True),(2,None,False)]:
            session.add(Snapshot(fixture_id=f'nhl:{i}',anchor_at=timestamp,game_date=timestamp.date(),vector=[],
                evidence_ids=[],model_version='test',prediction_home_probability=p,final_home_win=actual))
    result=await overview()
    assert (result['wins'],result['losses'],result['pushes'],result['voids'],result['pending'])==(101,1,1,1,1)
    assert result['settled']==103 and result['win_rate']=='99.02'
    assert result['settled_stake']=='1030.00' and result['profit']=='1000.00' and result['roi']=='97.09'
    assert [p['profit'] for p in result['curve']]==['1010.00','1000.00']
    assert result['model']=={'evaluated':2,'accuracy':'50.00','brier':'0.3400'}

async def test_manual_correction_recomputes_results_and_curve(database):
    async with database.begin() as session:
        session.add(Fixture(id='nhl:correction',sport='NHL',home='Home',away='Away',commence_time=now()))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers=HEADERS) as client:
        response=await client.post('/bets',json={'request_id':str(uuid4()),'fixture_id':'nhl:correction','selection':'Home','odds':'2','stake_cad':'10'})
        bet_id=response.json()['id']
        assert (await client.patch(f'/bets/{bet_id}',json={'outcome':'WIN'})).status_code==200
        assert (await overview())['win_rate']=='100.00'
        await client.patch(f'/bets/{bet_id}',json={'outcome':'LOSS'})
        result=await overview()
        assert result['win_rate']=='0.00' and result['profit']=='-10.00' and result['roi']=='-100.00'
        assert result['curve'][-1]['profit']=='-10.00'
        await client.patch(f'/bets/{bet_id}',json={'outcome':'VOID'})
        result=await overview()
        assert result['roi'] is None and result['curve']==[] and result['voids']==1

async def test_curve_uses_vancouver_dates_across_dst(database):
    async with database.begin() as session:
        session.add(Fixture(id='nhl:dst',sport='NHL',home='Home',away='Away',commence_time=now()))
        await session.flush()
        # UTC midnight would incorrectly put both tickets on November 1.
        for hour in (6,9):
            session.add(PersonalBet(request_id=str(uuid4()),fixture_id='nhl:dst',selection='Home',odds_taken=2,
                stake_cad=10,unit_size_at_execution=100,outcome=Outcome.WIN,profit_cad=10,
                updated_at=datetime(2026,11,1,hour,tzinfo=timezone.utc)))
    assert (await overview())['curve']==[{'date':'2026-10-31','profit':'10.00'},{'date':'2026-11-01','profit':'20.00'}]

async def test_long_curve_is_bounded_without_losing_profit(database):
    async with database.begin() as session:
        session.add(Fixture(id='nhl:long',sport='NHL',home='Home',away='Away',commence_time=now()))
        await session.flush()
        for day in range(181):
            session.add(PersonalBet(request_id=str(uuid4()),fixture_id='nhl:long',selection='Home',odds_taken=2,
                stake_cad=10,unit_size_at_execution=100,outcome=Outcome.WIN,profit_cad=10,updated_at=now()-timedelta(days=day)))
    result=await overview()
    assert len(result['curve'])==180
    assert result['curve'][0]['profit']=='10.00' and result['curve'][-1]['profit']=='1810.00'
    assert result['profit']=='1810.00'
