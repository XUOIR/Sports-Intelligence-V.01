"""One complete official season cache for paper inputs, using the NHL budget.

At most two admitted batches per Pacific day, at least six hours apart, with
one successful refresh per Eastern date. No keys, paid data, or browser fetch.
"""
from datetime import timedelta
import hashlib
import json
from zoneinfo import ZoneInfo
from sqlalchemy import select
from . import db
from .clock import now, aware
from .http import http, ProviderError
from .limits import limits
from .models import ProviderState, PaperInputArchive
from sqlalchemy.dialects.postgresql import insert

EASTERN = ZoneInfo('America/New_York')
KEY = 'nhl-paper-history'


def season_at(day):
    return day.year if day.month >= 7 else day.year - 1


def normalize(payload, season, day, teams):
    if (not isinstance(payload, dict) or not isinstance(payload.get('data'), list)
            or type(payload.get('total')) is not int or payload['total'] != len(payload['data'])
            or not 1 <= payload['total'] <= 1600):
        raise ValueError('Complete regular-season pagination required')
    seen, result = set(), []
    for row in payload['data']:
        gid = row.get('id')
        if (type(gid) is not int or str(gid)[:6] != f'{season}02' or len(str(gid)) != 10
                or gid in seen or row.get('gameType') != 2 or row.get('season') != season * 10000 + season + 1
                or str(row.get('homeTeamId')) not in teams or str(row.get('visitingTeamId')) not in teams
                or row['homeTeamId'] == row['visitingTeamId']):
            raise ValueError('Official season identity changed')
        seen.add(gid)
        date_string = row['gameDate']
        from datetime import date
        game_day = date.fromisoformat(date_string)
        if not date(season, 7, 1) <= game_day < date(season + 1, 7, 1):
            raise ValueError('Official game date outside season')
        if row.get('easternStartTime', date_string)[:10] != date_string:
            raise ValueError('Official start and calendar date disagree')
        if game_day >= day:
            continue  # Same-day results never influence this model's inputs.
        if row.get('gameScheduleStateId') != 1:
            raise ValueError('Nonstandard previous-day schedule state requires source review')
        if row.get('gameStateId') != 7:
            raise ValueError('A previous-day game remains unresolved; inputs incomplete')
        h, a = row.get('homeScore'), row.get('visitingScore')
        if (type(h) is not int or type(a) is not int or h == a or not 0 <= min(h, a) <= max(h, a) <= 30
                or row.get('period') not in (3, 4, 5)):
            raise ValueError('Official final score invalid')
        if row['period'] > 3 and abs(h - a) != 1:
            raise ValueError('Official overtime/shootout score invalid')
        result.append({'id': gid, 'date': date_string, 'season': season, 'home': row['homeTeamId'],
                       'away': row['visitingTeamId'], 'home_win': int(h > a)})
    return sorted(result, key=lambda g: (g['date'], g['id']))


async def refresh(bundle):
    at = now()
    day = at.astimezone(EASTERN).date()
    # Warmups and an overnight game cannot cause a partially completed date to
    # become model history. Wait until 06:00 ET before the daily batch.
    if at.astimezone(EASTERN).hour < 6:
        return
    async with db.Session() as session:
        cached = await session.get(ProviderState, KEY)
        if cached and cached.info.get('as_of_date') == str(day):
            return
    if not await limits.lease('nhl-paper-history-attempt', 6 * 3600):
        return
    async with db.Session.begin() as session:
        await limits._increment(session, f'paper-history:{at.date()}', 1, 2)
    season = season_at(day)
    payload = await http.request('nhl', 'GET', 'https://api.nhle.com/stats/rest/en/game',
        params={'cayenneExp': f'season={season * 10000 + season + 1} and gameType=2', 'limit': 1600, 'start': 0})
    games = normalize(payload, season, day, bundle['teams'])
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    info = {'as_of_date': str(day), 'season': season, 'games': games,
        'source_sha256': digest, 'source': 'https://api.nhle.com/stats/rest/en/game',
        'observed_at': now().isoformat(), 'total_scheduled': payload['total'], 'completed_prior_date': len(games)}
    archive_hash = hashlib.sha256(json.dumps({k: v for k, v in info.items() if k != 'observed_at'},
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    # The changing shared cache is not provenance. Keep one immutable normalized
    # input archive per date/content instead of copying an entire season per game.
    async with db.Session.begin() as session:
        await session.execute(insert(PaperInputArchive).values(sha256=archive_hash, observed_at=now(), data=info)
                              .on_conflict_do_nothing())
    await limits.observe(KEY, {**info, 'archive_sha256': archive_hash})
    await limits.observe('nhl-paper-history-error', {'error': None})


def admitted(cached, day, at):
    if (not cached or cached.info.get('as_of_date') != str(day)
            or aware(cached.observed_at) > at or at - aware(cached.observed_at) > timedelta(hours=30)):
        raise ValueError('Today’s complete official history is not cached yet')
    return cached.info
