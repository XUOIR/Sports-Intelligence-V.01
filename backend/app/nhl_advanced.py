"""Shared daily NHL descriptive statistics with durable bandwidth/admission caps.

MoneyPuck facts never set model factors, goalie confirmations, probabilities,
PLAY gates, wagers or AI requests. Reads use the database cache exclusively.
"""
import asyncio
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from email.utils import parsedate_to_datetime
import hashlib
import io
import json
import logging
from pathlib import Path
import tempfile
import time
import zipfile
import zlib

import httpx
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from . import db
from .clock import now, aware
from .config import settings
from .limits import limits, BudgetExceeded
from .models import ProviderState, RuntimeLimit, AuditLog
from .nhl_data import (TEAM_FIELDS, GOALIE_FIELDS, csv_rows, validate_team, validate_goalie,
                       rolling, team_context, pair_checks, goalie_checks, nhl_checks)

TEAM_URL = "https://moneypuck.com/moneypuck/playerData/careers/gameByGame/all_teams.csv"
GOALIE_URL = "https://peter-tanner.com/moneypuck/downloads/seasonPlayersSummary/goalies/2026.zip"
MAX_TEAM_WIRE = 40 * 1024 * 1024
MAX_TEAM_DECODED = 160 * 1024 * 1024
MAX_GOALIE_WIRE = 2_000_000
MAX_GOALIE_DECODED = 8 * 1024 * 1024
MAX_REFERENCE = 2_000_000
RESERVATION = MAX_TEAM_WIRE + MAX_GOALIE_WIRE + MAX_REFERENCE
CACHE_KEY = "nhl-advanced-statistics"
STATUS_KEY = "nhl-advanced-import"
PROBE_KEY = 'nhl-advanced-probe'
PROBE_RESERVATION = 2_000_000
PROBE_SAMPLE = 8192
log = logging.getLogger('nhl-statistics')
SAFE_IMPORT_REASONS = frozenset({
    'NHL file request failed; no retry', 'Required bandwidth-safe encoding unavailable',
    'NHL file transport cap exceeded', 'NHL file publication time is missing, future or too old',
    'NHL wire-byte cap exceeded', 'NHL decoded-byte cap exceeded', 'Incomplete NHL file',
    'NHL decompression budget/trailing data rejected', 'NHL parsing deadline exceeded',
    'Incomplete/current-day game appeared in daily source', 'Duplicate NHL team statistic',
    'NHL goalie ZIP contract changed', 'Unexpected goalie season/day', 'Duplicate goalie statistic',
    'Current-season NHL coverage is incomplete', 'Official NHL verification date mismatch',
    "Previous day's NHL games are not all final", 'NHL sources do not reconcile',
    'Team and goalie files have different game coverage', 'Official NHL verification request failed',
    'NHL verification byte cap exceeded', 'NHL statistics cache exceeded byte cap',
    'Source sample is not a ZIP file', 'Source sample is not valid gzip', 'Empty source sample',
})


def import_failure(exc, stage):
    # Publish only our fixed validation messages, never upstream bodies/URLs.
    reason = str(exc) if isinstance(exc, ValueError) and str(exc) in SAFE_IMPORT_REASONS else 'Import did not complete; inspect the stage and error category.'
    return {'status': 'failed', 'stage': stage, 'category': type(exc).__name__, 'reason': reason,
            'failed_at': now().isoformat(), 'retained_previous_cache': True}


def source_headers(response, *, compressed, observed):
    if response.status_code != 200:
        raise ValueError('NHL file request failed; no retry')
    encoding = response.headers.get('content-encoding', 'identity').lower()
    if compressed and encoding != 'gzip' or not compressed and encoding != 'identity':
        raise ValueError('Required bandwidth-safe encoding unavailable')
    length = response.headers.get('content-length')
    cap = MAX_TEAM_WIRE if compressed else MAX_GOALIE_WIRE
    if length is not None and (not length.isdigit() or int(length) > cap):
        raise ValueError('NHL file transport cap exceeded')
    modified = response.headers.get('last-modified')
    published = aware(parsedate_to_datetime(modified)) if modified else None
    if published is None or published > observed or observed-published > timedelta(hours=48):
        raise ValueError('NHL file publication time is missing, future or too old')
    return length, published


