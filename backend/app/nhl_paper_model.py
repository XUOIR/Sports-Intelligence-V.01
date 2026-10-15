"""Team-only paper inference. Standard library only; no providers or bankroll.

The v1 experiment is frozen. This separate contract preserves Utah's official
franchise continuity and can forecast a fixture without supplying its outcome.
"""
from copy import deepcopy
from datetime import date
import hashlib
import json
import math
from pathlib import Path

CONTRACT = 'nhl-team-paper-v2'
FEATURES = ['rating_difference', 'rest_difference', 'back_to_back_difference']
BUNDLE = Path(__file__).with_name('data') / 'nhl-paper-v2.json'


def canonical(team):
    # Official team reference: both are franchise 40. Arizona (franchise 28)
    # is deliberately NOT merged into Utah. All other official IDs stay intact.
    return 59 if int(team) == 68 else int(team)


def blank_state():
    return {'season': None, 'through': None, 'teams': {}}


def season_state(state, season):
    if type(season) is not int or not 2015 <= season <= 2100:
        raise ValueError('Invalid NHL season')
    previous = state['season']
    if previous is not None and season < previous:
        raise ValueError('Cannot move team state backwards')
    if previous != season:
        if previous is not None:
            for team in state['teams'].values():
                team['rating'] = 1500 + .75 ** (season - previous) * (team['rating'] - 1500)
        state['season'] = season


def team_state(state, team):
    key = str(canonical(team))
    return state['teams'].setdefault(key, {'rating': 1500., 'games': 0, 'last_day': None})


def features(state, home, away, day, season):
    if canonical(home) == canonical(away):
        raise ValueError('A team cannot play itself')
    day = date.fromisoformat(day)
    season_state(state, season)
    teams = [team_state(state, t) for t in (home, away)]
    if min(t['games'] for t in teams) < 10:
        raise ValueError('Fewer than ten prior games for a team')
    last = [date.fromisoformat(t['last_day']) for t in teams]
    if max(last) >= day:
        raise ValueError('Same-day or future results cannot supply pregame inputs')
    rests = [min(4, max(0, (day - d).days - 1)) for d in last]
    return [(teams[0]['rating'] - teams[1]['rating']) / 400,
            rests[0] - rests[1], int(rests[0] == 0) - int(rests[1] == 0)]


def apply_day(state, games):
    if not games:
        return
    if len({(g['date'], g['season']) for g in games}) != 1:
        raise ValueError('One completed calendar date required')
    day = games[0]['date']
    date.fromisoformat(day)
    if state['through'] and day <= state['through']:
        raise ValueError('Results must advance the frozen state')
    season_state(state, games[0]['season'])
    seen, updates = set(), []
    for game in games:
        home, away = canonical(game['home']), canonical(game['away'])
        if home == away or home in seen or away in seen:
            raise ValueError('Conflicting team identities on a date')
        if type(game['home_win']) is not int or game['home_win'] not in (0, 1):
            raise ValueError('An official final winner is required')
        seen.update((home, away))
        h, a = team_state(state, home), team_state(state, away)
        p = 1 / (1 + 10 ** (-(h['rating'] - a['rating'] + 35) / 400))
        updates.append((h, a, 10 * (game['home_win'] - p)))
    for h, a, change in updates:
        h['rating'] += change
        a['rating'] -= change
        for team in (h, a):
            team['games'] += 1
            team['last_day'] = day
    state['through'] = day


def advance(state, games):
    from itertools import groupby
    result = deepcopy(state)
    for _, rows in groupby(sorted(games, key=lambda g: (g['date'], g['id'])), key=lambda g: g['date']):
        apply_day(result, list(rows))
    return result


def sigmoid(value):
    return 1 / (1 + math.exp(-max(-35., min(35., value))))


def probability(bundle, vector):
    if len(vector) != 3 or any(not math.isfinite(v) for v in vector):
        raise ValueError('Invalid team inputs')
    fit = bundle['fit']
    raw = fit['coefficients'][0] + sum(
        (x - center) / scale * coefficient
        for x, center, scale, coefficient in zip(vector, fit['center'], fit['scale'], fit['coefficients'][1:]))
    return sigmoid(bundle['calibration']['coefficients'][0] + bundle['calibration']['coefficients'][1] * max(-35., min(35., raw)))


def load_bundle():
    raw = BUNDLE.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != BUNDLE.with_suffix('.sha256').read_text().strip():
        raise ValueError('Paper model integrity check failed')
    bundle = json.loads(raw)
    if (bundle['contract'] != CONTRACT or bundle['features'] != FEATURES
            or bundle['mode'] != 'paper_only' or bundle['approved_for_wagers'] is not False):
        raise ValueError('Incompatible paper model contract')
    expected = {'nhl_paper_model.py', 'nhl_paper_history.py', 'nhl_paper.py'}
    if set(bundle.get('inference_code_sha256', {})) != expected:
        raise ValueError('Paper inference implementation is not frozen')
    for filename, frozen_hash in bundle['inference_code_sha256'].items():
        # Normalize checkout line endings so the same Windows/Linux source has
        # the same identity. Any substantive logic change needs a new cohort.
        source = Path(__file__).with_name(filename).read_text(encoding='utf-8').replace('\r\n', '\n')
        if hashlib.sha256(source.encode()).hexdigest() != frozen_hash:
            raise ValueError('Paper inference changed; freeze a new candidate before collection')
    return bundle, digest
