"""Offline data admission tests; never imports the app or contacts a provider.

These aggregates are descriptive/reconstructed research, not saved historical
pregame observations, normalized model factors, approved predictions or bets.
"""
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/nhl-low-cost-provider-research"
OUTPUT = SOURCE / "moneypuck-offline-test"
sys.path.insert(0, str(ROOT / "backend"))
from app.nhl_data import (csv_rows, number, validate_identity, validate_team, validate_goalie, rolling, pair_checks, goalie_checks, nhl_checks)

SEASON = 2026
TARGET_DATE = date(2026, 10, 13)
MAX_ROWS = 350_000
MAX_PARSE_SECONDS = 45
SITUATIONS = {"all", "5on5", "5on4", "4on5", "other"}
TEAM_FIELDS = {"gameId", "season", "playerTeam", "opposingTeam", "home_or_away",
               "gameDate", "situation", "xGoalsFor", "xGoalsAgainst",
               "goalsFor", "goalsAgainst", "xGoalsPercentage", "iceTime", "playoffGame"}
GOALIE_FIELDS = {"playerId", "name", "gameId", "season", "playerTeam", "opposingTeam",
                 "home_or_away", "gameDate", "situation", "icetime", "xGoals", "goals"}




















def summary_checks(summaries, rows):
    groups = defaultdict(list)
    for row in rows:
        if row["situation"] == "5on5" and row["playoffGame"] == "0":
            groups[row["playerTeam"]].append(row)
    aligned, mismatched, failures = [], [], []
    for summary in summaries:
        if summary["season"] != str(SEASON) or summary["situation"] != "5on5":
            continue
        team = summary["team"]
        group = groups.get(team, [])
        count = int(number(summary["games_played"], integer=True))
        if count != len(group):
            mismatched.append({"team": team, "archive_games": len(group), "summary_games": count})
            continue
        dx = sum((number(r["xGoalsFor"]) for r in group), Decimal(0)) - number(summary["xGoalsFor"])
        da = sum((number(r["xGoalsAgainst"]) for r in group), Decimal(0)) - number(summary["xGoalsAgainst"])
        # Game values are rounded to .001, season totals to .01. Worst-case
        # accumulation bound; do not apply it to different game-count snapshots.
        tolerance = Decimal("0.005") + len(group) * Decimal("0.0005")
        if abs(dx) > tolerance or abs(da) > tolerance:
            failures.append({"team": team, "error": "Matched-sample season xG totals disagree"})
        aligned.append({"team": team, "games": count, "xgf_delta": str(dx), "xga_delta": str(da)})
    return {"aligned_teams": aligned, "different_snapshot_teams": mismatched, "failures": failures,
            "admission": "Do not mix season totals with game history at different coverage cutoffs"}


