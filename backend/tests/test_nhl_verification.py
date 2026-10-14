from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
import httpx
import pytest
from sqlalchemy import select, func
from app.api import app
from app.clock import aware
from app.models import Fixture, Evidence, Snapshot, MarketOdds, ProviderCall
from app.nhl_history import completed_games, HISTORY_CONTRACT
from app.features import frozen_vector
from app.ingestion import ingest_nhl, quote_identity
from app.calibrate import validate
from app.model_config import MODEL_VERSION

AT = aware('2026-10-14T12:00:00-07:00')
START = aware('2026-10-14T16:30:00-07:00')
HEADERS = {'Authorization': 'Bearer test-session-token-32-characters-long'}


def raw(index, days=1, game_type=2, team='MTL'):
    return {'id': 2026020000 + index, 'season': 20262027, 'gameType': game_type, 'gameState': 'OFF',
            'startTimeUTC': (START - timedelta(days=days)).isoformat(),
            'homeTeam': {'abbrev': team, 'score': 4}, 'awayTeam': {'abbrev': 'BUF', 'score': 3}}


def history(team='MTL'):
    return [raw(index, index, team=team) for index in range(1, 7)]


def test_completed_yesterday_counts_as_back_to_back_without_fake_end_time():
    rows = completed_games(history(), 'MTL', 20262027, AT, START)
    assert len(rows) == 6 and all('ended_at' not in row for row in rows)
    vector = frozen_vector({'games': 6, 'points_pct': .6}, {'games': 6, 'points_pct': .5}, {'home': rows, 'away': rows}, START)
    assert len(vector) == 15 and vector[8:10] == [6, 6]
    assert vector[10:] == [0, 0, 0, 1, 1]


@pytest.mark.parametrize('change', [
    {'gameType': 1}, {'season': 20252026}, {'gameState': 'FUT'}, {'startTimeUTC': START.isoformat()},
    {'startTimeUTC': 'broken'}, {'homeTeam': {'abbrev': 'MTL', 'score': 3}},
    {'homeTeam': {'abbrev': 'MTL', 'score': True}}, {'homeTeam': {'abbrev': 'OTHER', 'score': 4}},
])
def test_ineligible_rows_never_contaminate_form(change):
    invalid = raw(90, 2); invalid.update(change)
    rows = completed_games(history() + [invalid], 'MTL', 20262027, AT, START)
    assert len(rows) == 6 and all(row['game_id'] != '2026020090' for row in rows)


def test_preseason_split_squad_duplicates_cannot_break_regular_history():
    first, second = raw(91, 20, 1), raw(92, 20, 1)
    rows = completed_games(history() + [first, second], 'MTL', 20262027, AT, START)
    assert len(rows) == 6
    duplicate = deepcopy(history()[0]); duplicate['homeTeam']['score'] = 1
    with pytest.raises(ValueError):
        completed_games(history() + [duplicate], 'MTL', 20262027, AT, START)
    assert completed_games(history(), 'MTL', 20262027, START, START) == []


def test_legacy_history_cannot_approve_new_nhl_contract():
    anchor=START-timedelta(minutes=30)
    record={'fixture_id':'nhl:test','sport':'NHL','model_version':MODEL_VERSION,'vector':[0]*15,
            'probability':'.5','outcome':1,'commence_time':START.isoformat(),'anchor_at':anchor.isoformat(),
            'collected_at':anchor.isoformat(),'sources':{kind:{'source_at':(anchor-timedelta(minutes=1)).isoformat(),'observed_at':(anchor-timedelta(minutes=1)).isoformat(),
            'payload':{'home':[],'away':[]}} for kind in ('schedule','standings','history')}}
    record['sources']['standings']['payload']={'home':{'games':6,'points_pct':.5},'away':{'games':6,'points_pct':.5}}
    with pytest.raises(ValueError,match='Legacy NHL history'):
        validate([record])


async def seed(database):
    rows = completed_games(history(), 'MTL', 20262027, AT, START)
    async with database.begin() as session:
        session.add(Fixture(id='nhl:2026020106', sport='NHL', home='Washington Capitals', away='Montréal Canadiens',
                            commence_time=START, metrics={'nhl_season': 20262027}, gates={}))
        await session.flush()
        for kind, payload in [('schedule', {'start': START.isoformat()}),
                              ('standings', {'home': {'games': 6, 'points_pct': .5}, 'away': {'games': 6, 'points_pct': .6}}),
                              ('history', {'contract': HISTORY_CONTRACT, 'home': rows, 'away': rows})]:
            session.add(Evidence(fixture_id='nhl:2026020106', kind=kind, source_at=AT, observed_at=AT, payload=payload))


