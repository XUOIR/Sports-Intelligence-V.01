"""Explain NHL evidence readiness using saved data only; never grant gates."""
from datetime import timedelta
from sqlalchemy import select
from .clock import now, aware
from .features import SOURCE_MAX_AGE, frozen_vector
from .models import Evidence, ModelValidation
from .model_config import MIN_EDGE
from .readiness import validated_model, matching_nhl_starters
from .nhl_history import HISTORY_CONTRACT


def current_timestamp(value, at, lifetime):
    try:
        return timedelta(0) <= at - aware(value) <= lifetime
    except (ValueError, TypeError, AttributeError):
        return False


def price_pair(quotes, fixture, at):
    pairs,latest = {},{}
    for quote in quotes:
        if (quote.bookmaker in {'playnow', 'bclc'} and quote.market == 'h2h' and quote.line is None
                and quote.selection in {fixture.home, fixture.away} and quote.decimal_odds > 1):
            key=(quote.bookmaker,quote.selection)
            if key not in latest or aware(quote.source_at)>aware(latest[key].source_at):latest[key]=quote
    for quote in latest.values():
        if aware(quote.source_at)<=at:
            pairs.setdefault((quote.bookmaker,aware(quote.source_at)),{})[quote.selection]=quote
    complete = [(stamp, prices) for (_, stamp), prices in pairs.items() if len(prices) == 2]
    return max(complete, key=lambda row: row[0], default=None)


