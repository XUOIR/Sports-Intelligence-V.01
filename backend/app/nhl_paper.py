"""Forward paper collection from cached data. Never calls odds or AI providers.

All forecasts, failed eligibility checks and price observations use real server
times. Only official *prior-date* results update ratings; no invented starters.
"""
from datetime import timedelta
from decimal import Decimal
import hashlib
import json
import logging
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from . import db
from .clock import now, aware
from .config import settings
from .limits import limits
from .models import Fixture, PaperForecast, PaperPriceObservation, ProviderState, PaperInputArchive
from .market_display import latest_quotes
from .nhl_paper_model import load_bundle, advance, features, probability, canonical
from . import nhl_paper_history as history

log = logging.getLogger('paper')


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def version(digest):
    return 'nhl-team-paper-v2-' + digest[:12]


def quote_observation(fixture, quotes, p, at):
    """Two sides from the same book and source time; never mix markets/books."""
    relevant = [q for q in quotes if q.bookmaker in {'playnow', 'bclc'} and q.market == 'h2h' and q.line is None]
    saved = [{'id': q.id, 'bookmaker': q.bookmaker, 'selection': q.selection, 'odds': str(q.decimal_odds),
              'source_at': aware(q.source_at).isoformat(), 'saved_at': aware(q.created_at).isoformat()}
             for q in relevant]
    data = {'quotes': saved, 'market': 'h2h_final_including_ot_so'}
    paired = []
    for book in ('playnow', 'bclc'):
        rows = [q for q in relevant if q.bookmaker == book]
        h, a = [[q for q in rows if q.selection == name] for name in (fixture.home, fixture.away)]
        if len(h) == len(a) == 1 and aware(h[0].source_at) == aware(a[0].source_at):
            paired.append((h[0], a[0]))
    if not paired:
        return 'MISSING_MATCHED_PRICES', data
    h, a = max(paired, key=lambda pair: aware(pair[0].source_at))
    if any(aware(q.source_at) > at or aware(q.created_at) > at for q in (h, a)):
        return 'FUTURE_PRICE_REJECTED', data
    if any(at - aware(q.source_at) > timedelta(minutes=5) for q in (h, a)):
        return 'STALE_PRICES', data
    oh, oa = Decimal(h.decimal_odds), Decimal(a.decimal_odds)
    if not oh.is_finite() or not oa.is_finite() or min(oh, oa) <= 1:
        return 'INVALID_PRICES', data
    ph, pa = 1 / oh, 1 / oa
    edge_h, edge_a = p - ph, 1 - p - pa
    data.update(home_odds=str(oh), away_odds=str(oa), home_break_even=str(ph), away_break_even=str(pa),
                home_edge=str(edge_h), away_edge=str(edge_a), market_home_probability=str(ph / (ph + pa)),
                bookmaker=h.bookmaker, source_at=aware(h.source_at).isoformat())
    if max(edge_h, edge_a) >= Decimal('.03'):
        home = edge_h >= edge_a
        data['qualifies'] = {'selection': fixture.home if home else fixture.away, 'home': home,
            'odds': str(oh if home else oa), 'edge': str(edge_h if home else edge_a), 'units': '1',
            'source_at': data['source_at'], 'bookmaker': h.bookmaker}
    return 'VALID', data


def forecast(bundle, fixture, cached, at):
    start = aware(fixture.commence_time)
    day = start.astimezone(history.EASTERN).date()
    today = at.astimezone(history.EASTERN).date()
    if start <= at or fixture.metrics.get('nhl_game_type') != 2:
        raise ValueError('Only future regular-season fixtures are eligible')
    if day != today:
        raise ValueError('Awaiting match day so previous-day results can be included')
    info = history.admitted(cached, today, at)
    if history.season_at(day) != info['season'] or info['season'] != bundle['seed']['season'] + 1:
        raise ValueError('Paper season does not follow the frozen training history')
    if any(g['date'] >= str(today) or g['season'] != info['season'] for g in info['games']):
        raise ValueError('Same-day or future results cannot supply pregame inputs')
    teams = {}
    for side in ('home', 'away'):
        code = fixture.metrics.get(side + '_abbrev')
        candidates = {canonical(i) for i, t in bundle['teams'].items() if t['code'] == code}
        if len(candidates) != 1:
            raise ValueError('Official team identity missing or ambiguous')
        teams[side] = candidates.pop()
    state = advance(bundle['seed'], info['games'])
    vector = features(state, teams['home'], teams['away'], str(day), info['season'])
    if max(t['last_day'] for k, t in state['teams'].items() if int(k) in teams.values()) >= str(today):
        raise ValueError('Input result date is not strictly before today')
    return Decimal(str(probability(bundle, vector))), {
        'features': vector, 'feature_names': bundle['features'], 'team_ids': teams,
        'history_sha256': info['source_sha256'], 'history_observed_at': info['observed_at'],
        'input_archive_sha256': info.get('archive_sha256'),
        'history_as_of_date': info['as_of_date'], 'seed_through': bundle['seed']['through'],
        'latest_result_date': state['through'], 'market': 'h2h_final_including_ot_so',
        'lineup_policy': 'Team-only: expected/unconfirmed permitted; no goalie adjustment',
        'goalie_context': {k: fixture.metrics.get(k) for k in ('personnel_confirmed', 'confirmed_at', 'goalie_confirmations')},
        'approved_for_wagers': False}