async def reserve_probe():
    """A bounded diagnostic is separate from, and cannot reset, import admission."""
    at = now()
    async with db.Session.begin() as session:
        await session.execute(insert(RuntimeLimit).values(key='control:paid', used=0).on_conflict_do_nothing())
        await session.get(RuntimeLimit, 'control:paid', with_for_update=True)
        await limits._increment(session, f'moneypuck-probe:{at.date()}', 1, 1)
        await limits._increment(session, f'moneypuck-wire:{at:%Y-%m}', PROBE_RESERVATION, settings.nhl_advanced_monthly_bytes)
        session.add(AuditLog(action='NHL_SOURCE_PROBE_ADMITTED', entity_id='MoneyPuck',
                            details={'wire_reserved': PROBE_RESERVATION, 'source_requests': 2}))
    return at.date()


async def probe_sources(*, transport=None, admission=None):
    if not settings.nhl_advanced_enabled:
        return {'status': 'disabled', 'paid_credits': 0}
    day = admission or await reserve_probe()
    result = {'status': 'running', 'date': str(day), 'checked_at': now().isoformat(), 'sources': [],
              'paid_credits': 0, 'wire_reserved': PROBE_RESERVATION,
              'note': 'Transport samples only. No statistics imported, goalie confirmed or model approved.'}
    await limits.observe(PROBE_KEY, result)
    try:
        async with asyncio.timeout(25):
            async with httpx.AsyncClient(timeout=10, follow_redirects=False, transport=transport,
                                        headers={'User-Agent': 'G-Sports-private-statistics/0.1'}) as client:
                for kind, url, compressed in [('team', TEAM_URL, True), ('goalie', GOALIE_URL, False)]:
                    observed = now()
                    row = {'source': kind, 'observed_at': observed.isoformat()}
                    try:
                        async with client.stream('GET', url, headers={'Accept-Encoding': 'gzip' if compressed else 'identity'}) as response:
                            row.update(http_status=response.status_code,
                                       encoding=response.headers.get('content-encoding', 'identity'),
                                       content_length=response.headers.get('content-length'),
                                       last_modified=response.headers.get('last-modified'))
                            _, published = source_headers(response, compressed=compressed, observed=observed)
                            row['published_at'] = published.isoformat()
                            # Close the response after one small raw chunk. Never
                            # consume or cache a complete source in this operation.
                            sample = b''
                            async for chunk in response.aiter_raw(chunk_size=PROBE_SAMPLE):
                                sample = chunk
                                break
                            if not sample:
                                raise ValueError('Empty source sample')
                            if compressed:
                                try:
                                    zlib.decompressobj(31).decompress(sample, PROBE_SAMPLE)
                                except zlib.error:
                                    raise ValueError('Source sample is not valid gzip') from None
                            elif not sample.startswith(b'PK\x03\x04'):
                                raise ValueError('Source sample is not a ZIP file')
                            row.update(status='sample_available', sample_bytes=len(sample))
                    except Exception as exc:
                        failure = import_failure(exc, kind + '_transport')
                        row.update(status='failed', reason=failure['reason'], category=failure['category'])
                    result['sources'].append(row)
        result['status'] = 'complete' if all(r['status']=='sample_available' for r in result['sources']) else 'failed'
    except (Exception, asyncio.CancelledError) as exc:
        failure = import_failure(exc, 'transport_probe')
        result.update(status='failed', reason=failure['reason'], category=failure['category'])
        await limits.observe(PROBE_KEY, result)
        if isinstance(exc, asyncio.CancelledError):
            raise
    result['completed_at'] = now().isoformat()
    # Keep the conservative reservation even on success: TCP/read-ahead can
    # exceed the tiny sample returned by HTTPX. Never refund an uncertain call.
    await limits.observe(PROBE_KEY, result)
    return result


async def download(client, url, path, *, compressed=False):
    if url not in {TEAM_URL, GOALIE_URL}:
        raise ValueError("NHL data destination rejected")
    cap = MAX_TEAM_WIRE if compressed else MAX_GOALIE_WIRE
    decoded_cap = MAX_TEAM_DECODED if compressed else MAX_GOALIE_WIRE
    wire = decoded = 0
    digest = hashlib.sha256()
    observed = now()
    async with asyncio.timeout(90 if compressed else 20):
        async with client.stream("GET", url, headers={"Accept-Encoding": "gzip" if compressed else "identity"}) as response:
            length, published = source_headers(response, compressed=compressed, observed=observed)
            decoder = zlib.decompressobj(31) if compressed else None
            with path.open("wb") as target:
                async for raw in response.aiter_raw(chunk_size=65536):
                    wire += len(raw)
                    if wire > cap:
                        raise ValueError("NHL wire-byte cap exceeded")
                    chunk = decoder.decompress(raw, decoded_cap - decoded + 1) if decoder else raw
                    if decoder and (decoder.unconsumed_tail or decoder.unused_data):
                        raise ValueError("NHL decompression budget/trailing data rejected")
                    decoded += len(chunk)
                    if decoded > decoded_cap:
                        raise ValueError("NHL decoded-byte cap exceeded")
                    digest.update(chunk)
                    target.write(chunk)
            if (not decoded or decoder and not decoder.eof or length is not None and wire != int(length)):
                raise ValueError("Incomplete NHL file")
    return {"url": url, "observed_at": observed.isoformat(), "published_at": published.isoformat(),
            "sha256": digest.hexdigest(), "wire_bytes": wire, "decoded_bytes": decoded}


