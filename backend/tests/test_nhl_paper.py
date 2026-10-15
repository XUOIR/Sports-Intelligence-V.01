from copy import deepcopy
from datetime import timedelta, date
from decimal import Decimal
import json
import httpx
import pytest
from sqlalchemy import select, func, delete
from app import nhl_paper as paper, nhl_paper_history as history
from app.nhl_paper_model import (load_bundle, blank_state, canonical, apply_day, features, probability)
from app.models import (Fixture, ProviderState, PaperForecast, PaperPriceObservation, MarketOdds,
    PersonalBet, Account, JobLease, Snapshot, ModelValidation, PaperInputArchive)
from app.ingestion import quote_identity
from app.clock import now, aware
from app.api import app


def fixture(at=None):
    return Fixture(id='nhl:2026020001', sport='NHL', home='Toronto Maple Leafs', away='Edmonton Oilers',
        commence_time=(at or now())+timedelta(hours=2),
        metrics={'home_abbrev':'TOR', 'away_abbrev':'EDM', 'nhl_season':20262027, 'nhl_game_type':2})


def cache(at=None, games=None):
    at = at or now()
    return ProviderState(provider=history.KEY, observed_at=at, info={
        'as_of_date':str(at.astimezone(history.EASTERN).date()), 'season':2026, 'games':games or [],
        'source_sha256':'a'*64, 'observed_at':at.isoformat(), 'archive_sha256':'b'*64})


def quotes(f, at=None, book='playnow', odds='2.5'):
    at=at or now()
    return [MarketOdds(id=i, fixture_id=f.id, bookmaker=book, market='h2h', selection=team,
        line=None, decimal_odds=Decimal(odds), implied_probability=1/Decimal(odds),
        source_at=at, created_at=at, identity=quote_identity(book,'h2h',team,None))
        for i,team in enumerate((f.home,f.away),1)]


async def unlock(database):
    async with database.begin() as session:
        await session.execute(delete(JobLease).where(JobLease.key=='nhl-paper-collect'))


async def seed(database, price=True):
    f=fixture()
    async with database.begin() as session:
        session.add(f)
        session.add(cache())
        session.add(PaperInputArchive(sha256='b'*64,data=cache().info))
        await session.flush()
        if price:session.add_all(quotes(f))
    return f


def test_model_integrity_utah_continuity_and_no_numpy_dependency():
    bundle,digest=load_bundle()
    assert len(digest)==64 and bundle['approved_for_wagers'] is False
    assert canonical(59)==canonical(68) and canonical(53)!=canonical(68)
    assert bundle['seed']['teams']['59']['games']==164
    assert '68' not in bundle['seed']['teams']
    assert bundle['fit_seasons']==list(range(2018,2025)) and bundle['calibration_seasons']==[2025]
    assert bundle['seed']['through']=='2026-04-16'


def test_future_prediction_needs_no_outcome_and_cannot_use_same_day():
    bundle,_=load_bundle(); f=fixture()
    p,inputs=paper.forecast(bundle,f,cache(),now())
    assert 0<p<1 and inputs['approved_for_wagers'] is False
    assert inputs['lineup_policy'].startswith('Team-only')
    assert inputs['goalie_context']['personnel_confirmed'] is None
    bad=cache(games=[{'id':2026020002,'season':2026,'date':str(now().date()),'home':10,'away':22,'home_win':1}])
    with pytest.raises(ValueError,match='Same-day|future'):
        paper.forecast(bundle,f,bad,now())
    f.commence_time=now()-timedelta(seconds=1)
    with pytest.raises(ValueError):paper.forecast(bundle,f,cache(),now())


def test_expected_goalie_is_context_not_an_invented_adjustment():
    bundle,_=load_bundle();f=fixture()
    a,_=paper.forecast(bundle,f,cache(),now())
    f.metrics={**f.metrics,'personnel_confirmed':False,'goalie_confirmations':{'home':False,'away':False}}
    b,inputs=paper.forecast(bundle,f,cache(),now())
    assert a==b and inputs['goalie_context']['personnel_confirmed'] is False


def test_stale_history_and_tomorrow_block_instead_of_guessing():
    bundle,_=load_bundle();f=fixture()
    with pytest.raises(ValueError,match='not cached'):
        paper.forecast(bundle,f,cache(now()-timedelta(days=1)),now())
    f.commence_time=now()+timedelta(days=1)
    with pytest.raises(ValueError,match='Awaiting match day'):
        paper.forecast(bundle,f,cache(),now())


def test_first_ten_games_remain_real_expansion_warmup():
    state=blank_state()
    for i in range(10):
        apply_day(state,[{'id':i,'season':2024,'date':str(date(2024,10,1)+timedelta(days=i)),
                        'home':59,'away':10,'home_win':i%2}])
    assert len(features(state,68,10,'2024-10-11',2024))==3
    with pytest.raises(ValueError):features(state,59,68,'2024-10-11',2024)
    with pytest.raises(ValueError):features(state,59,10,'2024-10-10',2024)


