"""Regular-season NHL history without invented game-ending timestamps."""
from datetime import timedelta
from .clock import aware

HISTORY_CONTRACT = 'nhl-completed-games-v2'


def completed_games(rows, abbreviation, season, observed_at, start):
    """Accept prior Pacific dates whose final scores were actually observed.

    The club schedule does not provide an end time. Its final state establishes
    completion before the cache observation, not a fabricated midnight finish.
    Preseason split-squad games must never enter regular-season form or rest.
    """
    observed, upcoming = aware(observed_at), aware(start)
    anchor = upcoming - timedelta(minutes=30)
    if observed > anchor:
        return []
    selected = {}
    for row in rows:
        try:
            if row.get('gameType') != 2 or row.get('season') != season or row.get('gameState') not in {'OFF', 'FINAL'}:
                continue
            home, away = row['homeTeam'], row['awayTeam']
            if home['abbrev'] == away['abbrev'] or abbreviation not in {home['abbrev'], away['abbrev']}:
                continue
            h, a = home['score'], away['score']
            if type(h) is not int or type(a) is not int or not 0 <= h <= 30 or not 0 <= a <= 30 or h == a:
                continue
            try:
                began = aware(row['startTimeUTC'])
            except (ValueError, AttributeError):
                continue
            if began >= observed or began.date() >= upcoming.date():
                continue
            identifier = str(row['id'])
            if not identifier.isdigit() or len(identifier) != 10:
                continue
            game = {'contract': HISTORY_CONTRACT, 'game_id': identifier, 'game_type': 2, 'season': season,
                    'started_at': began.isoformat(), 'completion_observed_at': observed.isoformat(),
                    'win': (h > a) if home['abbrev'] == abbreviation else (a > h)}
            if identifier in selected and selected[identifier] != game:
                raise ValueError('Conflicting NHL final results')
            selected[identifier] = game
        except (KeyError, TypeError, AttributeError):
            continue
    games = sorted(selected.values(), key=lambda g: aware(g['started_at']), reverse=True)
    if len({g['started_at'] for g in games}) != len(games):
        raise ValueError('Conflicting regular-season NHL starts')
    return games[:10]