async def detail(session, fixture, snapshot, quotes, statistics):
    if fixture.sport != 'NHL':
        return None
    at, start = now(), aware(fixture.commence_time)
    anchor = start - timedelta(minutes=30)
    pending_anchor = at < anchor
    snapshot_ok = bool(snapshot and aware(snapshot.anchor_at) == anchor
        and timedelta(0) <= aware(snapshot.collected_at) - anchor <= timedelta(seconds=5)
        and len(snapshot.vector) == 15)
    phase = 'waiting_for_anchor' if pending_anchor else 'frozen' if snapshot_ok else 'anchor_missing'
    if start <= at:
        phase = 'game_started'
    inputs, sources = [], {}
    for kind in ('schedule', 'standings', 'history'):
        row = await session.scalar(select(Evidence).where(Evidence.fixture_id == fixture.id, Evidence.kind == kind)
            .order_by(Evidence.observed_at.desc(), Evidence.id.desc()).limit(1))
        fresh = bool(row and current_timestamp(row.source_at, at, SOURCE_MAX_AGE[kind])
                     and current_timestamp(row.observed_at, at, SOURCE_MAX_AGE[kind]))
        legacy = bool(kind=='history' and row and row.payload.get('contract') != HISTORY_CONTRACT)
        if legacy:fresh=False
        sources[kind] = row if fresh else None
        inputs.append({'key': kind, 'label': {'schedule': 'Official schedule', 'standings': 'Season standings', 'history': 'Regular-season form & rest'}[kind],
                       'status': 'available' if fresh else 'needs_refresh' if legacy else 'stale' if row else 'missing',
                       'source': 'NHL public API', 'observed_at': aware(row.observed_at).isoformat() if row else None})
    form, form_error = None, 'Schedule, standings and completed game history are required.'
    if all(sources.values()):
        try:
            if aware(sources['schedule'].payload['start']) != start:
                raise ValueError('Official start changed; evidence needs refreshing.')
            vector = frozen_vector(sources['standings'].payload['home'], sources['standings'].payload['away'], sources['history'].payload, start)
            form = {side: {'sample_games': vector[8 + index], 'win_rate': vector[5 + index],
                           'days_rest': vector[10 + index], 'back_to_back': bool(vector[13 + index])}
                    for index, side in enumerate(('home', 'away'))}
            form_error = ''
        except (ValueError, KeyError, TypeError) as exc:
            form_error = str(exc)[:180]
    if statistics:
        inputs.append({'key': 'advanced', 'label': '5v5 expected goals & goalie GSAx',
                       'status': 'available' if statistics['status'] == 'available' else statistics['status'],
                       'source': 'MoneyPuck.com', 'observed_at': statistics.get('observed_at')})
    pair = price_pair(quotes, fixture, at)
    prices_current = bool(pair and at - pair[0] <= timedelta(minutes=5))
    metrics = fixture.metrics
    personnel = metrics.get('personnel_confirmed') is True and current_timestamp(metrics.get('confirmed_at'), at, timedelta(minutes=30))
    review_current = current_timestamp(metrics.get('confirmed_at'), at, timedelta(minutes=30))
    model = await session.scalar(select(ModelValidation).where(ModelValidation.sport == 'NHL', ModelValidation.approved.is_(True))
        .order_by(ModelValidation.created_at.desc()).limit(1))
    model_ok = validated_model(model, snapshot) if snapshot_ok else validated_model(model)
    starter_pair_ok=matching_nhl_starters(snapshot,metrics) if snapshot_ok else True
    model_ok=model_ok and starter_pair_ok
    inputs.append({'key':'normalized_factors','label':'Reproducible forecast inputs',
        'status':'available' if snapshot_ok and snapshot.baseline_home_probability is not None else 'pending' if pending_anchor else 'missing',
        'source':'Frozen NHL statistics and confirmed starters',
        'observed_at':aware(snapshot.collected_at).isoformat() if snapshot_ok else None})
    active = start > at
    def check(key, label, message, valid=True):
        passed = active and not fixture.dirty and snapshot_ok and valid and fixture.gates.get(key) is True
        return {'key': key, 'label': label, 'status': 'passed' if passed else 'pending' if pending_anchor else 'blocked', 'message': message}
    price_message = ('No complete PlayNow moneyline has been saved.' if not pair else
                     'Saved PlayNow prices are older than five minutes; manual refresh required.' if not prices_current else
                     f'PlayNow prices received. The validated model must exceed break-even by at least {MIN_EDGE * 100:g} percentage points.')
    checks = [check('price', 'PlayNow price & edge', price_message, prices_current and model_ok),
              check('personnel', 'Confirmed starting goalies',
                    'Both starters have a current confirmation source.' if personnel else
                    'The NHL comparison lists goalie candidates, not confirmed starters. Record a current team confirmation.', personnel),
              check('form', 'Form & rest',
                    'Prior completed regular-season games are available. Inputs freeze at T−30.' if form else form_error,
                    form is not None),
              {'key': 'maps_veto', 'label': 'Map veto', 'status': 'not_applicable', 'message': 'This esports check is not applicable to NHL.'},
              check('other_markets', 'Spread & total cross-check',
                    'Matching spread and total prices require a recorded review.', review_current and metrics.get('other_markets_verified') is True),
              check('opposing_case', 'Opposing case',
                    'Record the evidence against the pick. Paid AI can veto only after all factual checks pass.', review_current and metrics.get('opposing_case_verified') is True),
              check('overlap_exposure', 'Bankroll & overlap',
                    'The engine checks duplicate tickets, open exposure and stake size after a price and forecast are available.'),
              check('probability', 'Validated model probability',
                    'Compatible model validation is available.' if model_ok else
                    'The confirmed goalie pairing differs from, or is absent in, the frozen inputs.' if not starter_pair_ok else
                    'No compatible approved NHL model. Raw xG and market-implied odds do not establish a forecast.', model_ok)]
    message = ('Checks run at T−30. Available statistics below do not grant a verified play.' if pending_anchor else
               'The T−30 inputs are frozen. Prices, starters and reviews still need current verification.' if snapshot_ok and active else
               'The exact T−30 snapshot is missing or invalid. This game cannot receive a retrospective verified pick.' if active else
               'The game has started. Saved information is for review; no new pregame recommendation is issued.')
    return {'phase': phase, 'anchor_at': anchor.isoformat(), 'checked_at': at.isoformat(), 'message': message,
            'checks': checks, 'inputs': inputs, 'form': form, 'paid_credits': 0,
            'note': 'Opening this panel reads the database only. It does not refresh odds or call AI.'}
