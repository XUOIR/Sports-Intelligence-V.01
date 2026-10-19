"""Time-limited, shared Daily Faceoff shadow collector. Never sets a play gate."""
import asyncio
from datetime import datetime, time, timedelta
import hashlib
import json
import re
from uuid import uuid4
import zlib

import httpx
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from . import db, nhl_advanced
from .clock import now, aware
from .config import PACIFIC, settings
from .dfo_public import ORIGIN, CONTRACT, MAX_HTML, SourceFormatError, canonical, page_url, parse_page, robots_allowed
from .limits import limits, BudgetExceeded
from .models import ProviderState, RuntimeLimit, Fixture, Evidence, AuditLog

CONTROL = 'nhl-goalie-pilot'
ROBOTS = 'dfo-robots'
INTERVAL = 600
DAILY_REQUESTS = 100
DAILY_BYTES = 12_000_000
MONTHLY_BYTES = 200_000_000
MAX_WIRE = 1_000_000
AGENT = 'GSportsIntelligence/0.1 (bounded private research pilot)'


def active(info, at):
    try:
        return not info.get('paused', True) and at < aware(info['expires_at'])
    except (KeyError, TypeError, ValueError):
        return False


def phase(info, at):
    if not info:
        return 'not_started'
    if not active(info, at):
        return 'paused' if info.get('paused') else 'expired'
    if info.get('halted') or info.get('status') == 'running' and at-aware(info['started_at']) > timedelta(seconds=90):
        return 'halted'
    return 'active'


async def control(action):
    at = now()
    async with db.Session.begin() as session:
        await session.execute(insert(ProviderState).values(provider=CONTROL, observed_at=at, info={}).on_conflict_do_nothing())
        row = await session.get(ProviderState, CONTROL, with_for_update=True)
        info = dict(row.info)
        if action == 'start':
            if info.get('expires_at') and at < aware(info['expires_at']):
                raise BudgetExceeded('The existing pilot is still active; its deadline is not extended')
            info.update(paused=False, halted=False, reason=None, status='waiting', mode='shadow',
                        initial_check_pending=True, expires_at=(at+timedelta(hours=72)).isoformat())
        elif action == 'pause':
            info['paused'] = True
        elif action == 'resume':
            if not info.get('expires_at') or at >= aware(info['expires_at']):
                raise BudgetExceeded('The pilot expired; start a new bounded test')
            info.update(paused=False, halted=False)
            info['initial_check_pending']=True
            if info.get('reason'):
                info['last_failure']={'reason':info['reason'],'at':info.get('failed_at')}
                info['reason']=None
            if info.get('status') == 'failed':
                info['status']='waiting'
            if info.get('status') == 'running':
                if at-aware(info['started_at']) <= timedelta(seconds=90):
                    raise BudgetExceeded('The earlier collection is still in progress')
                info['status'] = 'interrupted'
        elif action != 'check':
            raise ValueError('Unknown pilot control')
        if action == 'check' and phase(info, at) != 'active':
            raise BudgetExceeded('Start or resume the bounded pilot before checking its source')
        row.info, row.observed_at = info, at
        session.add(AuditLog(action='DFO_PILOT_CONTROL', entity_id='DailyFaceoff', details={'action': action, 'mode': 'shadow'}))


async def reserve():
    """Reserve before dispatch; the control lock serializes all tabs/instances."""
    at = now()
    async with db.Session.begin() as session:
        row = await session.get(ProviderState, CONTROL, with_for_update=True)
        info = dict(row.info) if row else {}
        if phase(info, at) != 'active' or info.get('status') == 'running':
            raise BudgetExceeded('Pilot is inactive, halted or an earlier attempt is unfinished')
        if info.get('next_at') and at < aware(info['next_at']):
            raise BudgetExceeded('The shared ten-minute source cooldown is still active')
        robots = await session.get(ProviderState, ROBOTS)
        current_robots = bool(robots and timedelta(0) <= at-aware(robots.observed_at) < timedelta(hours=24)
                              and isinstance(robots.info.get('policy_text'), str))
        if current_robots and not robots_allowed(robots.info['policy_text'].encode(), page_url(at.date())):
            raise BudgetExceeded('Cached source crawler policy does not permit this public page')
        requests = 1 if current_robots else 2
        keys = (f'dfo-requests:{at.date()}', f'dfo-wire-day:{at.date()}', f'dfo-wire-month:{at:%Y-%m}')
        for key, amount, cap in zip(keys, (requests, requests*MAX_WIRE, requests*MAX_WIRE),
                                    (DAILY_REQUESTS, DAILY_BYTES, MONTHLY_BYTES)):
            await limits._increment(session, key, amount, cap)
        attempt = str(uuid4())
        info.update(status='running', initial_check_pending=False, started_at=at.isoformat(),
                    next_at=(at+timedelta(seconds=INTERVAL)).isoformat(), attempt_id=attempt)
        row.info, row.observed_at = info, at
        return {'attempt_id': attempt, 'keys': keys, 'reserved': requests*MAX_WIRE,
                'need_robots': not current_robots, 'day': at.date()}