@pytest.mark.parametrize('delta,status',[(0,'VALID'),(-301,'STALE_PRICES'),(1,'FUTURE_PRICE_REJECTED')])
def test_freshness_keeps_original_price_time(delta,status):
    at=now();f=fixture();q=quotes(f,at+timedelta(seconds=delta))
    got,data=paper.quote_observation(f,q,Decimal('.55'),at)
    assert got==status
    if status=='VALID':
        assert Decimal(data['home_edge'])==Decimal('.15')
        assert Decimal(data['away_edge'])==Decimal('.05')
        assert data['qualifies']['home'] is True
        assert Decimal(data['market_home_probability'])==Decimal('.5')


def test_no_qualifying_edge_and_never_mix_books_or_source_times():
    at=now();f=fixture();q=quotes(f,at,odds='1.91')
    status,data=paper.quote_observation(f,q,Decimal('.5'),at)
    assert status=='VALID' and 'qualifies' not in data
    q[1].bookmaker='bclc'
    assert paper.quote_observation(f,q,Decimal('.5'),at)[0]=='MISSING_MATCHED_PRICES'
    q[1].bookmaker='playnow';q[1].source_at-=timedelta(seconds=1)
    assert paper.quote_observation(f,q,Decimal('.5'),at)[0]=='MISSING_MATCHED_PRICES'


async def test_collection_freezes_once_without_paid_calls_or_bankroll_writes(database,monkeypatch):
    f=await seed(database)
    async def forbidden(*a,**k):raise AssertionError('No network allowed during collection')
    monkeypatch.setattr(paper.history.http,'request',forbidden)
    await paper.collect()
    async with database() as session:
        original=await session.scalar(select(PaperForecast))
        assert original.position and original.captured_at and original.home_probability
        saved_at=original.captured_at;p=original.home_probability
        assert await session.scalar(select(func.count()).select_from(PaperPriceObservation))==1
    await unlock(database);await paper.collect()
    async with database() as session:
        row=await session.scalar(select(PaperForecast))
        assert row.captured_at==saved_at and row.home_probability==p
        assert await session.scalar(select(func.count()).select_from(PaperForecast))==1
        assert await session.scalar(select(func.count()).select_from(PaperPriceObservation))==1
        assert await session.scalar(select(func.count()).select_from(PersonalBet))==0
        assert await session.scalar(select(func.count()).select_from(Snapshot))==0
        assert await session.scalar(select(func.count()).select_from(ModelValidation))==0
        assert (await session.get(Account,1)).initial_bankroll==Decimal(1100)


async def test_unpriced_forecast_and_blocked_attempt_are_preserved(database):
    await seed(database,price=False)
    async with database.begin() as session:
        cached=await session.get(ProviderState,history.KEY);await session.delete(cached)
    await paper.collect()
    async with database() as session:
        row=await session.scalar(select(PaperForecast));assert row.home_probability is None and row.issue
        seen=row.first_seen_at
    async with database.begin() as session:session.add(cache())
    await unlock(database);await paper.collect()
    async with database() as session:
        row=await session.scalar(select(PaperForecast))
        assert row.captured_at>=seen and row.home_probability is not None and row.position is None
        obs=await session.scalar(select(PaperPriceObservation))
        assert obs.status=='MISSING_MATCHED_PRICES'


async def test_stale_position_never_created_and_later_price_can_qualify(database):
    f=await seed(database,price=False)
    async with database.begin() as session:session.add_all(quotes(f,now()-timedelta(minutes=6)))
    await paper.collect()
    async with database.begin() as session:
        row=await session.scalar(select(PaperForecast));assert row.position is None
        for q in (await session.scalars(select(MarketOdds))).all():
            q.source_at=now();q.created_at=now()
    await unlock(database);await paper.collect()
    async with database() as session:
        row=await session.scalar(select(PaperForecast));assert row.position
        assert await session.scalar(select(func.count()).select_from(PaperPriceObservation))==2


async def test_game_start_during_collection_never_creates_late_position(database,monkeypatch):
    f=await seed(database)
    original=paper.latest_quotes
    async def crossing_start(session,ids):
        result=await original(session,ids)
        monkeypatch.setattr(paper,'now',lambda:aware(f.commence_time)+timedelta(seconds=1))
        return result
    monkeypatch.setattr(paper,'latest_quotes',crossing_start)
    await paper.collect()
    async with database() as session:
        row=await session.scalar(select(PaperForecast))
        assert row.captured_at<aware(f.commence_time) and row.position is None
        assert await session.scalar(select(func.count()).select_from(PaperPriceObservation))==0