def build_batch(team_path, goalie_path, day, reference, sources):
    started = time.monotonic()
    teams, goalies = [], []
    team_keys, goalie_keys = set(), set()
    quarantined = 0
    with team_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv_rows(handle, TEAM_FIELDS):
            if time.monotonic() - started > 45:
                raise ValueError("NHL parsing deadline exceeded")
            if row["season"] != "2026":
                quarantined += int(row["playerTeam"] == row["opposingTeam"])
                continue
            _, game_day = validate_team(row)
            if game_day >= day:
                raise ValueError("Incomplete/current-day game appeared in daily source")
            key = (row["gameId"], row["playerTeam"], row["situation"])
            if key in team_keys:
                raise ValueError("Duplicate NHL team statistic")
            team_keys.add(key)
            teams.append(row)
    with zipfile.ZipFile(goalie_path) as archive:
        members = archive.infolist()
        if len(members) != 1 or not members[0].filename.endswith(".csv") or members[0].file_size > MAX_GOALIE_DECODED:
            raise ValueError("NHL goalie ZIP contract changed")
        with archive.open(members[0]) as handle:
            for row in csv_rows(io.TextIOWrapper(handle, encoding="utf-8-sig"), GOALIE_FIELDS, 20_000):
                _, game_day = validate_goalie(row)
                if row["season"] != "2026" or game_day >= day:
                    raise ValueError("Unexpected goalie season/day")
                key = (row["gameId"], row["playerId"], row["situation"])
                if key in goalie_keys:
                    raise ValueError("Duplicate goalie statistic")
                goalie_keys.add(key)
                goalies.append(row)
    if not teams or not goalies or len({r["playerTeam"] for r in teams}) != 32:
        raise ValueError("Current-season NHL coverage is incomplete")
    if reference.get("currentDate") != (day - timedelta(days=1)).isoformat():
        raise ValueError("Official NHL verification date mismatch")
    if any(g.get("gameState") not in {"OFF", "FINAL"} for g in reference.get("games", []) if g.get("gameType") == 2):
        raise ValueError("Previous day's NHL games are not all final")
    checks = [pair_checks(teams), goalie_checks(goalies, teams)]
    official = nhl_checks(reference, teams) if reference.get("games") else {"completed_games": 0, "failures": []}
    checks.append(official)
    if any(check["failures"] for check in checks):
        raise ValueError("NHL sources do not reconcile")
    source_team_games = {r["gameId"] for r in teams}
    source_goalie_games = {r["gameId"] for r in goalies}
    if source_team_games != source_goalie_games:
        raise ValueError("Team and goalie files have different game coverage")
    team_windows = {team: rolling(teams, day, team=team) for team in sorted({r["playerTeam"] for r in teams})}
    contexts={team:team_context(teams,day,team) for team in team_windows}
    goalie_windows = {}
    for player in sorted({r["playerId"] for r in goalies}):
        rows = [r for r in goalies if r["playerId"] == player and r["situation"] == "all"]
        last = max(rows, key=lambda r: (r["gameDate"], r["gameId"]))
        row = rolling(goalies, day, goalie=player)
        row.update(player_id=player, name=last["name"][:100], latest_team=last["playerTeam"], starter_confirmed=False)
        goalie_windows[player] = row
    return {"schema_version": 1, "source": "MoneyPuck.com", "source_url": "https://moneypuck.com/data.htm",
            "classification": "descriptive_statistics", "as_of_date": day.isoformat(),
            "observed_at": now().isoformat(), "verified_through": reference["currentDate"],
            "latest_game_date": max(r["gameDate"] for r in teams), "sources": sources,
            "team_games": len(source_team_games), "verified_games_previous_day": official["completed_games"],
            "historical_identity_rows_quarantined": quarantined, "teams": team_windows, "goalies": goalie_windows,
            "team_context":contexts,"model_approved_by_import": False, "starters_confirmed_by_import": False}


