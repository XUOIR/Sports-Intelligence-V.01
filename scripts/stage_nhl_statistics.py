"""Validate and import tested NHL statistics into an isolated local SQLite cache.

This is an offline rehearsal. No application credentials/config/database imports,
provider requests, production writes, model approvals or recommendations.
"""
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/nhl-low-cost-provider-research/moneypuck-offline-test"


def numeric(value, *, signed=False):
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Malformed derived statistic") from None
    if not result.is_finite() or (not signed and result < 0):
        raise ValueError("Unusable derived statistic")
    return result


def validate_bundle(bundle):
    if (bundle.get("schema_version") != 1 or bundle.get("source") != "MoneyPuck.com"
            or bundle.get("classification") != "offline_descriptive_research"):
        raise ValueError("Unrecognized cache contract")
    target = date.fromisoformat(bundle["target_date"])
    for field in ("source_observed_at", "goalie_source_observed_at"):
        timestamp = datetime.fromisoformat(bundle[field])
        if timestamp.tzinfo is None or timestamp.utcoffset() is None or timestamp > datetime.now(timezone.utc):
            raise ValueError("Invalid source observation time")
    for field in ("source_sha256", "goalie_source_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", bundle[field]):
            raise ValueError("Source fingerprint missing")
    for kind, maximum in (("teams", 40), ("goalies", 128)):
        records = bundle.get(kind)
        if not isinstance(records, dict) or not 1 <= len(records) <= maximum:
            raise ValueError("Cache entity budget exceeded")
        for key, row in records.items():
            if not isinstance(row, dict) or row.get("historical_observation_verified") is not False:
                raise ValueError("Historical observation claim rejected")
            sample = row.get("sample_games")
            if type(sample) is not int or not 0 <= sample <= 10 or row.get("target_date") != target.isoformat():
                raise ValueError("Invalid sample window")
            ids = row.get("game_ids")
            if not isinstance(ids, list) or len(ids) != sample or len(set(ids)) != sample:
                raise ValueError("Duplicate/missing sample game")
            if any(not isinstance(gid, str) or not re.fullmatch(r"202602\d{4}", gid) for gid in ids):
                raise ValueError("Invalid sample game identity")
            if row.get("latest_game_date") and date.fromisoformat(row["latest_game_date"]) >= target:
                raise ValueError("Target-day or future results leaked into cache")
            status = row.get("status")
            if status not in {"available", "insufficient_sample", "undefined_xg_share"}:
                raise ValueError("Unknown statistic status")
            if status == "available" and sample < 3:
                raise ValueError("Available statistic has insufficient sample")
            if status == "insufficient_sample" and sample >= 3:
                raise ValueError("Inconsistent insufficient-sample status")
            if kind == "goalies":
                if row.get("player_id") != key or row.get("starter_confirmed") is not False:
                    raise ValueError("Goalie identity or confirmation is invalid")
                if status != "available" and any(field in row for field in ("gsax", "xga", "goals_against")):
                    raise ValueError("Unavailable goalie exposes invented statistics")
                if status == "available":
                    expected = numeric(row["xga"]) - numeric(row["goals_against"])
                    if numeric(row["gsax"], signed=True) != expected or row.get("situation") != "all":
                        raise ValueError("GSAx derivation or situation mismatch")
            else:
                if status != "available" and any(field in row for field in ("xgf", "xga", "xg_share")):
                    raise ValueError("Unavailable team exposes invented statistics")
                if status == "available":
                    xf, xa, share = numeric(row["xgf"]), numeric(row["xga"]), numeric(row["xg_share"])
                    if (row.get("team") != key or row.get("situation") != "5on5" or xf + xa == 0
                            or share > 1 or abs(share - xf / (xf + xa)) > Decimal("1e-24")):
                        raise ValueError("5v5 expected-goal share does not reconcile")
                    numeric(row["xgf_per_60"])
                    numeric(row["xga_per_60"])
    return bundle


def stage(bundle, database):
    validate_bundle(bundle)  # Fail before opening/writing the isolated cache.
    canonical = json.dumps(bundle, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        with connection:
            connection.execute("CREATE TABLE IF NOT EXISTS source_batches (id TEXT PRIMARY KEY, target_date TEXT NOT NULL, observed_at TEXT NOT NULL, provenance TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS statistics (batch_id TEXT NOT NULL REFERENCES source_batches(id), kind TEXT NOT NULL, entity_id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(batch_id,kind,entity_id))")
            exists = connection.execute("SELECT 1 FROM source_batches WHERE id=?", (fingerprint,)).fetchone()
            if exists:
                return {"status": "reused", "batch_id": fingerprint, "rows_written": 0}
            provenance = {k: v for k, v in bundle.items() if k not in {"teams", "goalies"}}
            connection.execute("INSERT INTO source_batches VALUES (?,?,?,?)",
                (fingerprint, bundle["target_date"], bundle["source_observed_at"], json.dumps(provenance)))
            rows = [(fingerprint, kind, key, json.dumps(row)) for kind in ("teams", "goalies") for key, row in bundle[kind].items()]
            connection.executemany("INSERT INTO statistics VALUES (?,?,?,?)", rows)
    return {"status": "imported", "batch_id": fingerprint, "rows_written": len(rows)}


def main():
    if (OUTPUT / "audit.json").stat().st_size > 2_000_000 or (OUTPUT / "rolling-statistics.json").stat().st_size > 200_000:
        raise ValueError("Offline cache input exceeded byte budget")
    audit = json.loads((OUTPUT / "audit.json").read_text(encoding="utf-8"))
    if audit.get("status") != "passed_current_season_offline_checks" or audit.get("failures"):
        raise ValueError("Current-season audit has not passed")
    bundle = json.loads((OUTPUT / "rolling-statistics.json").read_text(encoding="utf-8"))
    result = stage(bundle, OUTPUT / "nhl-statistics-test.sqlite3")
    result.update(production_writes=0, paid_provider_calls=0, source="MoneyPuck.com",
        target_date=bundle["target_date"], available_team_metrics=sum(r["status"] == "available" for r in bundle["teams"].values()),
        available_goalie_metrics=sum(r["status"] == "available" for r in bundle["goalies"].values()),
        insufficient_goalie_samples=sum(r["status"] == "insufficient_sample" for r in bundle["goalies"].values()))
    (OUTPUT / "staging.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    if "--fresh" in sys.argv:
        OUTPUT = OUTPUT / "compressed-2026-10-14"
    main()
