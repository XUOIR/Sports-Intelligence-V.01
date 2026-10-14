"""Validated MoneyPuck data primitives. No network, configuration or database imports."""
from collections import Counter, defaultdict
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re

SEASON = 2026
MAX_ROWS = 350_000
SITUATIONS = {"all", "5on5", "5on4", "4on5", "other"}
TEAM_FIELDS = {"gameId", "season", "playerTeam", "opposingTeam", "home_or_away", "gameDate", "situation", "xGoalsFor", "xGoalsAgainst", "goalsFor", "goalsAgainst", "xGoalsPercentage", "iceTime", "playoffGame"}
GOALIE_FIELDS = {"playerId", "name", "gameId", "season", "playerTeam", "opposingTeam", "home_or_away", "gameDate", "situation", "icetime", "xGoals", "goals"}

def csv_rows(handle, required, maximum=MAX_ROWS):
    reader = csv.reader(handle)
    header = next(reader, None)
    if not header or not required.issubset(header):
        raise ValueError("Missing required CSV header")
    counts = Counter(header)
    if any(n > 1 and key != "team" for key, n in counts.items()):
        raise ValueError("Ambiguous duplicate CSV header")
    for number, values in enumerate(reader, 1):
        if number > maximum:
            raise ValueError("CSV row budget exceeded")
        if len(values) != len(header):
            raise ValueError(f"Changed CSV row width at row {number}")
        # The published season summary repeats `team`. Never silently overwrite
        # contradictory values when reconciling that separate reference file.
        if counts["team"] > 1 and len({v for k, v in zip(header, values) if k == "team"}) != 1:
            raise ValueError("Conflicting repeated team columns")
        yield dict(zip(header, values))


def number(value, integer=False):
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Invalid numeric statistic") from None
    if not parsed.is_finite() or parsed < 0 or (integer and parsed != parsed.to_integral_value()):
        raise ValueError("Invalid numeric statistic")
    return parsed


def validate_identity(row):
    season = int(row["season"])
    if not 2007 <= season <= SEASON:
        raise ValueError("Unexpected season")
    gid = row["gameId"]
    if not re.fullmatch(r"\d{10}", gid) or not gid.startswith(str(season)) or gid[4:6] not in {"02", "03"}:
        raise ValueError("Invalid season/game identity")
    day = datetime.strptime(row["gameDate"], "%Y%m%d").date()
    if not date(season, 7, 1) <= day < date(season + 2, 1, 1):
        raise ValueError("Game date outside season interval")
    if row["situation"] not in SITUATIONS or row["home_or_away"] not in {"HOME", "AWAY"}:
        raise ValueError("Unknown situation or venue side")
    for field in ("playerTeam", "opposingTeam"):
        if not re.fullmatch(r"[A-Z.]{2,4}", row[field]):
            raise ValueError("Invalid team identity")
    if row["playerTeam"] == row["opposingTeam"]:
        raise ValueError("Identical opposing teams")
    return season, day


def validate_team(row):
    season, day = validate_identity(row)
    if row["playoffGame"] not in {"0", "1"} or (row["playoffGame"] == "1") != (row["gameId"][4:6] == "03"):
        raise ValueError("Playoff flag disagrees with game ID")
    for field in ("xGoalsFor", "xGoalsAgainst", "iceTime"):
        number(row[field])
    for field in ("goalsFor", "goalsAgainst"):
        number(row[field], integer=True)
    share = number(row["xGoalsPercentage"])
    if share > 1:
        raise ValueError("xG share outside 0-1")
    xf, xa = number(row["xGoalsFor"]), number(row["xGoalsAgainst"])
    # Source values have three-decimal xG and four-decimal shares. Allow bounded
    # display rounding, rather than demanding binary-float equality.
    if row["situation"] == "5on5" and xf + xa and abs(share - xf / (xf + xa)) > Decimal("0.0002"):
        raise ValueError("5v5 xG share does not reconcile")
    return season, day