async def collect(bundle=None, digest=None):
    if 'NHL' not in settings.active_sports:
        return
    if bundle is None:
        bundle, digest = load_bundle()
    model_version = version(digest)
    # A short global lease limits database work. The row lock and unique keys
    # additionally enforce one forecast/position across overlapping instances.
    if not await limits.lease('nhl-paper-collect', 50):
        return
    at = now()
    counts = {'captured': 0, 'blocked': 0, 'new_positions': 0}
    async with db.Session() as session:
        ids = list((await session.scalars(select(Fixture.id).where(Fixture.sport == 'NHL',
            Fixture.commence_time > at, Fixture.commence_time <= at + timedelta(hours=48)).limit(100))).all())
    for fid in ids:
        async with db.Session.begin() as session:
            fixture = await session.get(Fixture, fid, with_for_update=True)
            at = now()
            if aware(fixture.commence_time) <= at:
                continue
            if (not fid.startswith('nhl:') or not fid[4:].isdigit() or len(fid[4:]) != 10
                    or fid[8:10] != '02' or fixture.metrics.get('nhl_game_type') != 2):
                continue
            await session.execute(insert(PaperForecast).values(fixture_id=fid, model_version=model_version,
                first_seen_at=at, start_at=fixture.commence_time, home=fixture.home, away=fixture.away, inputs={})
                .on_conflict_do_nothing(index_elements=['fixture_id', 'model_version']))
            row = await session.scalar(select(PaperForecast).where(PaperForecast.fixture_id == fid,
                PaperForecast.model_version == model_version).with_for_update())
            if row.resolution or aware(row.start_at) != aware(fixture.commence_time):
                continue
            if row.captured_at is None:
                try:
                    # Check the cheap calendar condition before fetching a full
                    # season cache/archive. Future fixtures are revisited each
                    # minute; transferring that history for them wastes DB egress.
                    if aware(fixture.commence_time).astimezone(history.EASTERN).date() != at.astimezone(history.EASTERN).date():
                        raise ValueError('Awaiting match day so previous-day results can be included')
                    cached = await session.get(ProviderState, history.KEY)
                    if cached:
                        archive = await session.get(PaperInputArchive, cached.info.get('archive_sha256') or '')
                        if archive is None:
                            raise ValueError('Immutable official input archive is missing')
                        normalized = lambda value: {k: v for k, v in value.items() if k not in {'archive_sha256', 'observed_at'}}
                        if normalized(archive.data) != normalized(cached.info):
                            raise ValueError('Cached inputs disagree with their immutable archive')
                    p, inputs = forecast(bundle, fixture, cached, at)
                    captured_at = now()
                    if captured_at >= aware(fixture.commence_time):
                        row.issue = 'Game started before forecast capture completed'
                        continue
                    row.home_probability = p.quantize(Decimal('.0000000001'))
                    row.inputs = {**inputs, 'model_sha256': digest}
                    row.captured_at = captured_at
                    row.issue = None
                    counts['captured'] += 1
                except (ValueError, KeyError, TypeError) as exc:
                    row.issue = str(exc)[:500]
                    counts['blocked'] += 1
                    continue
            quotes = (await latest_quotes(session, [fid])).get(fid, [])
            at = now()
            if at >= aware(fixture.commence_time):
                continue
            status, observation = quote_observation(fixture, quotes, Decimal(row.home_probability), at)
            key = identity({'status': status, 'quotes': observation['quotes']})
            inserted = await session.execute(insert(PaperPriceObservation).values(forecast_id=row.id,
                identity=key, observed_at=at, status=status, data=observation).on_conflict_do_nothing()
                .returning(PaperPriceObservation.id))
            oid = inserted.scalar_one_or_none()
            if oid and status == 'VALID' and observation.get('qualifies') and row.position is None:
                row.position = {**observation['qualifies'], 'observed_at': at.isoformat(), 'observation_id': oid}
                counts['new_positions'] += 1
    await limits.observe('nhl-paper-collection', {**counts, 'model_version': model_version, 'error': None})