async def reserve_batch():
    at = now()
    async with db.Session.begin() as session:
        await session.execute(insert(RuntimeLimit).values(key="control:paid", used=0).on_conflict_do_nothing())
        await session.get(RuntimeLimit, "control:paid", with_for_update=True)
        await limits._increment(session, f"moneypuck-batch:{at.date()}", 1, 1)
        await limits._increment(session, f"moneypuck-wire:{at:%Y-%m}", RESERVATION, settings.nhl_advanced_monthly_bytes)
        # The daily admission and byte reservation survive failed calls, restarts
        # and concurrent tabs. Failure retains the whole uncertain reservation.
        session.add(AuditLog(action="NHL_ADVANCED_IMPORT_ADMITTED", entity_id="MoneyPuck", details={"wire_reserved": RESERVATION}))
    return f"moneypuck-wire:{at:%Y-%m}", at.date()


async def reserve_manual_recovery():
    """Explicit operator fallback only; never reset or re-admit a daily import.

    This is intentionally not exposed through the scheduler or HTTP routes.
    Public downloads can be reachable from the operator's computer even when
    the hosting network receives a redirect/access denial.
    """
    at = now()
    async with db.Session.begin() as session:
        await session.execute(insert(RuntimeLimit).values(key='control:paid', used=0).on_conflict_do_nothing())
        await session.get(RuntimeLimit, 'control:paid', with_for_update=True)
        daily = await session.get(RuntimeLimit, f'moneypuck-batch:{at.date()}')
        failed = await session.get(ProviderState, STATUS_KEY)
        probe = await session.get(ProviderState, PROBE_KEY)
        cache = await session.get(ProviderState, CACHE_KEY)
        eligible = (daily and daily.used == 1 and failed and failed.info.get('status') == 'failed'
                    and failed.info.get('date') == str(at.date()) and probe
                    and probe.info.get('date') == str(at.date())
                    and timedelta(0) <= at-aware(probe.observed_at) <= timedelta(hours=1)
                    and probe.info.get('status') == 'failed'
                    and any(s.get('http_status') in {301,302,303,307,308,403}
                            for s in probe.info.get('sources', [])))
        if not eligible:
            raise BudgetExceeded('Manual recovery requires today’s failed import and a recent failed source diagnostic')
        if cache and cache.info.get('as_of_date') == str(at.date()):
            raise BudgetExceeded('Current-day statistics are already saved; recovery is unnecessary')
        await limits._increment(session, f'moneypuck-manual-recovery:{at.date()}', 1, 1)
        await limits._increment(session, f'moneypuck-wire:{at:%Y-%m}', RESERVATION, settings.nhl_advanced_monthly_bytes)
        session.add(AuditLog(action='NHL_MANUAL_RECOVERY_ADMITTED', entity_id='MoneyPuck',
                            details={'wire_reserved': RESERVATION, 'mode': 'operator_public_download',
                                     'original_daily_attempt_retained': True}))
    return f'moneypuck-wire:{at:%Y-%m}', at.date()