async def test_pre_anchor_panel_explains_sources_without_network_or_granting_gates(database, monkeypatch):
    await seed(database)
    monkeypatch.setattr('app.verification.now', lambda: AT)
    async def forbidden(*args, **kwargs):
        raise AssertionError('Opening a match must not contact providers')
    monkeypatch.setattr('app.providers.http.request', forbidden)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.get('/fixtures/nhl:2026020106')).status_code == 401
        result = (await client.get('/fixtures/nhl:2026020106', headers=HEADERS)).json()
        assert result['fixture']['gates'] == {} and result['fixture']['probability'] is None
        panel = result['verification']
        assert panel['phase'] == 'waiting_for_anchor' and panel['paid_credits'] == 0
        assert len(panel['checks']) == 8 and not any(c['status'] == 'passed' for c in panel['checks'])
        assert panel['form']['away']['back_to_back'] is True
        assert all(i['status'] == 'available' for i in panel['inputs'][:3])
    async with database() as session:
        assert await session.scalar(select(func.count()).select_from(ProviderCall)) == 0
        assert (await session.get(Fixture, 'nhl:2026020106')).gates == {}


async def test_expired_price_and_missed_anchor_are_explicit(database, monkeypatch):
    await seed(database)
    at = START - timedelta(minutes=20)
    monkeypatch.setattr('app.verification.now', lambda: at)
    async with database.begin() as session:
        for selection in ('Washington Capitals', 'Montréal Canadiens'):
            session.add(MarketOdds(fixture_id='nhl:2026020106', bookmaker='playnow', market='h2h', selection=selection, line=None,
                decimal_odds=2, implied_probability=Decimal('.5'), source_at=at - timedelta(minutes=6), identity=quote_identity('playnow', 'h2h', selection, None)))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', headers=HEADERS) as client:
        panel = (await client.get('/fixtures/nhl:2026020106')).json()['verification']
        assert panel['phase'] == 'anchor_missing'
        assert panel['checks'][0]['status'] == 'blocked' and 'older than five minutes' in panel['checks'][0]['message']
        assert 'retrospective' in panel['message']


async def test_starter_evidence_can_be_recorded_without_inventing_factors(database, monkeypatch):
    await seed(database)
    monkeypatch.setattr('main.now', lambda: AT)
    body = {'source_at': AT.isoformat(), 'source_reference': 'https://www.nhl.com/canadiens/news/starting-goalie',
            'personnel_confirmed': True, 'home_goalie': 'Verified Home', 'away_goalie': 'Verified Away',
            'other_markets_verified': False, 'opposing_case_verified': False}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', headers=HEADERS) as client:
        response = await client.post('/fixtures/nhl:2026020106/evidence', json=body)
        assert response.status_code == 200, response.text
        assert response.json()['probability'] is None and response.json()['metrics']['factors'] == {}
        assert (await client.post('/fixtures/nhl:2026020106/evidence', json={**body, 'factors': {'expected_goals': .2}})).status_code == 422
        assert (await client.post('/fixtures/nhl:2026020106/evidence', json={**body, 'away_goalie': None})).status_code == 422
    async with database() as session:
        assert await session.scalar(select(func.count()).select_from(Evidence).where(Evidence.kind == 'model_factors')) == 0
    monkeypatch.setattr('main.now', lambda: START - timedelta(minutes=20))
    body['source_at'] = (START - timedelta(minutes=20)).isoformat()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', headers=HEADERS) as client:
        assert (await client.post('/fixtures/nhl:2026020106/evidence', json=body)).status_code == 200
        factors = {k: 0 for k in ('goalie_personnel', 'expected_goals', 'rest_fatigue', 'venue_special_teams')}
        assert (await client.post('/fixtures/nhl:2026020106/evidence', json={**body, 'factors': factors})).status_code == 409


async def test_ingestion_saves_both_histories_despite_preseason_split_squads(database, monkeypatch):
    monkeypatch.setattr('app.ingestion.now', lambda: AT)
    game = {'id': 2026020106, 'startTimeUTC': START.isoformat(), 'season': 20262027, 'gameType': 2,
            'homeTeam': {'abbrev': 'WSH', 'placeName': 'Washington', 'commonName': 'Capitals'},
            'awayTeam': {'abbrev': 'MTL', 'placeName': 'Montréal', 'commonName': 'Canadiens'}}
    async def schedule():return [game]
    async def standings():return [{'teamAbbrev': code, 'teamName': code, 'gamesPlayed': 6, 'pointPctg': .5} for code in ('WSH', 'MTL')]
    async def games(code, season):return history(code) + [raw(91, 20, 1, code), raw(92, 20, 1, code)]
    monkeypatch.setattr('app.providers.nhl_schedule', schedule)
    monkeypatch.setattr('app.providers.nhl_standings', standings)
    monkeypatch.setattr('app.providers.nhl_history', games)
    await ingest_nhl(history=True)
    async with database() as session:
        row = await session.scalar(select(Evidence).where(Evidence.kind == 'history'))
        assert row and row.payload['contract'] == HISTORY_CONTRACT
        assert len(row.payload['home']) == len(row.payload['away']) == 6
        assert aware(row.payload['away'][0]['started_at']).date() == START.date() - timedelta(days=1)