async def fetch_public(client, url, *, etag=None, robots=False):
    # All URLs are constructed here; never follow reporter links or redirects.
    if url != ORIGIN+'/robots.txt' and not re.fullmatch(re.escape(ORIGIN)+r'/starting-goalies/\d{4}-\d{2}-\d{2}', url):
        raise SourceFormatError('Only the public goalie page and crawler policy may be fetched')
    headers = {'Accept-Encoding': 'gzip', 'User-Agent': AGENT}
    if etag:
        headers['If-None-Match'] = etag
    async with client.stream('GET', url, headers=headers) as response:
        if response.status_code == 304 and etag and not robots:
            return None, 0, etag
        if response.status_code != 200:
            raise SourceFormatError(f'Source HTTP {response.status_code}; no automatic retry')
        content_type = response.headers.get('content-type', '').split(';')[0].lower().strip()
        if content_type not in ({'text/plain'} if robots else {'text/html'}):
            raise SourceFormatError('Source response type changed')
        encoding = response.headers.get('content-encoding', 'identity').lower()
        if encoding not in {'identity', 'gzip'}:
            raise SourceFormatError('Unsupported bounded source encoding')
        cap = 64_000 if robots else MAX_HTML
        decoder = zlib.decompressobj(31) if encoding == 'gzip' else None
        wire, body = 0, bytearray()
        async for raw in response.aiter_raw(chunk_size=65536):
            wire += len(raw)
            if wire > MAX_WIRE:
                raise SourceFormatError('Source wire-byte limit exceeded')
            chunk = decoder.decompress(raw, cap-len(body)+1) if decoder else raw
            body.extend(chunk)
            if len(body) > cap or decoder and decoder.unconsumed_tail:
                raise SourceFormatError('Source decoded-byte limit exceeded')
        if decoder and (not decoder.eof or decoder.unused_data):
            raise SourceFormatError('Source compressed stream is incomplete or concatenated')
        tag = response.headers.get('etag', '')
        tag = tag if re.fullmatch(r'(?:W/)?"[\x21\x23-\x7e]{1,120}"', tag) else None
        return bytes(body), wire, tag


async def eligible():
    at = now()
    async with db.Session() as session:
        row = await session.get(ProviderState, CONTROL)
        if row is None or phase(row.info, at) != 'active':
            return False
        if row.info.get('initial_check_pending') is True:
            return True
        start = datetime.combine(at.date(), time.min, PACIFIC)
        return bool(await session.scalar(select(Fixture.id).where(Fixture.sport == 'NHL',
            Fixture.commence_time > at, Fixture.commence_time <= at+timedelta(hours=8),
            Fixture.commence_time < start+timedelta(days=1)).limit(1)))


def failure_reason(exc):
    """Useful failure categories without exposing HTTP exceptions or secrets."""
    if isinstance(exc, SourceFormatError):
        return str(exc)
    if isinstance(exc, httpx.ReadTimeout):
        return 'The goalie source timed out while responding; saved reports were kept. Explicit resume required.'
    if isinstance(exc, httpx.ConnectTimeout):
        return 'The goalie source connection timed out; saved reports were kept. Explicit resume required.'
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return 'The goalie source check exceeded its time limit; saved reports were kept. Explicit resume required.'
    if isinstance(exc, (httpx.NetworkError, httpx.ProtocolError)):
        return 'The goalie source connection failed; saved reports were kept. Explicit resume required.'
    return 'Source collection interrupted or failed; explicit resume required'