async def sync(*, transport=None, admission=None, acquisition='scheduled_public_download'):
    if not settings.nhl_advanced_enabled:
        return {"status": "disabled"}
    if db.Session is None:
        raise ValueError("NHL statistics database is not configured")
    if not date(2026,7,1) <= now().date() < date(2027,7,1):
        raise BudgetExceeded("The 2026 NHL source contract requires a season update")
    monthly_key, day = admission or await reserve_batch()
    await limits.observe(STATUS_KEY, {"status": "running", "started_at": now().isoformat(), "date": str(day)})
    stage = 'team_download'
    try:
        async with asyncio.timeout(180):
            with tempfile.TemporaryDirectory(prefix="nhl-statistics-") as temporary:
                team_path, goalie_path = Path(temporary) / "teams.csv", Path(temporary) / "goalies.zip"
                async with httpx.AsyncClient(timeout=15, follow_redirects=False, transport=transport,
                                            headers={'User-Agent':'G-Sports-private-statistics/0.1'}) as client:
                    team_source = await download(client, TEAM_URL, team_path, compressed=True)
                    stage = 'goalie_download'
                    goalie_source = await download(client, GOALIE_URL, goalie_path)
                    # One explicit, bounded free verification request; no generic
                    # retry loop and no odds/AI fallback.
                    reference_url = f"https://api-web.nhle.com/v1/score/{day - timedelta(days=1)}"
                    stage = 'official_verification'
                    await limits.reserve("nhl", 1)
                    async with client.stream("GET", reference_url, headers={"Accept-Encoding": "identity"}) as response:
                        if response.status_code != 200:
                            raise ValueError("Official NHL verification request failed")
                        body = bytearray()
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            if len(body) + len(chunk) > MAX_REFERENCE:
                                raise ValueError("NHL verification byte cap exceeded")
                            body.extend(chunk)
                    reference = json.loads(body)
                stage = 'source_validation'
                parse = asyncio.create_task(asyncio.to_thread(build_batch, team_path, goalie_path, day, reference,
                                                             {"team": team_source, "goalie": goalie_source}))
                try:
                    batch = await asyncio.shield(parse)
                except asyncio.CancelledError:
                    # The bounded parsing thread must release its files before
                    # TemporaryDirectory cleanup (particularly on Windows).
                    await parse
                    raise
        batch['acquisition'] = acquisition
        serialized = json.dumps(batch, separators=(",", ":"))
        if len(serialized.encode()) > 200_000:
            raise ValueError("NHL statistics cache exceeded byte cap")
        actual = team_source["wire_bytes"] + goalie_source["wire_bytes"] + MAX_REFERENCE
        stage = 'cache_save'
        async with db.Session.begin() as session:
            stmt = insert(ProviderState).values(provider=CACHE_KEY, observed_at=now(), info=batch)
            await session.execute(stmt.on_conflict_do_update(index_elements=[ProviderState.provider],
                set_={"observed_at": stmt.excluded.observed_at, "info": stmt.excluded.info}))
            # Only known unused transfer capacity is released after complete
            # validation. A failed/uncertain batch never refunds its reservation.
            await session.execute(update(RuntimeLimit).where(RuntimeLimit.key == monthly_key,
                RuntimeLimit.used >= RESERVATION - actual).values(used=RuntimeLimit.used - (RESERVATION - actual)))
            session.add(AuditLog(action="NHL_ADVANCED_IMPORT_SUCCEEDED", entity_id="MoneyPuck",
                                details={"team_games": batch["team_games"], "wire_accounted": actual}))
        result = {"status": "succeeded", "date": str(day), "completed_at": now().isoformat(),
                  "team_games": batch["team_games"], "wire_accounted": actual, "paid_credits": 0,
                  "acquisition": acquisition}
        await limits.observe(STATUS_KEY, result)
        return result
    except (Exception, asyncio.CancelledError) as exc:
        failure = {**import_failure(exc, stage), 'date': str(day)}
        await limits.observe(STATUS_KEY, failure)
        log.warning('NHL statistics import failed at %s: %s (%s)', stage, failure['reason'], failure['category'])
        if isinstance(exc, asyncio.CancelledError):
            raise
        # Do not emit upstream exception text or retry this day's admission.
        return {"status": "failed", "retained_previous_cache": True, "paid_credits": 0}


async def detail(session, fixture):
    if fixture.sport != "NHL" or not settings.nhl_advanced_enabled:
        return None
    row = await session.get(ProviderState, CACHE_KEY)
    state = await session.get(ProviderState, STATUS_KEY)
    if row is None:
        return {"status": "pending", "source": "MoneyPuck.com", "message": "Advanced statistics have not been imported yet."}
    batch = row.info
    age = now() - aware(row.observed_at)
    stale = age < timedelta(0) or age > timedelta(hours=26) or batch.get("as_of_date") != now().date().isoformat()
    if batch.get("schema_version") != 1 or batch.get("model_approved_by_import") is not False:
        return {"status": "unavailable", "source": "MoneyPuck.com", "message": "Statistics cache requires verification."}
    codes = {side: fixture.metrics.get(f"{side}_abbrev") for side in ("home", "away")}
    if not all(codes.values()):
        names = await session.get(ProviderState, "nhl-team-names")
        mapping = names.info.get("teams", {}) if names else {}
        for side in codes:
            name = getattr(fixture, side)
            matches = [key for key, value in mapping.items() if value == name]
            codes[side] = matches[0] if len(matches) == 1 else None
    sides = {}
    for side, code in codes.items():
        sides[side] = {"team": getattr(fixture, side), "abbrev": code,
                       "metrics": batch.get("teams", {}).get(code),
                       "goalies": [g for g in batch.get("goalies", {}).values() if g.get("latest_team") == code] if code else []}
    return {"status": "stale" if stale else "available", "source": "MoneyPuck.com",
            "source_url": "https://moneypuck.com/data.htm", "observed_at": aware(row.observed_at).isoformat(),
            "as_of_date": batch["as_of_date"], "verified_through": batch["verified_through"],
            "import_status": state.info.get("status") if state else None, "sides": sides,
            "note": "Descriptive statistics. Goalies are unconfirmed; these values do not approve a play or change model factors."}


