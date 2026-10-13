from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
import httpx
import pytest
from sqlalchemy import select
from app.api import app
from app.clock import now
from app.models import Fixture,PersonalBet,EvaluationCycle,RuntimeLimit,State
from app.limits import Limits,BudgetExceeded
from app.ingestion import quote_identity

HEADERS={"Authorization":"Bearer test-session-token-32-characters-long"}

async def seed(database):
    async with database.begin() as session:
        session.add(Fixture(id="nhl:1",sport="NHL",home="Home",away="Away",commence_time=now()+timedelta(hours=2)))

async def test_private_routes_fail_closed(database):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
        assert (await client.get('/dashboard')).status_code==401
        assert (await client.get('/dashboard',headers=HEADERS)).status_code==200
        assert (await client.get('/health/live')).json()['timezone']=='America/Vancouver'

async def test_wager_idempotency_and_settlement_corrections(database):
    await seed(database)
    body={"request_id":str(uuid4()),"fixture_id":"nhl:1","selection":"Home","odds":"-110","stake_cad":"10.00"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test",headers=HEADERS) as client:
        first=await client.post('/bets',json=body)
        assert first.status_code==201,first.text
        bet_id=first.json()['id']
        assert (await client.post('/bets',json=body)).json()['id']==bet_id
        assert (await client.post('/bets',json={**body,"stake_cad":"11.00"})).status_code==409
        assert (await client.get('/dashboard')).json()['exposure']=='10.00'
        won=await client.patch(f'/bets/{bet_id}',json={"outcome":"WIN"})
        assert won.json()['profit_cad']=='9.09'
        assert (await client.get('/dashboard')).json()['bankroll']=='1109.09'
        assert (await client.patch(f'/bets/{bet_id}',json={"outcome":"VOID"})).json()['profit_cad']=='0.00'
        overview=(await client.get('/dashboard')).json()
        assert overview['bankroll']=='1100.00' and overview['roi']=='0.00'
        await client.patch(f'/bets/{bet_id}',json={"outcome":"PENDING"})
        assert (await client.get('/dashboard')).json()['exposure']=='10.00'
    async with database() as session:
        assert len((await session.scalars(select(PersonalBet))).all())==1

async def test_invalid_wagers_do_not_mutate_bankroll(database):
    await seed(database)
    body={"request_id":str(uuid4()),"fixture_id":"nhl:1","selection":"Home","odds":"1.00","stake_cad":"10.00"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test",headers=HEADERS) as client:
        assert (await client.post('/bets',json=body)).status_code==422
        assert (await client.post('/bets',json={**body,"odds":"2","stake_cad":"1100.01"})).status_code==409
        assert (await client.post('/bets',json={**body,"odds":"2","market":"totals"})).status_code==422
        assert (await client.post('/bets',json={**body,"odds":"2","selection":"Wrong team"})).status_code==422
        assert (await client.get('/bets')).json()==[]

async def test_oversized_mutation_body_is_rejected(database):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test",headers=HEADERS) as client:
        result=await client.post('/bets',content=b'{"padding":"'+b'x'*20000+b'"}',headers={'Content-Type':'application/json'})
        assert result.status_code==413

async def test_durable_limits_and_fixture_cycle_cap(database):
    await seed(database)
    guard=Limits()
    async with database.begin() as session:
        session.add(EvaluationCycle(id='cycle',fixture_id='nhl:1'))
    for _ in range(3): await guard.llm_attempt('cycle')
    with pytest.raises(BudgetExceeded):await guard.llm_attempt('cycle')
    await guard.reserve('openrouter',12)
    with pytest.raises(BudgetExceeded):await guard.reserve('openrouter')
    assert await guard.lease('worker',60)
    assert not await guard.lease('worker',60)
    await guard.trip('openrouter')
    assert await guard.blocked('openrouter')

def test_exact_market_line_identity():
    assert quote_identity('pinnacle','totals','Over','5.5')!=quote_identity('pinnacle','totals','Over','6.5')
    assert quote_identity('pinnacle','spreads','Home','-1.5')!=quote_identity('pinnacle','totals','Home','-1.5')
    assert quote_identity('pinnacle','totals','Over','5.500')==quote_identity('pinnacle','totals','Over','5.5')
    with pytest.raises(ValueError):quote_identity('pinnacle','totals','Over',None)
    with pytest.raises(ValueError):quote_identity('pinnacle','h2h','Home',1)