async def collect(*, manual=False, transport=None, admission=None):
    if 'NHL' not in settings.active_sports or not manual and not await eligible():
        return {'status': 'idle', 'mode': 'shadow'}
    admission = admission or await reserve()
    day = admission['day']
    wire = 0
    try:
        async with asyncio.timeout(40):
            async with httpx.AsyncClient(timeout=15, follow_redirects=False, transport=transport) as client:
                if admission['need_robots']:
                    body, count, _ = await fetch_public(client, ORIGIN+'/robots.txt', robots=True)
                    wire += count
                    allowed = robots_allowed(body, page_url(day))
                    await limits.observe(ROBOTS, {'allowed': allowed, 'sha256': hashlib.sha256(body).hexdigest(),
                                                 'policy_text':body.decode('utf-8', errors='strict')})
                    if not allowed:
                        raise SourceFormatError('Source crawler policy disallows the public goalie page')
                async with db.Session() as session:
                    cached = await session.get(ProviderState, 'dfo-page:'+str(day))
                    cached_info = dict(cached.info) if cached else {}
                body, count, etag = await fetch_public(client, page_url(day), etag=cached_info.get('etag'))
                wire += count
                observed = now()
                facts = parse_page(body, day, observed) if body is not None else cached_info.get('facts')
                if not facts or facts.get('contract') != CONTRACT or facts.get('date') != str(day):
                    raise SourceFormatError('Unchanged response has no compatible saved public page')
                digest = hashlib.sha256(body).hexdigest() if body is not None else cached_info['sha256']
            result = await save_reports(facts, observed, digest, etag, admission, wire)
            return result
    except (Exception, asyncio.CancelledError) as exc:
        # SourceFormatError text is authored locally. Never persist arbitrary
        # request exceptions, response bodies, cookies or redirect locations.
        reason = failure_reason(exc)
        async with db.Session.begin() as session:
            row = await session.get(ProviderState, CONTROL, with_for_update=True)
            if row and row.info.get('attempt_id') == admission['attempt_id']:
                row.info = {**row.info, 'halted': True, 'status': 'failed', 'reason': reason, 'failed_at': now().isoformat()}
                row.observed_at = now()
            session.add(AuditLog(action='DFO_PILOT_HALTED', entity_id='DailyFaceoff',
                details={'reason': reason, 'category': type(exc).__name__, 'reservation_retained': admission['reserved']}))
        if isinstance(exc, asyncio.CancelledError):
            raise
        return {'status': 'failed', 'mode': 'shadow', 'reason': reason, 'paid_credits': 0}


