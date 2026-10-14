import hashlib
import logging
import re
import unicodedata
from datetime import timedelta
from sqlalchemy import select
from . import db, providers
from .clock import now, aware
from .models import Fixture, Evidence, MarketOdds, State, Snapshot, AuditLog
from .maths import implied, parse_odds, decimal
from .model_config import SHARP_MOVEMENT
from .features import eligible_history
from .config import settings
from .limits import limits

log = logging.getLogger("ingestion")

def name(value):
    if isinstance(value, dict):
        value = value.get("default", "")
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise ValueError("Invalid team name")
    return value.strip()

def normalized(value):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize('NFKD',name(value).casefold()))

def quote_identity(bookmaker, market, selection, line):
    if market not in {"h2h","spreads","totals"} or (market == "h2h") != (line is None):
        raise ValueError("Market type / exact numerical line required")
    canonical_line = format(decimal(line).normalize(), "f") if line is not None else "none"
    return hashlib.sha256(f"{bookmaker}|{market}|{selection}|{canonical_line}".encode()).hexdigest()

def dirty(fixture, reason):
    fixture.dirty = True
    fixture.revision += 1
    fixture.suggested_stake = 0
    fixture.state = State.HOLD if fixture.state == State.RECOMMEND else fixture.state
    fixture.reason = reason[:500]
    fixture.updated_at = now()

def evidence(session, fixture, kind, payload, at=None):
    session.add(Evidence(fixture_id=fixture.id, kind=kind, observed_at=now(), source_at=at or now(), payload=payload))

async def reschedule(session, fixture, start):
    snapshot=await session.get(Snapshot,fixture.id)
    if snapshot:
        session.add(AuditLog(action="ARCHIVE_RESCHEDULED_SNAPSHOT",entity_id=fixture.id,details={
            "anchor_at":aware(snapshot.anchor_at).isoformat(),"vector":snapshot.vector,"context":snapshot.context,
            "baseline_probability":str(snapshot.baseline_home_probability),"new_start":start.isoformat()}))
        await session.delete(snapshot)
    fixture.commence_time=start
    dirty(fixture,"Official start changed; old snapshot archived and new anchor required")
    fixture.state=State.HOLD
    await session.flush()

async def ingest_nhl_personnel():
    async with db.Session() as session:
        fixtures=(await session.scalars(select(Fixture).where(Fixture.id.like("nhl:%"),Fixture.commence_time>now(),
            Fixture.commence_time<now()+timedelta(hours=2)).limit(6))).all()
    for fixture in fixtures:
        payload=await providers.nhl_game(fixture.id.split(":",1)[1])
        confirmations=providers.goalie_confirmation(payload)
        async with db.Session.begin() as session:
            current=await session.get(Fixture,fixture.id,with_for_update=True)
            if all(confirmations.values()):
                current.metrics={**current.metrics,"personnel_confirmed":True,"confirmed_at":now().isoformat(),"goalie_confirmations":confirmations}
                dirty(current,"Official starter confirmations changed")
            elif current.metrics.get("source_reference"):
                # Preserve still-current operator evidence; absence in a feed does not contradict it.
                continue
            else:
                current.metrics={**current.metrics,"personnel_confirmed":False,"goalie_confirmations":confirmations}
                current.state,current.suggested_stake,current.reason=State.HOLD,0,"NHL feed does not explicitly confirm both starting goalies"