async def matchup_teams(session, fixtures):
    """Read one saved cache for daily cards; never refresh an upstream source."""
    nhl = [fixture for fixture in fixtures if fixture.sport == 'NHL']
    if not nhl or not settings.nhl_advanced_enabled:
        return {}
    row = await session.get(ProviderState, CACHE_KEY)
    if row is None:
        return {f.id: {'status': 'pending', 'source': 'MoneyPuck.com', 'sides': {}} for f in nhl}
    batch, at = row.info, now()
    if (batch.get('schema_version') != 1 or batch.get('model_approved_by_import') is not False
            or aware(row.observed_at) > at):
        return {f.id: {'status': 'unavailable', 'source': 'MoneyPuck.com', 'sides': {}} for f in nhl}
    observed = aware(row.observed_at)
    stale = not timedelta(0) <= at - observed <= timedelta(hours=26) or batch.get('as_of_date') != at.date().isoformat()
    comparisons = {}
    for fixture in nhl:
        start = aware(fixture.commence_time)
        sides = {}
        for side in ('home', 'away'):
            code = fixture.metrics.get(f'{side}_abbrev')
            metrics = batch.get('teams', {}).get(code)
            # A current cache cannot masquerade as a historical pregame read.
            # Same-day completed games also cannot enter that game's context.
            if metrics:
                try:
                    latest = metrics.get('latest_game_date')
                    eligible = (isinstance(latest, str) and len(latest) == 10
                                and date.fromisoformat(latest) < start.date()
                                and observed <= start - timedelta(minutes=30))
                except (TypeError, ValueError):
                    eligible = False
                if not eligible:
                    metrics = {'status': 'not_pre_game', 'sample_games': 0, 'latest_game_date': None}
            sides[side] = {'team': getattr(fixture, side), 'abbrev': code, 'metrics': metrics}
        comparisons[fixture.id] = {'status': 'stale' if stale else 'available', 'source': 'MoneyPuck.com',
                                  'source_url': 'https://moneypuck.com/data.htm', 'observed_at': observed.isoformat(),
                                  'as_of_date': batch.get('as_of_date'), 'verified_through': batch.get('verified_through'), 'sides': sides}
    return comparisons


async def frozen_context(session, fixture, anchor):
    """Preserve genuine pre-anchor facts without changing the frozen model vector."""
    if not settings.nhl_advanced_enabled or fixture.sport != 'NHL':
        return None
    row = await session.get(ProviderState, CACHE_KEY)
    if row is None:
        return None
    at = aware(anchor)
    age = at - aware(row.observed_at)
    batch = row.info
    if (not timedelta(0) <= age <= timedelta(hours=26) or batch.get('as_of_date') != at.date().isoformat()
            or batch.get('schema_version') != 1 or batch.get('model_approved_by_import') is not False):
        return None
    sources = batch.get('sources', {})
    try:
        if set(sources) != {'team','goalie'} or any(aware(s['observed_at']) > at for s in sources.values()):
            return None
    except (KeyError, TypeError, ValueError):
        return None
    codes = {side: fixture.metrics.get(f'{side}_abbrev') for side in ('home','away')}
    if not all(code in batch.get('teams', {}) for code in codes.values()):
        return None
    return {'source':'MoneyPuck.com','classification':'observed_pre_anchor_descriptive_statistics',
            'cache_observed_at':aware(row.observed_at).isoformat(),'anchor_at':at.isoformat(),
            'as_of_date':batch['as_of_date'],'verified_through':batch['verified_through'],'sources':sources,
            'teams':{side:batch['teams'][code] for side,code in codes.items()},
            'team_context':{side:batch.get('team_context',{}).get(code) for side,code in codes.items()},
            'goalie_candidates':[g for g in batch.get('goalies',{}).values() if g.get('latest_team') in codes.values()],
            'starters_confirmed_by_import':False,'model_approved_by_import':False}