async def save_reports(facts, observed, digest, etag, admission, wire):
    start = datetime.combine(admission['day'], time.min, PACIFIC)
    saved, changes, unmatched = 0, 0, len(facts['games'])
    async with db.Session.begin() as session:
        fixtures = (await session.scalars(select(Fixture).where(Fixture.sport == 'NHL',
            Fixture.commence_time >= start, Fixture.commence_time < start+timedelta(days=1)).limit(32))).all()
        identity_cache = await session.get(ProviderState, nhl_advanced.CACHE_KEY)
        for fixture in fixtures:
            rows = [g for g in facts['games'] if canonical(g['home']) == canonical(fixture.home)
                and canonical(g['away']) == canonical(fixture.away)
                and abs((aware(g['start_at'])-aware(fixture.commence_time)).total_seconds()) <= 120]
            if len(rows) == 1:
                targets = [f for f in fixtures if canonical(rows[0]['home']) == canonical(f.home)
                    and canonical(rows[0]['away']) == canonical(f.away)
                    and abs((aware(rows[0]['start_at'])-aware(f.commence_time)).total_seconds()) <= 120]
                if len(targets) != 1:
                    rows = []
            key = 'dfo:'+fixture.id
            previous = await session.get(ProviderState, key)
            if len(rows) != 1:
                if previous:
                    missing = {**previous.info, 'missing_from_page': True, 'checked_at': observed.isoformat()}
                    if not previous.info.get('missing_from_page'):
                        session.add(Evidence(fixture_id=fixture.id, kind='nhl_goalie_report', source_at=observed,
                            observed_at=observed, payload=missing))
                        changes += 1
                    session.add(Evidence(fixture_id=fixture.id, kind='nhl_goalie_observation', source_at=observed,
                        observed_at=observed, payload={'contract':CONTRACT,'fixture_start_at':aware(fixture.commence_time).isoformat(),
                            'missing_from_page':True,'fingerprint':previous.info.get('fingerprint'),'body_sha256':digest}))
                    previous.info = {**previous.info, 'missing_from_page': True, 'checked_at': observed.isoformat()}
                continue
            unmatched -= 1
            report = json.loads(json.dumps(rows[0]))
            for side, goalie in report['sides'].items():
                goalie.update(identity_for(fixture, side, goalie['name'], identity_cache, observed))
            identity = {**report, 'sides':{side:{k:v for k,v in goalie.items() if k!='identity_observed_at'}
                                         for side,goalie in report['sides'].items()}}
            fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            changed = previous is None or previous.info.get('fingerprint') != fingerprint or previous.info.get('missing_from_page')
            info = {'mode': 'shadow', 'contract': CONTRACT, 'fixture_id': fixture.id,
                'fixture_start_at': aware(fixture.commence_time).isoformat(), 'report': report,
                'source_url': page_url(admission['day']), 'checked_at': observed.isoformat(), 'missing_from_page': False,
                'first_observed_at': observed.isoformat() if changed else previous.info['first_observed_at'],
                'fingerprint': fingerprint, 'body_sha256': digest}
            if changed:
                session.add(Evidence(fixture_id=fixture.id, kind='nhl_goalie_report', source_at=observed,
                    observed_at=observed, payload={**info, 'manual_at_collection':{
                        'names': fixture.metrics.get('goalie_confirmations'), 'at': fixture.metrics.get('confirmed_at'),
                        'method': fixture.metrics.get('starter_confirmation_method')}}))
                changes += 1
            # A small receipt records unchanged rechecks without creating a new
            # source revision. Future checkpoint grading needs the actual check
            # times, not just the first time a goalie name/status changed.
            session.add(Evidence(fixture_id=fixture.id, kind='nhl_goalie_observation', source_at=observed,
                observed_at=observed, payload={'contract':CONTRACT,'fixture_start_at':aware(fixture.commence_time).isoformat(),
                    'missing_from_page':False,'fingerprint':fingerprint,'body_sha256':digest}))
            await session.execute(insert(ProviderState).values(provider=key, observed_at=observed, info=info)
                .on_conflict_do_update(index_elements=[ProviderState.provider], set_={'observed_at': observed, 'info': info}))
            saved += 1
        await session.execute(insert(ProviderState).values(provider='dfo-page:'+facts['date'], observed_at=observed,
            info={'facts': facts, 'etag': etag, 'sha256': digest}).on_conflict_do_update(index_elements=[ProviderState.provider],
                set_={'observed_at': observed, 'info': {'facts': facts, 'etag': etag, 'sha256': digest}}))
        # Release only known unused wire reservation after complete validation
        # and cache persistence; uncertain failures retain their full allocation.
        unused = admission['reserved']-wire
        for key in admission['keys'][1:]:
            await session.execute(update(RuntimeLimit).where(RuntimeLimit.key == key, RuntimeLimit.used >= unused)
                                  .values(used=RuntimeLimit.used-unused))
        control_row = await session.get(ProviderState, CONTROL, with_for_update=True)
        control_row.info = {**control_row.info, 'status': 'succeeded', 'halted': False, 'reason': None,
            'last_success_at': observed.isoformat(), 'matched_games': saved, 'changed_reports': changes,
            'unmatched_source_games': max(0, unmatched), 'wire_bytes_last': wire}
        control_row.observed_at = observed
        session.add(AuditLog(action='DFO_PILOT_COLLECTED', entity_id='DailyFaceoff', details={
            'matched_games': saved, 'changed_reports': changes, 'wire_bytes': wire, 'mode': 'shadow'}))
    return {'status': 'succeeded', 'mode': 'shadow', 'matched_games': saved, 'paid_credits': 0}