def validate_goalie(row):
    season, day = validate_identity(row)
    if not re.fullmatch(r"\d{7}", row["playerId"]) or not row["name"].strip():
        raise ValueError("Invalid goalie identity")
    number(row["icetime"])
    number(row["xGoals"])
    number(row["goals"], integer=True)
    return season, day


def rolling(rows, target, *, team=None, goalie=None, season=SEASON, limit=10, minimum=3):
    """Sum eligible game numerators; never average per-game percentages.

    Conservative date-only admission excludes the entire target day. For goalie
    totals use only `all`, not all plus strength splits. Do not silently skip a
    malformed eligible game to reach a desired sample size.
    """
    if not isinstance(target, date) or isinstance(target, datetime):
        raise ValueError("A target calendar date is required")
    if (team is None) == (goalie is None) or not 1 <= minimum <= limit <= 10:
        raise ValueError("Invalid rolling-window request")
    eligible = []
    seen = set()
    for row in rows:
        if row["season"] != str(season):
            continue
        if team is not None and (row["playerTeam"] != team or row["situation"] != "5on5"):
            continue
        if goalie is not None and (row["playerId"] != str(goalie) or row["situation"] != "all"):
            continue
        _, day = validate_team(row) if team is not None else validate_goalie(row)
        if day >= target:
            continue
        if row["gameId"][4:6] != "02":
            continue
        if row["gameId"] in seen:
            raise ValueError("Duplicate game in rolling window")
        seen.add(row["gameId"])
        if number(row["iceTime"] if team is not None else row["icetime"]) <= 0:
            raise ValueError("Eligible game lacks meaningful ice time")
        eligible.append((day, row["gameId"], row))
    chosen = sorted(eligible, reverse=True)[:limit]
    result = {"status": "available" if len(chosen) >= minimum else "insufficient_sample",
              "sample_games": len(chosen), "requested_games": limit,
              "game_ids": [gid for _, gid, _ in chosen],
              "latest_game_date": chosen[0][0].isoformat() if chosen else None,
              "target_date": target.isoformat(), "season": season,
              "historical_observation_verified": False}
    if result["status"] != "available":
        return result
    selected = [row for _, _, row in chosen]
    if team is not None:
        xf = sum((number(row["xGoalsFor"]) for row in selected), Decimal(0))
        xa = sum((number(row["xGoalsAgainst"]) for row in selected), Decimal(0))
        ice = sum((number(row["iceTime"]) for row in selected), Decimal(0))
        if xf + xa == 0:
            result["status"] = "undefined_xg_share"
            return result
        result.update(team=team, situation="5on5", xgf=str(xf), xga=str(xa),
                      xg_share=str(xf / (xf + xa)),
                      xgf_per_60=str(xf * 3600 / ice), xga_per_60=str(xa * 3600 / ice))
    else:
        xga = sum((number(row["xGoals"]) for row in selected), Decimal(0))
        goals = sum((number(row["goals"]) for row in selected), Decimal(0))
        result.update(player_id=str(goalie), situation="all", xga=str(xga),
                      goals_against=str(goals), gsax=str(xga - goals))
    return result


