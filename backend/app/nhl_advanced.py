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
                       rolling, pair_checks, goalie_checks, nhl_checks)

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
            if response.status_code != 200:
                raise ValueError("NHL file request failed; no retry")
            encoding = response.headers.get("content-encoding", "identity")
            if compressed and encoding != "gzip" or not compressed and encoding != "identity":
                raise ValueError("Required bandwidth-safe encoding unavailable")
            length = response.headers.get("content-length")
            if length is not None and (not length.isdigit() or int(length) > cap):
                raise ValueError("NHL file transport cap exceeded")
            modified = response.headers.get("last-modified")
            published = aware(parsedate_to_datetime(modified)) if modified else None
            if published is None or published > observed or observed - published > timedelta(hours=48):
                raise ValueError("NHL file publication time is missing, future or too old")
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
            "model_approved_by_import": False, "starters_confirmed_by_import": False}


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


async def sync(*, transport=None, admission=None):
    if not settings.nhl_advanced_enabled:
        return {"status": "disabled"}
    if db.Session is None:
        raise ValueError("NHL statistics database is not configured")
    if not date(2026,7,1) <= now().date() < date(2027,7,1):
        raise BudgetExceeded("The 2026 NHL source contract requires a season update")
    monthly_key, day = admission or await reserve_batch()
    await limits.observe(STATUS_KEY, {"status": "running", "started_at": now().isoformat(), "date": str(day)})
    try:
        async with asyncio.timeout(180):
            with tempfile.TemporaryDirectory(prefix="nhl-statistics-") as temporary:
                team_path, goalie_path = Path(temporary) / "teams.csv", Path(temporary) / "goalies.zip"
                async with httpx.AsyncClient(timeout=15, follow_redirects=False, transport=transport,
                                            headers={'User-Agent':'G-Sports-private-statistics/0.1'}) as client:
                    team_source = await download(client, TEAM_URL, team_path, compressed=True)
                    goalie_source = await download(client, GOALIE_URL, goalie_path)
                    # One explicit, bounded free verification request; no generic
                    # retry loop and no odds/AI fallback.
                    reference_url = f"https://api-web.nhle.com/v1/score/{day - timedelta(days=1)}"
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
                parse = asyncio.create_task(asyncio.to_thread(build_batch, team_path, goalie_path, day, reference,
                                                             {"team": team_source, "goalie": goalie_source}))
                try:
                    batch = await asyncio.shield(parse)
                except asyncio.CancelledError:
                    # The bounded parsing thread must release its files before
                    # TemporaryDirectory cleanup (particularly on Windows).
                    await parse
                    raise
        serialized = json.dumps(batch, separators=(",", ":"))
        if len(serialized.encode()) > 200_000:
            raise ValueError("NHL statistics cache exceeded byte cap")
        actual = team_source["wire_bytes"] + goalie_source["wire_bytes"] + MAX_REFERENCE
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
                  "team_games": batch["team_games"], "wire_accounted": actual, "paid_credits": 0}
        await limits.observe(STATUS_KEY, result)
        return result
    except (Exception, asyncio.CancelledError) as exc:
        await limits.observe(STATUS_KEY, {"status": "failed", "date": str(day), "category": type(exc).__name__,
                                        "failed_at": now().isoformat(), "retained_previous_cache": True})
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
            'goalie_candidates':[g for g in batch.get('goalies',{}).values() if g.get('latest_team') in codes.values()],
            'starters_confirmed_by_import':False,'model_approved_by_import':False}
