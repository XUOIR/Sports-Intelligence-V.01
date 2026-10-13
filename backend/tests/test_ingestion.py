from datetime import timedelta
from sqlalchemy import select
import pytest
from app.clock import now
from app.models import Fixture,MarketOdds,State,Snapshot,AuditLog
from app.ingestion import ingest_odds,reschedule
from app.providers import goalie_confirmation,array
from app.http import ProviderError

async def test_source_alias_withdrawal_and_anomalous_prices(database,monkeypatch):
    start=now()+timedelta(hours=2)
    async with database.begin() as session:
        session.add(Fixture(id='nhl:7',sport='NHL',home='Home',away='Away',commence_time=start))
    markets=[{'key':'h2h','outcomes':[{'name':'Home','price':2},{'name':'Away','price':1.9}]}]
    books=[{'key':'playnow_ca','last_update':now().isoformat(),'markets':markets}]
    async def fake(sport):
        return [{'id':'external','commence_time':start.isoformat(),'home_team':'Home','away_team':'Away','bookmakers':books}] if sport=='NHL' else []
    monkeypatch.setattr('app.providers.odds',fake)
    await ingest_odds()
    async with database() as session:
        fixture=await session.get(Fixture,'nhl:7')
        assert fixture.metrics['execution_source_present'] is True
        quotes=(await session.scalars(select(MarketOdds))).all()
        assert len(quotes)==2 and all(q.bookmaker=='playnow' for q in quotes)
    books.clear()
    await ingest_odds()
    async with database() as session:
        assert (await session.get(Fixture,'nhl:7')).metrics['execution_source_present'] is False
    books.append({'key':'playnow_ca','last_update':now().isoformat(),'markets':[{'key':'h2h','outcomes':[{'name':'Home','price':1.0001},{'name':'Away','price':1.9}]}]})
    await ingest_odds()
    async with database() as session:
        assert (await session.get(Fixture,'nhl:7')).metrics['execution_source_present'] is False

async def test_reschedule_archives_snapshot_and_allows_new_anchor(database):
    start=now()+timedelta(hours=2)
    async with database.begin() as session:
        fixture=Fixture(id='nhl:8',sport='NHL',home='Home',away='Away',commence_time=start)
        session.add(fixture);await session.flush()
        session.add(Snapshot(fixture_id=fixture.id,anchor_at=start-timedelta(minutes=30),game_date=start.date(),vector=[0]*15,evidence_ids=[],model_version='baseline-v0.1'))
    async with database.begin() as session:
        fixture=await session.get(Fixture,'nhl:8')
        await reschedule(session,fixture,start+timedelta(days=1))
    async with database() as session:
        assert await session.get(Snapshot,'nhl:8') is None
        assert (await session.get(Fixture,'nhl:8')).state==State.HOLD
        audit=await session.scalar(select(AuditLog))
        assert audit.action=='ARCHIVE_RESCHEDULED_SNAPSHOT' and len(audit.details['vector'])==15

def test_probable_goalie_is_never_treated_as_confirmed():
    assert not any(goalie_confirmation({'matchup':{'goalieComparison':{'homeTeam':{'playerId':1}}}}).values())
    assert not any(goalie_confirmation({}).values())
    with pytest.raises(ProviderError):array({'gameWeek':None},'gameWeek')
    with pytest.raises(ProviderError):array([None])