async def ingest_nhl(history=False):
    games, standings = await providers.nhl_schedule(), await providers.nhl_standings()
    by_abbrev = {name(s["teamAbbrev"]): s for s in standings}
    histories = {}
    history_times = {}
    if history:
        for game in games:
            try:
                if not now() < aware(game["startTimeUTC"]) < now()+timedelta(days=3):
                    continue
                for side in ("homeTeam","awayTeam"):
                    abbreviation = game[side]["abbrev"]
                    if abbreviation not in histories and len(histories)<40:
                        histories[abbreviation] = await providers.nhl_history(abbreviation,game.get('season'))
                        cached=await limits.observation(f"nhl-history:{abbreviation}:{game.get('season') or 'now'}",max_age=4*3600)
                        history_times[abbreviation]=aware(cached['source_at']) if cached else now()
            except (ValueError,KeyError,TypeError):
                log.warning("NHL schedule team structure changed")
    async with db.Session() as session:
        for game in games:
            try:
                start = aware(game["startTimeUTC"])
                if not now() < start < now()+timedelta(days=3):
                    continue
                home, away = game["homeTeam"], game["awayTeam"]
                home_name = name(home["placeName"]) + " " + name(home["commonName"])
                away_name = name(away["placeName"]) + " " + name(away["commonName"])
                fid = f"nhl:{game['id']}"
                fixture = await session.get(Fixture, fid)
                if fixture is None:
                    fixture = Fixture(id=fid, sport="NHL", home=home_name, away=away_name, commence_time=start)
                    session.add(fixture)
                    await session.flush()
                elif aware(fixture.commence_time) != start:
                    await reschedule(session,fixture,start)
                evidence(session, fixture, "schedule", {"start": start.isoformat(), "provider_id": str(game["id"])})
                h, a = by_abbrev.get(home["abbrev"]), by_abbrev.get(away["abbrev"])
                if h and a:
                    evidence(session, fixture, "standings", {side: {"games": int(team["gamesPlayed"]),
                        "points_pct": float(team["pointPctg"])} for side, team in (("home",h),("away",a))})
                else:
                    log.warning("NHL standings missing for fixture %s", fid)
                if history:
                    payload = {}
                    for side, team in (("home", home), ("away", away)):
                        abbr = team["abbrev"]
                        if abbr not in histories:
                            raise ValueError("Bounded history fetch missing")
                        finished = []
                        for row in histories[abbr]:
                            if row.get("gameState") not in {"OFF", "FINAL"}:
                                continue
                            if "score" not in row["homeTeam"] or "score" not in row["awayTeam"]:
                                continue
                            started = aware(row["startTimeUTC"])
                            # Feed lacks end timestamps. Conservative next-day boundary avoids same-day leakage.
                            ended = (started+timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                            if ended <= started:
                                ended = started+timedelta(hours=6)
                            is_home = row["homeTeam"]["abbrev"] == abbr
                            won = row["homeTeam"]["score"] > row["awayTeam"]["score"]
                            finished.append({"started_at": started.isoformat(), "ended_at": ended.isoformat(), "win": won if is_home else not won})
                        payload[side] = eligible_history(finished, start)[:10]
                    evidence(session, fixture, "history", payload,at=min(history_times[home['abbrev']],history_times[away['abbrev']]))
                fixture.updated_at = now()
            except (KeyError, ValueError, TypeError) as exc:
                log.warning("NHL payload structure changed: %s", type(exc).__name__)
        await session.commit()

async def ingest_esports():
    for sport in providers.ESPORTS:
        if sport not in settings.active_sports:continue
        upcoming = await providers.esports_matches(sport)
        if not upcoming:
            continue
        past = await providers.esports_matches(sport, past=True)
        rosters = {}
        for row in upcoming:
            if not isinstance(row,dict):
                continue
            tid = row.get("tournament_id") or (row.get("tournament") or {}).get("id")
            if tid and tid not in rosters and len(rosters)<6:
                try:
                    rosters[tid] = await providers.esports_rosters(tid)
                except providers.ProviderError:
                    rosters[tid] = []
                    log.warning("Roster unavailable; hard HOLD for tournament %s", tid)
        async with db.Session() as session:
            for row in upcoming:
                try:
                    start = aware(row["begin_at"])
                    if not now() < start < now()+timedelta(days=3):
                        continue
                    opponents = providers.array(row, "opponents", 2)
                    if len(opponents) != 2:
                        raise ValueError("Incomplete opponents")
                    home, away = [o["opponent"] for o in opponents]
                    fid = f"panda:{row['id']}"
                    fixture = await session.get(Fixture, fid)
                    if fixture is None:
                        fixture = Fixture(id=fid, sport=sport, home=name(home["name"]), away=name(away["name"]), commence_time=start)
                        session.add(fixture)
                        await session.flush()
                    if aware(fixture.commence_time) != start:
                        await reschedule(session,fixture,start)
                    evidence(session, fixture, "schedule", {"start":start.isoformat()})
                    tid = row.get("tournament_id") or (row.get("tournament") or {}).get("id")
                    roster_rows = rosters.get(tid, [])
                    roster_lookup = {r.get("team", {}).get("id"): r.get("players") for r in roster_rows if isinstance(r,dict) and isinstance(r.get("team"),dict)}
                    roster_ok = all(providers.complete_roster(roster_lookup.get(team["id"])) for team in (home,away))
                    games = row.get("games")
                    maps = [g.get("map") for g in games if isinstance(g, dict)] if isinstance(games,list) else []
                    fixture.metrics = {**fixture.metrics, "roster_complete": roster_ok, "home_team_id":home["id"],"away_team_id":away["id"],"map_veto": maps[:10], "stats_window_start": providers.three_month_cutoff(start).isoformat()}
                    if not roster_ok:
                        dirty(fixture, "Null/incomplete tournament roster; personnel HOLD")
                        fixture.state = State.HOLD
                    payload = {}
                    for side, team in (("home",home),("away",away)):
                        rows = []
                        for match in past:
                            ids = [o.get("opponent", {}).get("id") for o in match.get("opponents", []) if isinstance(o, dict) and isinstance(o.get("opponent"),dict)]
                            if team["id"] not in ids or not match.get("end_at") or not match.get("begin_at") or not match.get("winner_id"):
                                continue
                            rows.append({"started_at": match["begin_at"], "ended_at":match["end_at"], "win": match["winner_id"] == team["id"]})
                        payload[side] = eligible_history(rows, start, esports=True)[:10]
                    evidence(session, fixture, "history", payload)
                    # Win rate is not season points percentage; no false NHL-style vector is generated for esports.
                except (KeyError, ValueError, TypeError) as exc:
                    log.warning("PandaScore payload structure changed: %s", type(exc).__name__)
            await session.commit()

async def ingest_odds():
    reevaluate = set()
    for sport in providers.ODDS_SPORTS:
        if sport not in settings.active_sports:continue
        async with db.Session() as session:
            scheduled=await session.scalar(select(Fixture.id).where(Fixture.sport==sport,
                Fixture.commence_time>now(),Fixture.commence_time<=now()+timedelta(hours=48)).limit(1))
        if sport=='NHL' and not scheduled:continue
        rows = await providers.odds(sport)
        async with db.Session() as session:
            for row in rows:
                try:
                    start = aware(row["commence_time"])
                    candidates = (await session.scalars(select(Fixture).where(Fixture.sport == sport,
                        Fixture.commence_time >= start-timedelta(minutes=5), Fixture.commence_time <= start+timedelta(minutes=5)))).all()
                    matching = [f for f in candidates if normalized(f.home) == normalized(row["home_team"]) and normalized(f.away) == normalized(row["away_team"])]
                    if len(matching) > 1:
                        raise ValueError("Ambiguous provider fixture mapping")
                    if sport=='NHL' and not matching:
                        log.warning('NHL odds could not be matched to an official fixture; row discarded')
                        continue
                    fixture = matching[0] if matching else await session.get(Fixture, f"odds:{row['id']}")
                    if fixture is None:
                        fixture = Fixture(id=f"odds:{row['id']}", sport=sport, home=name(row["home_team"]), away=name(row["away_team"]), commence_time=start)
                        session.add(fixture)
                        await session.flush()
                    elif fixture.id.startswith("odds:") and aware(fixture.commence_time)!=start:
                        await reschedule(session,fixture,start)
                    executable_sides=set()
                    for book in providers.array(row, "bookmakers", 20):
                        bookmaker = providers.BOOKMAKER_ALIASES.get(book["key"], book["key"])
                        for market in providers.array(book, "markets", 10):
                            key = market["key"]
                            if key not in {"h2h","spreads","totals"}:
                                continue
                            if key == "h2h" and (len(market.get("outcomes",[])) != 2 or {normalized(o.get("name",'')) for o in market["outcomes"]} != {normalized(fixture.home),normalized(fixture.away)}):
                                continue
                            for outcome in providers.array(market, "outcomes", 4):
                                try:
                                    price = parse_odds(outcome["price"], "decimal")
                                    line = decimal(outcome["point"]) if key != "h2h" else None
                                    selection = name(outcome["name"])
                                    selection = next((team for team in (fixture.home,fixture.away) if normalized(selection)==normalized(team)),selection)
                                    if key == "h2h" and selection not in {fixture.home, fixture.away}:
                                        continue  # Draw / three-way moneyline cannot use binary model.
                                    source_at = aware(market.get("last_update") or book["last_update"])
                                    if source_at > now() or now()-source_at > timedelta(hours=2):
                                        continue
                                    if bookmaker in {"playnow","bclc"} and key=="h2h" and now()-source_at<=timedelta(minutes=5):
                                        executable_sides.add((bookmaker,selection))
                                    identity = quote_identity(bookmaker,key,selection,line)
                                    existing = await session.scalar(select(MarketOdds).where(MarketOdds.fixture_id == fixture.id,
                                        MarketOdds.identity == identity).order_by(MarketOdds.source_at.desc()).limit(1))
                                    if existing and aware(existing.source_at) >= source_at:
                                        continue
                                    q = implied(price)
                                    if existing and (existing.decimal_odds != price):
                                        dirty(fixture, "Market price changed; eight gates require re-evaluation")
                                        if bookmaker == "pinnacle" and abs(q-existing.implied_probability) >= SHARP_MOVEMENT:
                                            reevaluate.add(fixture.id)
                                    session.add(MarketOdds(fixture_id=fixture.id, bookmaker=bookmaker, market=key, selection=selection,
                                        line=line, decimal_odds=price, implied_probability=q, source_at=source_at, identity=identity))
                                    fixture.updated_at = now()
                                except (ValueError,KeyError,TypeError):
                                    log.warning("Invalid odds discarded for %s", fixture.id)
                    execution_present=any({(book,fixture.home),(book,fixture.away)}<=executable_sides for book in ("playnow","bclc"))
                    if fixture.metrics.get("execution_source_present")!=execution_present:
                        dirty(fixture,"Execution source availability changed")
                    fixture.metrics={**fixture.metrics,"execution_source_present":execution_present,"execution_verified_at":now().isoformat()}
                except (KeyError,ValueError,TypeError) as exc:
                    log.warning("Odds payload structure changed: %s", type(exc).__name__)
            await session.commit()
    return reevaluate

async def ingest_results():
    async with db.Session() as session:
        fixtures = (await session.scalars(select(Fixture).where(Fixture.id.like("nhl:%"), Fixture.commence_time < now(),
            Fixture.commence_time > now()-timedelta(days=3), Fixture.final_home_win.is_(None)).limit(12))).all()
        for fixture in fixtures:
            payload = await providers.nhl_game(fixture.id.split(":",1)[1])
            if payload.get("gameState") not in {"OFF","FINAL"}:
                continue
            try:
                h, a = payload["homeTeam"]["score"], payload["awayTeam"]["score"]
                if h == a:
                    continue
                fixture.final_home_win = h > a
                snapshot = await session.get(Snapshot, fixture.id)
                if snapshot and snapshot.baseline_home_probability is not None:
                    snapshot.final_home_win = fixture.final_home_win
                    predicted = snapshot.prediction_home_probability if snapshot.prediction_home_probability is not None else snapshot.baseline_home_probability
                    snapshot.brier = (predicted-decimal(int(h>a)))**2
            except (KeyError, TypeError):
                log.warning("NHL result payload changed for %s", fixture.id)
        await session.commit()
    for sport in providers.ESPORTS:
        if sport not in settings.active_sports:continue
        async with db.Session() as session:
            unresolved=(await session.scalars(select(Fixture).where(Fixture.sport==sport,Fixture.commence_time<now(),
                Fixture.commence_time>now()-timedelta(days=3),Fixture.final_home_win.is_(None)).limit(50))).all()
        if not unresolved:
            continue
        past={str(row["id"]):row for row in await providers.esports_matches(sport,past=True)}
        async with db.Session.begin() as session:
            for fixture in unresolved:
                row=past.get(fixture.id.split(":",1)[-1])
                winner=row.get("winner_id") if row else None
                home_id=fixture.metrics.get("home_team_id")
                away_id=fixture.metrics.get("away_team_id")
                if winner not in {home_id,away_id} or not winner or not row.get("end_at") or aware(row["end_at"])>now():
                    continue
                current=await session.get(Fixture,fixture.id)
                current.final_home_win=winner==home_id
                snapshot=await session.get(Snapshot,fixture.id)
                if snapshot and snapshot.baseline_home_probability is not None:
                    snapshot.final_home_win=winner==home_id
                    p=snapshot.prediction_home_probability if snapshot.prediction_home_probability is not None else snapshot.baseline_home_probability
                    snapshot.brier=(p-decimal(int(winner==home_id)))**2