def pair_checks(rows):
    lookup = {(r["gameId"], r["playerTeam"], r["situation"]): r for r in rows}
    inverse = {"5on4": "4on5", "4on5": "5on4", "all": "all", "5on5": "5on5", "other": "other"}
    groups = defaultdict(list)
    for row in rows:
        groups[(row["gameId"], row["situation"])].append(row)
    failures = []
    for key, pair in groups.items():
        if len(pair) != 2:
            failures.append({"key": key, "error": "Expected both teams exactly once"})
            continue
        a = pair[0]
        # A team's power-play events are its opponent's penalty-kill events.
        b = lookup.get((a["gameId"], a["opposingTeam"], inverse[a["situation"]]))
        if b is None:
            failures.append({"key": key, "error": "Missing opposing strength situation"})
            continue
        if (a["playerTeam"] != b["opposingTeam"] or b["playerTeam"] != a["opposingTeam"]
                or a["home_or_away"] == b["home_or_away"] or a["gameDate"] != b["gameDate"]
                or a["playoffGame"] != b["playoffGame"]
                or number(a["xGoalsFor"]) != number(b["xGoalsAgainst"])
                or number(a["xGoalsAgainst"]) != number(b["xGoalsFor"])
                or number(a["goalsFor"]) != number(b["goalsAgainst"])
                or number(a["goalsAgainst"]) != number(b["goalsFor"])):
            failures.append({"key": key, "error": "Opposing team records disagree"})
    return {"paired_game_situations": len(groups), "failures": failures}


def goalie_checks(goalies, teams):
    lookup = {(r["gameId"], r["playerTeam"], r["situation"]): r for r in teams}
    groups = defaultdict(list)
    for row in goalies:
        groups[(row["gameId"], row["playerTeam"], row["situation"])].append(row)
    failures = []
    differences = Counter()
    for key, players in groups.items():
        team = lookup.get(key)
        if not team:
            failures.append({"key": key, "error": "Goalie game lacks team reference"})
            continue
        if any(r["opposingTeam"] != team["opposingTeam"] or r["gameDate"] != team["gameDate"]
               or r["home_or_away"] != team["home_or_away"] for r in players):
            failures.append({"key": key, "error": "Goalie identity disagrees with team"})
        xga = sum((number(r["xGoals"]) for r in players), Decimal(0))
        goals = sum((number(r["goals"]) for r in players), Decimal(0))
        dx, dg = number(team["xGoalsAgainst"]) - xga, number(team["goalsAgainst"]) - goals
        if dg < 0 or dx < Decimal("-0.002"):
            failures.append({"key": key, "error": "Goalie totals exceed team totals"})
        if abs(dx) > Decimal("0.002") or dg:
            differences[key[2]] += 1
            if key[2] == "5on5":
                failures.append({"key": key, "error": "5v5 goalie totals do not reconcile"})
    for key, team in lookup.items():
        if key[2] == "5on5" and number(team["iceTime"]) > 0 and key not in groups:
            failures.append({"key": key, "error": "Missing 5v5 goalie record"})
    return {"goalie_team_situation_groups": len(groups), "failures": failures,
            "team_minus_goalie_differences": dict(differences),
            "note": "All/other differences may include empty-net exposure; do not replace goalie xGA with team xGA."}


def nhl_checks(payload, rows):
    lookup = {(r["gameId"], r["playerTeam"]): r for r in rows if r["situation"] == "all"}
    failures, completed = [], []
    for game in payload["games"]:
        if game["gameState"] not in {"OFF", "FINAL"} or game["gameType"] != 2:
            continue
        gid = str(game["id"])
        completed.append(gid)
        shootout = game.get("gameOutcome", {}).get("lastPeriodType") == "SO"
        winner = "homeTeam" if game["homeTeam"]["score"] > game["awayTeam"]["score"] else "awayTeam"
        for side in ("homeTeam", "awayTeam"):
            team = game[side]
            row = lookup.get((gid, team["abbrev"]))
            if not row or row["gameDate"] != game["gameDate"].replace("-", ""):
                failures.append({"game_id": gid, "error": "Missing or mismatched completed NHL team game"})
                continue
            expected_goals = team["score"] - int(shootout and side == winner)
            if number(row["goalsFor"]) != expected_goals:
                failures.append({"game_id": gid, "team": team["abbrev"], "error": "Final goals disagree"})
    if not completed:
        failures.append({"error": "No completed NHL game verified"})
    return {"verification_date": payload["currentDate"], "completed_games": len(completed),
            "game_ids": completed, "failures": failures,
            "scope": "One completed day only; not full-season completeness proof"}