def audit():
    started = time.monotonic()
    csv.field_size_limit(65536)
    seasons, situations = Counter(), Counter()
    keys, current, failures = set(), [], []
    quarantined = Counter()
    quarantine_examples = []
    earliest, latest = {}, {}
    archive = OUTPUT / "all_teams.csv"
    with archive.open(encoding="utf-8-sig", newline="") as handle:
        for count, row in enumerate(csv_rows(handle, TEAM_FIELDS), 1):
            if time.monotonic() - started > MAX_PARSE_SECONDS:
                raise TimeoutError("Offline parse budget exceeded")
            try:
                season, day = validate_team(row)
            except ValueError as exc:
                issue = {"row": count, "season": row.get("season"),
                         "game_id": row.get("gameId"), "error": str(exc)}
                quarantined[(row.get("season"), str(exc))] += 1
                if len(quarantine_examples) < 10:
                    quarantine_examples.append(issue)
                if row.get("season") == str(SEASON):
                    failures.append(issue)
                continue
            key = (row["gameId"], row["playerTeam"], row["situation"])
            if key in keys:
                failures.append({"row": count, "error": "Duplicate team/game/situation"})
            keys.add(key)
            seasons[str(season)] += 1
            situations[row["situation"]] += 1
            earliest[str(season)] = min(earliest.get(str(season), day), day)
            latest[str(season)] = max(latest.get(str(season), day), day)
            if season == SEASON:
                current.append(row)
    fresh = TARGET_DATE == date(2026, 10, 14)
    goalie_archive = OUTPUT / "goalies/goalies.zip" if fresh else SOURCE / "moneypuck-goalies-2026.zip"
    with zipfile.ZipFile(goalie_archive) as archive_zip:
        members = archive_zip.infolist()
        if len(members) != 1 or not members[0].filename.endswith(".csv") or members[0].file_size > 2_000_000:
            raise ValueError("Goalie archive exceeds admission contract")
        with archive_zip.open(members[0]) as member:
            goalies = list(csv_rows(io.TextIOWrapper(member, encoding="utf-8-sig"), GOALIE_FIELDS, 20_000))
    goalie_keys = set()
    for row in goalies:
        validate_goalie(row)
        key = (row["gameId"], row["playerId"], row["situation"])
        if key in goalie_keys:
            failures.append({"key": key, "error": "Duplicate goalie game/situation"})
        goalie_keys.add(key)
    summary_path = OUTPUT / "summary/teams-summary.csv" if fresh else SOURCE / "moneypuck-teams-2026.csv"
    with summary_path.open(encoding="utf-8-sig", newline="") as handle:
        summaries = list(csv_rows(handle, {"team", "season", "situation", "games_played", "xGoalsFor", "xGoalsAgainst"}, 1000))
    teams = sorted({row["playerTeam"] for row in current})
    windows = {team: rolling(current, TARGET_DATE, team=team) for team in teams}
    players = sorted({row["playerId"] for row in goalies})
    goalie_windows = {player: rolling(goalies, TARGET_DATE, goalie=player) for player in players}
    for player, window in goalie_windows.items():
        records = [r for r in goalies if r["playerId"] == player and r["situation"] == "all"]
        last = max(records, key=lambda r: (r["gameDate"], r["gameId"]))
        window.update(player_id=player, name=last["name"], latest_team=last["playerTeam"],
                      starter_confirmed=False)
    score_path = OUTPUT / "nhl/nhl-score-2026-10-13.json" if fresh else OUTPUT / "nhl-score-2026-10-12.json"
    score = json.loads(score_path.read_text(encoding="utf-8"))
    tests = {"team_pairs": pair_checks(current), "goalie_reconciliation": goalie_checks(goalies, current),
             "official_nhl_day": nhl_checks(score, current), "season_summary": summary_checks(summaries, current)}
    errors = failures + [failure for result in tests.values() for failure in result["failures"]]
    download = json.loads((OUTPUT / "download.json").read_text(encoding="utf-8"))
    if download.get("result") != "downloaded" or archive.stat().st_size != download.get("bytes"):
        errors.append({"error": "Download provenance/size check failed"})
    digest = hashlib.sha256()
    with archive.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    if digest.hexdigest() != download.get("sha256"):
        errors.append({"error": "Archive hash does not match source observation"})
    report = {"status": "passed_current_season_offline_checks" if not errors else "failed",
              "production_rollout_approved": False, "predictive_model_approved": False,
              "historical_archive_approved": False,
              "audited_at": datetime.now(timezone.utc).isoformat(), "target_date": TARGET_DATE.isoformat(),
              "download": download, "total_rows": count, "season_rows": dict(seasons),
              "season_date_ranges": {k: [earliest[k].isoformat(), latest[k].isoformat()] for k in seasons},
              "situation_rows": dict(situations), "current_rows": len(current),
              "current_games": len({r["gameId"] for r in current}), "current_teams": len(teams),
              "goalie_rows": len(goalies), "unique_goalies": len(players), "checks": tests,
              "historical_quarantine": {"rows": sum(quarantined.values()),
                  "counts": [{"season": k[0], "reason": k[1], "rows": v} for k, v in quarantined.items()],
                  "examples": quarantine_examples,
                  "policy": "Never repair or admit historical identities by guessing; all historical model training remains unapproved"},
              "team_rolling": windows, "goalie_rolling": goalie_windows, "failures": errors,
              "elapsed_seconds": round(time.monotonic() - started, 3),
              "limitations": ["Not a confirmed-starter source", "No historical publication/observation proof",
                              "No precise daily refresh SLA verified", "One-day NHL cross-check only",
                              "Current samples may be under ten games; expose actual counts",
                              "Source xG model/version chronology must be resolved before historical model validation",
                              "Season summary and archive have different coverage cutoffs; do not merge blindly"]}
    (OUTPUT / "audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    goalie_metadata = (json.loads((OUTPUT / "goalies/download.json").read_text(encoding="utf-8")) if fresh
                       else json.loads((SOURCE / "moneypuck-sample-audit.json").read_text(encoding="utf-8"))[0])
    (OUTPUT / "rolling-statistics.json").write_text(json.dumps({"schema_version": 1, "source": "MoneyPuck.com",
        "classification": "offline_descriptive_research", "target_date": TARGET_DATE.isoformat(),
        "source_observed_at": download["observed_at"], "source_sha256": download["sha256"],
        "goalie_source_observed_at": goalie_metadata["observed_at"],
        "goalie_source_sha256": hashlib.sha256(goalie_archive.read_bytes()).hexdigest(),
        "teams": windows, "goalies": goalie_windows}, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "total_rows": count, "current_games": report["current_games"],
        "current_teams": len(teams), "failure_count": len(errors), "failure_examples": errors[:5],
        "historical_quarantine_rows": sum(quarantined.values()), "report": str(OUTPUT / "audit.json")}, indent=2))
    return report


if __name__ == "__main__":
    if "--fresh" in sys.argv:
        OUTPUT = OUTPUT / "compressed-2026-10-14"
        TARGET_DATE = date(2026, 10, 14)
    raise SystemExit(0 if audit()["status"] == "passed_current_season_offline_checks" else 1)