async def settle():
    """Use already reconciled official results; no additional upstream calls."""
    from .ingestion import cached_result
    async with db.Session.begin() as session:
        rows = (await session.scalars(select(PaperForecast).where(PaperForecast.resolution.is_(None))
            .order_by(PaperForecast.start_at).limit(500).with_for_update())).all()
        for row in rows:
            fixture = await session.get(Fixture, row.fixture_id)
            if not fixture:
                continue
            if aware(fixture.commence_time) != aware(row.start_at) or fixture.home != row.home or fixture.away != row.away:
                row.resolution, row.result_source = 'VOID', {'reason': 'Official fixture identity or start changed'}
            elif fixture.final_home_win is not None and aware(row.start_at) < now():
                row.result_home_win = fixture.final_home_win
                row.resolution, row.result_source = 'FINAL', {'source': 'Official result reconciled by NHL ingestion'}
            else:
                cached = await session.get(ProviderState, f'nhl-score:{aware(row.start_at).date()}')
                result = cached_result(cached, fixture)
                if result:
                    row.result_home_win, row.result_source = result
                    row.resolution = 'FINAL'
                for game in cached.info.get('games', []) if not result and cached and aware(cached.observed_at) <= now() else []:
                    if (game['id'] == row.fixture_id and aware(game['commence_time']) == aware(row.start_at)
                            and game.get('schedule_state') in {'CNCL', 'PPD'}):
                        row.resolution, row.result_source = 'VOID', {
                            'source': 'Official NHL score cache', 'schedule_state': game['schedule_state'],
                            'observed_at': aware(cached.observed_at).isoformat()}
            if row.resolution:
                row.settled_at = now()


async def cycle():
    bundle, digest = load_bundle()
    try:
        await history.refresh(bundle)
    except Exception as exc:
        # Retain immutable observations and allow settlement even when the free
        # source fails. Error categories never expose request URLs or secrets.
        log.warning('Paper history unavailable (%s)', type(exc).__name__)
        await limits.observe('nhl-paper-history-error', {'error': type(exc).__name__, 'at': now().isoformat()})
    await settle()
    await collect(bundle, digest)


async def summary(session):
    bundle, digest = load_bundle()
    model_version = version(digest)
    rows = (await session.scalars(select(PaperForecast).where(PaperForecast.model_version == model_version)
                                 .order_by(PaperForecast.first_seen_at, PaperForecast.id))).all()
    observations = (await session.scalars(select(PaperPriceObservation).join(PaperForecast)
        .where(PaperForecast.model_version == model_version).order_by(PaperPriceObservation.id))).all()
    first_prices = {}
    for obs in observations:
        if obs.status == 'VALID':
            first_prices.setdefault(obs.forecast_id, obs)
    captured = [r for r in rows if r.captured_at]
    resolved = [r for r in captured if r.resolution == 'FINAL']
    paired = [r for r in resolved if r.id in first_prices]
    positions = [r for r in rows if r.position]
    settled_positions = [r for r in positions if r.resolution == 'FINAL']
    net = sum((Decimal(r.position['odds']) - 1 if bool(r.result_home_win) == r.position['home'] else Decimal(-1))
              for r in settled_positions)
    brier = lambda group, prediction: (str(sum((prediction(r) - int(r.result_home_win)) ** 2 for r in group) / len(group))
                                        if group else None)
    def row_data(row):
        position = row.position
        price = first_prices.get(row.id)
        return {'fixture_id': row.fixture_id, 'home': row.home, 'away': row.away,
            'start_at': aware(row.start_at).isoformat(), 'captured_at': aware(row.captured_at).isoformat() if row.captured_at else None,
            'home_probability': str(row.home_probability) if row.home_probability is not None else None,
            'issue': row.issue, 'position': position, 'resolution': row.resolution,
            'result_home_win': row.result_home_win, 'prices': price.data if price else None}
    state = await session.get(ProviderState, 'nhl-paper-collection')
    error = await session.get(ProviderState, 'nhl-paper-history-error')
    return {'mode': 'paper_only', 'approved_for_wagers': False, 'model_version': model_version,
        'model_sha256': digest, 'model_created_at': bundle['created_at'], 'collection_rules': bundle['collection'],
        'fixtures_seen': len(rows), 'forecasts': len(captured), 'blocked': len(rows) - len(captured),
        'resolved': len(resolved), 'matched_prices': len(first_prices), 'resolved_pairs': len(paired),
        'positions': len(positions), 'settled_positions': len(settled_positions),
        'void_positions': sum(r.resolution == 'VOID' for r in positions),
        'profit_units': str(net), 'roi_percent': str(net / len(settled_positions) * 100) if settled_positions else None,
        'brier': brier(resolved, lambda r: r.home_probability),
        'paired_model_brier': brier(paired, lambda r: r.home_probability),
        'paired_market_brier': brier(paired, lambda r: Decimal(first_prices[r.id].data['market_home_probability'])),
        'last_collection_at': aware(state.observed_at).isoformat() if state else None,
        'history_error': error.info.get('error') if error else None,
        'records': [row_data(r) for r in reversed(rows[-200:])],
        'note': 'Forward paper research. One simulated unit; no bankroll changes. No demonstrated sportsbook edge.'}