def identity_for(fixture, side, name, cache, observed):
    """Saved identity only. Old samples never become current availability/form."""
    found = {}
    comparison = fixture.metrics.get('nhl_goalie_comparison', {})
    try:
        if aware(comparison['observed_at']) <= observed:
            for row in comparison.get('sides', {}).get(side, []):
                if name and canonical(row['name']) == canonical(name) and re.fullmatch(r'\d{7}', row['player_id']):
                    found[row['player_id']] = ('saved_nhl_comparison', comparison['observed_at'])
    except (KeyError, TypeError, ValueError):
        pass
    if (cache and aware(cache.observed_at) <= observed and cache.info.get('schema_version') == 1
            and cache.info.get('model_approved_by_import') is False and fixture.metrics.get(side+'_abbrev')):
        for row in cache.info.get('goalies', {}).values():
            if (row.get('latest_team') == fixture.metrics[side+'_abbrev'] and name
                    and canonical(row['name']) == canonical(name) and re.fullmatch(r'\d{7}', row['player_id'])):
                found.setdefault(row['player_id'], ('saved_goalie_history', aware(cache.observed_at).isoformat()))
    if len(found) != 1:
        return {'player_id':None, 'identity_source':None, 'identity_observed_at':None}
    identifier, (source, at) = next(iter(found.items()))
    return {'player_id':identifier, 'identity_source':source, 'identity_observed_at':at}


async def status(session):
    at = now()
    row = await session.get(ProviderState, CONTROL)
    info = dict(row.info) if row else {}
    keys = (f'dfo-requests:{at.date()}', f'dfo-wire-day:{at.date()}', f'dfo-wire-month:{at:%Y-%m}')
    values = [await session.get(RuntimeLimit, key) for key in keys]
    return {**info, 'mode': 'shadow', 'phase': phase(info, at), 'paid_credits': 0,
        'requests_reserved_today': values[0].used if values[0] else 0, 'request_cap': DAILY_REQUESTS,
        'bytes_reserved_today': values[1].used if values[1] else 0, 'daily_byte_cap': DAILY_BYTES,
        'bytes_reserved_month': values[2].used if values[2] else 0, 'monthly_byte_cap': MONTHLY_BYTES,
        'minimum_interval_seconds': INTERVAL}


async def detail(session, fixture):
    if fixture.sport != 'NHL':
        return None
    row = await session.get(ProviderState, 'dfo:'+fixture.id)
    if row is None:
        return {'mode': 'shadow', 'status': 'missing', 'sides': {}, 'paid_credits': 0}
    info, at = row.info, now()
    if info.get('contract') != CONTRACT or aware(info['fixture_start_at']) != aware(fixture.commence_time):
        return {'mode': 'shadow', 'status': 'unavailable', 'sides': {}, 'paid_credits': 0}
    fresh = timedelta(0) <= at-aware(row.observed_at) <= timedelta(minutes=20) and not info.get('missing_from_page')
    manual = fixture.metrics.get('starter_confirmation_method') == 'manual_operator' and fixture.metrics.get('personnel_confirmed') is True
    try:
        current = manual and timedelta(0) <= at-aware(fixture.metrics['confirmed_at']) <= timedelta(minutes=30)
    except (KeyError, TypeError, ValueError):
        current = False
    sides = {}
    for side, goalie in info['report']['sides'].items():
        chosen = fixture.metrics.get('goalie_confirmations', {}).get(side)
        comparison = ('manual_expired' if manual and not current else 'no_manual_confirmation' if not current else
            'source_unconfirmed' if not fresh or goalie['reported_status'] != 'confirmed' else
            'matches_manual' if isinstance(chosen, str) and goalie['name'] and canonical(chosen) == canonical(goalie['name']) else 'conflicts_manual')
        sides[side] = {**goalie, 'comparison': comparison}
    return {'mode': 'shadow', 'status': 'fresh' if fresh else 'stale', 'sides': sides, 'paid_credits': 0,
        'observed_at': aware(row.observed_at).isoformat(), 'first_observed_at': info['first_observed_at'],
        'valid_until': (aware(row.observed_at)+timedelta(minutes=20)).isoformat(), 'pregame': at < aware(fixture.commence_time),
        'source_url': info['source_url'], 'missing_from_page': info.get('missing_from_page', False)}
