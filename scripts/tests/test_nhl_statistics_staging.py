from copy import deepcopy
import sqlite3
import pytest
from scripts.stage_nhl_statistics import stage, validate_bundle


def bundle():
    window = {"status": "available", "sample_games": 3, "requested_games": 10,
              "game_ids": ["2026020003", "2026020002", "2026020001"],
              "latest_game_date": "2026-10-03", "target_date": "2026-10-13", "season": 2026,
              "historical_observation_verified": False}
    team = {**window, "team": "TOR", "situation": "5on5", "xgf": "3", "xga": "3",
            "xg_share": "0.5", "xgf_per_60": "2", "xga_per_60": "2"}
    goalie = {**window, "player_id": "8470000", "name": "Test goalie", "latest_team": "TOR",
              "starter_confirmed": False, "situation": "all", "xga": "3", "goals_against": "4", "gsax": "-1"}
    return {"schema_version": 1, "source": "MoneyPuck.com", "classification": "offline_descriptive_research",
            "target_date": "2026-10-13", "source_observed_at": "2026-10-14T05:37:12+00:00",
            "goalie_source_observed_at": "2026-10-14T04:15:54+00:00",
            "source_sha256": "a" * 64, "goalie_source_sha256": "b" * 64,
            "teams": {"TOR": team}, "goalies": {"8470000": goalie}}


def test_idempotent_import_preserves_provenance_and_does_not_duplicate_rows(tmp_path):
    path = tmp_path / "isolated.sqlite3"
    first = stage(bundle(), path)
    second = stage(bundle(), path)
    assert first["status"] == "imported" and first["rows_written"] == 2
    assert second["status"] == "reused" and second["rows_written"] == 0
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM source_batches").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM statistics").fetchone()[0] == 2
        assert "offline_descriptive_research" in connection.execute("SELECT provenance FROM source_batches").fetchone()[0]


@pytest.mark.parametrize("fault", ["nan", "wrong_share", "future_game", "backdated_observation_claim", "fake_confirmation", "wrong_gsax", "duplicate_game", "fake_available", "missing_hash", "invented_missing_stat"])
def test_failed_admission_keeps_previous_valid_cache(fault, tmp_path):
    path = tmp_path / "isolated.sqlite3"
    previous = stage(bundle(), path)
    changed = deepcopy(bundle())
    team = changed["teams"]["TOR"]
    goalie = changed["goalies"]["8470000"]
    if fault == "nan": team["xgf"] = "NaN"
    if fault == "wrong_share": team["xg_share"] = ".99"
    if fault == "future_game": team["latest_game_date"] = changed["target_date"]
    if fault == "backdated_observation_claim": team["historical_observation_verified"] = True
    if fault == "fake_confirmation": goalie["starter_confirmed"] = True
    if fault == "wrong_gsax": goalie["gsax"] = "100"
    if fault == "duplicate_game": team["game_ids"][0] = team["game_ids"][1]
    if fault == "fake_available": team["sample_games"] = 2; team["game_ids"] = team["game_ids"][:2]
    if fault == "missing_hash": changed["source_sha256"] = ""
    if fault == "invented_missing_stat": goalie["status"] = "insufficient_sample"; goalie["sample_games"] = 2; goalie["game_ids"] = goalie["game_ids"][:2]
    with pytest.raises(ValueError): stage(changed, path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT id FROM source_batches").fetchall() == [(previous["batch_id"],)]
        assert connection.execute("SELECT count(*) FROM statistics").fetchone()[0] == 2


def test_unknown_schema_or_oversized_entity_collection_is_rejected():
    changed = bundle(); changed["schema_version"] = 99
    with pytest.raises(ValueError): validate_bundle(changed)
    changed = bundle(); changed["teams"] = {str(i): changed["teams"]["TOR"] for i in range(41)}
    with pytest.raises(ValueError): validate_bundle(changed)