async def test_schedule_change_voids_and_does_not_reissue_a_forecast(database):
    f=await seed(database);await paper.collect()
    async with database.begin() as session:
        saved=await session.get(Fixture,f.id);saved.commence_time+=timedelta(days=1)
    await paper.settle();await unlock(database);await paper.collect()
    async with database() as session:
        result=await paper.summary(session)
        assert result['positions']==1 and result['void_positions']==1 and result['profit_units']=='0'
        assert result['forecasts']==1 and result['roi_percent'] is None


async def test_result_settlement_scores_true_forecast_and_keeps_bankroll_separate(database,monkeypatch):
    f=await seed(database);await paper.collect()
    later=now()+timedelta(hours=5);monkeypatch.setattr(paper,'now',lambda:later)
    async with database.begin() as session:
        saved=await session.get(Fixture,f.id);saved.final_home_win=True
    await paper.settle();await paper.settle()
    async with database() as session:
        result=await paper.summary(session)
        assert result['resolved']==result['resolved_pairs']==result['settled_positions']==1
        assert Decimal(result['brier'])>=0 and result['paired_market_brier']=='0.25'
        assert result['records'][0]['resolution']=='FINAL'
        assert result['profit_units'] in {'1.50000000','-1'}
        assert (await session.get(Account,1)).initial_bankroll==Decimal(1100)
        assert await session.scalar(select(func.count()).select_from(PersonalBet))==0


async def test_cached_official_final_settles_without_waiting_for_result_fetch(database,monkeypatch):
    from app import ingestion
    f=await seed(database);await paper.collect()
    later=now()+timedelta(hours=5)
    monkeypatch.setattr(paper,'now',lambda:later);monkeypatch.setattr(ingestion,'now',lambda:later)
    async with database.begin() as session:
        session.add(ProviderState(provider=f'nhl-score:{aware(f.commence_time).date()}',observed_at=later,
            info={'games':[{'id':f.id,'commence_time':aware(f.commence_time).isoformat(),
                'home':f.home,'away':f.away,'game_state':'OFF','schedule_state':'OK','home_score':3,'away_score':2}]}))
    await paper.settle()
    async with database() as session:
        row=await session.scalar(select(PaperForecast))
        assert row.resolution=='FINAL' and row.result_home_win is True
        assert row.result_source['source']=='NHL public API score cache'
        assert (await session.get(Fixture,f.id)).final_home_win is None


def scheduled_payload():
    return {'total':2,'data':[{'id':2026020001+i,'gameType':2,'season':20262027,
        'gameDate':f'2026-10-{12+i:02d}','easternStartTime':f'2026-10-{12+i:02d}T19:00:00',
        'homeTeamId':10,'visitingTeamId':22,'homeScore':3,'visitingScore':2,
        'gameStateId':7,'gameScheduleStateId':1,'period':3} for i in range(2)]}


def test_complete_season_validation_excludes_same_day_and_rejects_missing_or_unresolved():
    bundle,_=load_bundle();payload=scheduled_payload()
    assert len(history.normalize(payload,2026,date(2026,10,13),bundle['teams']))==1
    payload['data'][0]['gameStateId']=1
    with pytest.raises(ValueError,match='unresolved'):
        history.normalize(payload,2026,date(2026,10,13),bundle['teams'])
    payload['total']=3
    with pytest.raises(ValueError,match='pagination'):
        history.normalize(payload,2026,date(2026,10,13),bundle['teams'])


async def test_history_one_success_per_day_shared_nhl_budget(database,monkeypatch):
    bundle,_=load_bundle();calls=[]
    async def request(provider,method,url,**kwargs):
        calls.append((provider,url));return scheduled_payload()
    monkeypatch.setattr(history.http,'request',request)
    await history.refresh(bundle);await history.refresh(bundle)
    assert len(calls)==1 and calls[0][0]=='nhl' and calls[0][1].startswith('https://api.nhle.com/')
    async with database() as session:
        saved=await session.get(ProviderState,history.KEY)
        archived=await session.get(PaperInputArchive,saved.info['archive_sha256'])
        assert archived.data['games']==saved.info['games'] and len(archived.data['games'])==2


async def test_performance_route_is_private_and_read_only(database,monkeypatch):
    async def forbidden(*a,**k):raise AssertionError('GET cannot collect or refresh')
    monkeypatch.setattr(history.http,'request',forbidden)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        assert (await client.get('/performance')).status_code==401
        response=await client.get('/performance',headers={'Authorization':'Bearer test-session-token-32-characters-long'})
        assert response.status_code==200,response.text
        data=response.json()['paper']
        assert data['mode']=='paper_only' and data['forecasts']==0 and data['approved_for_wagers'] is False
