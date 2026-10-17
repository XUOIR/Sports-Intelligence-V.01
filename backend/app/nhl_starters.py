"""Saved-data goalie previews. Estimates never supply confirmation evidence."""
from datetime import timedelta
import hashlib
import json
from .clock import aware, now

MANUAL_CONTRACT = 'nhl-manual-starters-v1'


def selection_options(fixture, statistics, at):
    """Identified team candidates from saved reads; no roster/availability claim."""
    saved = fixture.metrics.get('nhl_goalie_comparison', {})
    try:
        fresh = timedelta(0) <= at-aware(saved['observed_at']) <= timedelta(hours=2)
    except (KeyError, TypeError, ValueError):
        fresh = False
    try:
        stats_fresh = ((statistics or {}).get('status') == 'available'
            and timedelta(0) <= at-aware(statistics['observed_at']) <= timedelta(hours=26))
    except (KeyError, TypeError, ValueError):
        stats_fresh = False
    sides = {}
    times = []
    for side in ('home', 'away'):
        rows = {}
        if stats_fresh:
            for goalie in statistics.get('sides', {}).get(side, {}).get('goalies', []):
                if fixture.metrics.get(side+'_abbrev') and goalie.get('latest_team') == fixture.metrics.get(side+'_abbrev'):
                    rows[goalie['player_id']] = {'player_id': goalie['player_id'], 'name': goalie['name'],
                        'candidate_source': 'saved_team_history'}
            times.append(statistics['observed_at'])
        if fresh:
            for goalie in saved.get('sides', {}).get(side, []):
                rows[goalie['player_id']] = {'player_id': goalie['player_id'], 'name': goalie['name'],
                    'candidate_source': 'nhl_comparison'}
            times.append(saved['observed_at'])
        sides[side] = sorted((row for row in rows.values()
            if isinstance(row['player_id'], str) and len(row['player_id']) == 7 and row['player_id'].isdigit()
            and isinstance(row['name'], str) and 2 <= len(row['name']) <= 100), key=lambda row: row['name'])
    identity = {'fixture_id': fixture.id, 'start_at': aware(fixture.commence_time).isoformat(),
                'sides': sides, 'observed_at': sorted(set(times))}
    version = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'version': version, 'sides': sides, 'observed_at': max(times, key=aware) if times else None}


def comparison(payload, fixture, at):
    """Retain only identified candidates from the already-admitted landing read."""
    try:
        if str(payload['id']) != fixture.id.split(':', 1)[1]:
            return None
        result = {'observed_at': aware(at).isoformat(), 'sides': {}}
        for side in ('home', 'away'):
            if payload[side+'Team']['abbrev'] != fixture.metrics.get(side+'_abbrev'):
                return None
            leaders = payload['matchup']['goalieComparison'][side+'Team']['leaders']
            if not isinstance(leaders, list) or not 1 <= len(leaders) <= 6:
                return None
            candidates = []
            for row in leaders:
                identifier, played = row['playerId'], row['gamesPlayed']
                name = ' '.join(row[key]['default'].strip() for key in ('firstName', 'lastName'))
                if (type(identifier) is not int or not 1_000_000 <= identifier <= 9_999_999
                        or type(played) is not int or not 0 <= played <= 100 or not 2 <= len(name) <= 100):
                    return None
                candidates.append({'player_id': str(identifier), 'name': name, 'season_appearances': played})
            if len({c['player_id'] for c in candidates}) != len(candidates):
                return None
            result['sides'][side] = candidates
        return result
    except (KeyError, TypeError, AttributeError):
        return None


def preview(fixture, statistics, at=None):
    at = aware(at or now())
    saved = fixture.metrics.get('nhl_goalie_comparison', {})
    try:
        fresh = timedelta(0) <= at-aware(saved['observed_at']) <= timedelta(hours=2)
    except (KeyError, TypeError, ValueError):
        fresh = False
    confirmation = fixture.metrics.get('goalie_confirmations', {})
    try:
        confirmed = (fixture.metrics.get('personnel_confirmed') is True
            and timedelta(0) <= at-aware(fixture.metrics['confirmed_at']) <= timedelta(minutes=30))
    except (KeyError, TypeError, ValueError):
        confirmed = False
    sides = {}
    for side in ('home', 'away'):
        histories = (statistics or {}).get('sides', {}).get(side, {}).get('goalies', [])
        candidates = []
        for row in saved.get('sides', {}).get(side, []) if fresh else []:
            candidate = dict(row)
            history = next((g for g in histories if g['player_id'] == row['player_id']), {})
            candidate['latest_appearance'] = history.get('latest_game_date')
            candidate['recent_appearances'] = history.get('sample_games')
            candidates.append(candidate)
        ranked = sorted(candidates, key=lambda c: c['season_appearances'], reverse=True)
        pick = None
        reason = 'Awaiting a recent official goalie comparison; availability is not established by game history.'
        if len(ranked) >= 2:
            lead, backup = ranked[:2]
            # A modest workload rule, without a fabricated probability of starting.
            # Do not call a tie or missing last-appearance date a useful estimate.
            if (statistics or {}).get('status') == 'available' and all(c['latest_appearance'] for c in (lead, backup)):
                try:
                    rest = [(aware(fixture.commence_time).date()-aware_date(c['latest_appearance'])).days-1 for c in (lead, backup)]
                except (ValueError,TypeError):
                    rest = [-1,-1]
                if rest[0] == 0 and rest[1] >= 1:
                    pick = backup
                    reason = 'Workload estimate: the more-used goalie appeared yesterday; this candidate has more rest.'
                elif rest[0] >= 1 and lead['season_appearances']-backup['season_appearances'] >= 2:
                    pick = lead
                    reason = 'Workload estimate: clear season appearance lead and at least one full rest day.'
                else:
                    reason = 'Workload and rest do not distinguish a clear starter; confirmation is needed.'
            else:
                reason = 'Current appearance history is incomplete; no workload projection is made.'
        name = confirmation.get(side) if confirmed else None
        sides[side] = {'status': 'confirmed' if isinstance(name, str) and name else 'projected' if pick else 'unknown',
            'confirmed_name': name if isinstance(name, str) else None,
            'projected_name': pick['name'] if pick else None, 'candidates': candidates, 'reason': reason,
            'confirmed_at': fixture.metrics.get('confirmed_at') if confirmed else None,
            'reported_at': fixture.metrics.get('starter_reported_at') if confirmed else None,
            'source_url': fixture.metrics.get('starter_source_url', fixture.metrics.get('source_reference')) if confirmed else None,
            'confirmation_method': fixture.metrics.get('starter_confirmation_method', 'public_source') if confirmed else None,
            'confirmed_player_id': fixture.metrics.get('goalie_confirmation_ids', {}).get(side) if confirmed else None}
    return {'contract': 'nhl-workload-preview-v1', 'sides': sides,'checked_at':at.isoformat(),
        'selection': selection_options(fixture, statistics, at),
        'projection_valid_until':(aware(saved['observed_at'])+timedelta(hours=2)).isoformat() if fresh else None,
        'note': 'Choose one known team goalie per side, then confirm that they are today’s starters. Manual confirmations are your attestation, not an independent news report. Candidate lists and workload projections do not establish availability.',
        'paid_credits': 0, 'grants_verification': False}


def aware_date(value):
    from datetime import date
    return date.fromisoformat(value)
