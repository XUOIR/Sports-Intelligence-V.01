from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
import httpx
import pytest
from sqlalchemy import select,func
from app.api import app
from app.clock import now
from app.models import Fixture,MarketOdds,Snapshot,PersonalBet,Outcome
from app.ingestion import ingest_odds,quote_identity
from app.market_display import latest_quotes

HEADERS={'Authorization':'Bearer test-session-token-32-characters-long'}

@pytest.mark.parametrize('offset,ambiguous,expected',[(10,False,2),(16,False,0),(10,True,0)])
async def test_puck_drop_matching_is_bounded_unique_and_never_reschedules(database,monkeypatch,offset,ambiguous,expected):
    start=now()+timedelta(hours=2)
    async with database.begin() as session:
        session.add(Fixture(id='nhl:display',sport='NHL',home='Washington Capitals',away='Montréal Canadiens',commence_time=start))
        if ambiguous:session.add(Fixture(id='nhl:duplicate',sport='NHL',home='Washington Capitals',away='Montréal Canadiens',commence_time=start+timedelta(minutes=1)))
    async def fake(sport,**kwargs):
        return [{'id':'external','commence_time':(start+timedelta(minutes=offset)).isoformat(),'home_team':'Washington Capitals','away_team':'Montreal Canadiens',
            'bookmakers':[{'key':'playnow_ca','last_update':now().isoformat(),'markets':[{'key':'h2h','outcomes':[
                {'name':'Washington Capitals','price':2},{'name':'Montreal Canadiens','price':1.9}]}]}]}]
    monkeypatch.setattr('app.providers.odds',fake)
    report={};await ingest_odds(refresh_id='test',report=report)
    async with database() as session:
        fixture=await session.get(Fixture,'nhl:display')
        assert fixture.commence_time==start
        assert await session.scalar(select(func.count()).select_from(MarketOdds))==expected
        assert report['quotes_saved']==expected
        if expected:assert fixture.metrics['odds_start_offset_seconds']==600

async def test_latest_quotes_are_batched_and_keep_expired_prices(database):
    start=now()+timedelta(hours=2)
    async with database.begin() as session:
        session.add(Fixture(id='nhl:quotes',sport='NHL',home='Home',away='Away',commence_time=start))
        await session.flush()
        for ago,price in [(90,'1.8'),(30,'2.0')]:
            session.add(MarketOdds(fixture_id='nhl:quotes',bookmaker='playnow',market='h2h',selection='Home',line=None,
                decimal_odds=price,implied_probability=1/Decimal(price),source_at=now()-timedelta(minutes=ago),identity=quote_identity('playnow','h2h','Home',None)))
    async with database() as session:
        quotes=await latest_quotes(session,['nhl:quotes'])
        assert len(quotes['nhl:quotes'])==1 and quotes['nhl:quotes'][0].decimal_odds==Decimal('2')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers=HEADERS) as client:
        result=(await client.get('/dashboard')).json()
        assert result['market_odds']['nhl:quotes'][0]['decimal_odds'].startswith('2.')
        assert result['stale'] is True
        assert (await client.get('/dashboard?date=bad')).status_code==422
        other=now().date()+timedelta(days=1)
        result=(await client.get(f'/dashboard?date={other}')).json()
        assert result['fixtures']==[] and result['market_odds']=={} and result['source_updated_at'] is None

async def test_model_page_is_private_sport_scoped_and_never_counts_tickets_as_predictions(database):
    at=now()
    async with database.begin() as session:
        for sport in ['NHL','MLB']:
            session.add(Fixture(id=f'{sport}:test',sport=sport,home='Home',away='Away',commence_time=at))
        await session.flush()
        session.add(PersonalBet(request_id=str(uuid4()),fixture_id='NHL:test',selection='Home',odds_taken=2,stake_cad=10,unit_size_at_execution=100,outcome=Outcome.WIN,profit_cad=10))
        session.add(Snapshot(fixture_id='MLB:test',anchor_at=at,game_date=at.date(),vector=[],evidence_ids=[],model_version='test',prediction_home_probability='.7',final_home_win=True))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        assert (await client.get('/performance')).status_code==401
        result=(await client.get('/performance?sport=NHL',headers=HEADERS)).json()
        assert result['model']['predicted']==result['model']['evaluated']==0
        assert result['predictions']==[] and result['model']['accuracy'] is None
        assert (await client.get('/performance?sport=MLB',headers=HEADERS)).status_code==422
    async with database.begin() as session:
        session.add(Snapshot(fixture_id='NHL:test',anchor_at=at,game_date=at.date(),vector=[],evidence_ids=[],model_version='test',prediction_home_probability='.4',final_home_win=True))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers=HEADERS) as client:
        result=(await client.get('/performance')).json()
        assert result['model']['evaluated']==1 and result['model']['accuracy']=='0.00'
        assert result['predictions'][0]['selection']=='Away' and result['predictions'][0]['result']=='INCORRECT'
