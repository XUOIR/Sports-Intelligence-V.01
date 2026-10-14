from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import io
import json
import gzip
from pathlib import Path
import pytest

from scripts.audit_moneypuck import csv_rows, number, rolling, validate_team, pair_checks, nhl_checks
from scripts import moneypuck_test_download as download


def team_row(n=1, *, xf="1", xa="1", team="TOR", opponent="EDM", side="HOME", situation="5on5", day=None):
    return {"gameId": f"202602{n:04}", "gameDate": (day or date(2026, 10, n)).strftime("%Y%m%d"),
            "season": "2026", "playerTeam": team, "opposingTeam": opponent,
            "home_or_away": side, "situation": situation, "xGoalsFor": xf, "xGoalsAgainst": xa,
            "goalsFor": "1", "goalsAgainst": "1", "iceTime": "1800", "playoffGame": "0",
            "xGoalsPercentage": str(Decimal(xf) / (Decimal(xf) + Decimal(xa))) if Decimal(xf)+Decimal(xa) else "0"}


def goalie_row(n=1, *, xga="2", goals="1", situation="all", player="8470000"):
    row = team_row(n)
    row.update(playerId=player, name="Test goalie", situation=situation,
               icetime="3600", xGoals=xga, goals=goals)
    return row


@pytest.mark.parametrize("value", ["", "NaN", "Infinity", "-1", "unknown", None])
def test_unusable_numbers_are_rejected(value):
    with pytest.raises(ValueError):
        number(value)


def test_fractional_goal_count_is_rejected():
    with pytest.raises(ValueError):
        number("1.5", integer=True)


def test_csv_schema_and_duplicate_column_checks():
    assert list(csv_rows(io.StringIO("team,team,x\nTOR,TOR,1\n"), {"team", "x"})) == [{"team": "TOR", "x": "1"}]
    for body in ("team,team,x\nTOR,EDM,1\n", "team,x,x\nTOR,1,2\n", "team,x\nTOR,1,2\n", "team\nTOR\n"):
        with pytest.raises(ValueError):
            list(csv_rows(io.StringIO(body), {"team", "x"}))
    with pytest.raises(ValueError):
        list(csv_rows(io.StringIO("team,x\nTOR,1\nEDM,2\n"), {"team", "x"}, maximum=1))


def test_invalid_team_identity_and_playoff_flag_are_rejected():
    bad = team_row(); bad["opposingTeam"] = bad["playerTeam"]
    with pytest.raises(ValueError):
        validate_team(bad)
    bad = team_row(); bad["playoffGame"] = "1"
    with pytest.raises(ValueError):
        validate_team(bad)


def test_rolling_share_is_weighted_and_excludes_target_day_future_other_strength_and_season():
    rows = [team_row(1, xf="9", xa="1"), team_row(2, xf="1", xa="9"), team_row(3, xf="1", xa="3")]
    extras = [team_row(4, xf="99", xa="1"), team_row(5), team_row(1, xf="50", xa="1", situation="all")]
    prior = team_row(6); prior.update(season="2025", gameId="2025020001", gameDate="20251001")
    result = rolling(rows + extras + [prior], date(2026, 10, 4), team="TOR")
    assert result["sample_games"] == 3
    assert result["game_ids"] == ["2026020003", "2026020002", "2026020001"]
    assert Decimal(result["xg_share"]) == Decimal(11) / Decimal(24)
    assert Decimal(result["xg_share"]) != (Decimal(".9") + Decimal(".1") + Decimal(".25")) / 3
    assert Decimal(result["xgf_per_60"]) == Decimal(11) * 3600 / 5400
    assert result["historical_observation_verified"] is False


def test_only_latest_ten_games_are_used():
    rows = [team_row(i) for i in range(1, 13)]
    result = rolling(rows, date(2026, 10, 13), team="TOR")
    assert result["sample_games"] == 10
    assert result["game_ids"][-1] == "2026020003"


def test_missing_sample_and_zero_denom_do_not_fabricate_statistics():
    result = rolling([team_row(1), team_row(2)], date(2026, 10, 4), team="TOR")
    assert result["status"] == "insufficient_sample"
    assert "xg_share" not in result
    result = rolling([team_row(i, xf="0", xa="0") for i in range(1, 4)], date(2026, 10, 4), team="TOR")
    assert result["status"] == "undefined_xg_share"
    assert "xg_share" not in result


def test_duplicate_or_invalid_eligible_game_blocks_window():
    rows = [team_row(i) for i in range(1, 4)]
    with pytest.raises(ValueError):
        rolling(rows + [deepcopy(rows[0])], date(2026, 10, 4), team="TOR")
    rows[0]["xGoalsFor"] = "NaN"
    with pytest.raises(ValueError):
        rolling(rows, date(2026, 10, 4), team="TOR")


def test_goalie_gsax_uses_all_only_and_preserves_negative_values():
    rows = [goalie_row(1, xga="1", goals="3"), goalie_row(2), goalie_row(3),
            goalie_row(1, xga="99", goals="0", situation="5on5"), goalie_row(4, xga="99", goals="0")]
    result = rolling(rows, date(2026, 10, 4), goalie="8470000")
    assert result["sample_games"] == 3
    assert Decimal(result["gsax"]) == 0
    rows[2]["goals"] = "2"
    assert Decimal(rolling(rows, date(2026, 10, 4), goalie="8470000")["gsax"]) == -1


def test_power_play_pairs_match_opponent_penalty_kill():
    rows = [team_row(xf="2", xa="1", situation="5on4"),
            team_row(xf="1", xa="2", team="EDM", opponent="TOR", side="AWAY", situation="4on5"),
            team_row(xf="3", xa="4", situation="4on5"),
            team_row(xf="4", xa="3", team="EDM", opponent="TOR", side="AWAY", situation="5on4")]
    assert pair_checks(rows)["failures"] == []
    rows[1]["xGoalsAgainst"] = "999"
    assert pair_checks(rows)["failures"]


def test_missing_other_team_fails_pair_checks():
    assert pair_checks([team_row()])["failures"]


def test_official_scores_exclude_shootout_winner_bonus():
    payload = {"currentDate": "2026-10-01", "games": [{"id": 2026020001,
        "gameState": "OFF", "gameType": 2, "gameDate": "2026-10-01",
        "gameOutcome": {"lastPeriodType": "SO"},
        "homeTeam": {"abbrev": "TOR", "score": 2}, "awayTeam": {"abbrev": "EDM", "score": 1}}]}
    rows = [team_row(situation="all"), team_row(team="EDM", opponent="TOR", side="AWAY", situation="all")]
    assert nhl_checks(payload, rows)["failures"] == []
    payload["games"][0]["gameOutcome"]["lastPeriodType"] = "REG"
    assert nhl_checks(payload, rows)["failures"]


def test_persistent_admission_blocks_repeat_after_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(download, "OUTPUT", tmp_path)
    monkeypatch.setattr(download.sys, "argv", ["download"])
    (tmp_path / "attempt.json").write_text("{}")
    monkeypatch.setattr(download.subprocess, "run", lambda *a, **k: pytest.fail("A repeated network attempt was admitted"))
    assert download.main() == 1


def test_cache_tampering_cannot_trigger_replacement_request(monkeypatch, tmp_path):
    monkeypatch.setattr(download, "OUTPUT", tmp_path)
    monkeypatch.setattr(download.sys, "argv", ["download"])
    body = b"verified source"
    (tmp_path / "all_teams.csv").write_bytes(body)
    (tmp_path / "download.json").write_text(json.dumps({"result": "downloaded", "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}))
    monkeypatch.setattr(download.subprocess, "run", lambda *a, **k: pytest.fail("A network request was sent"))
    assert download.main() == 0
    (tmp_path / "all_teams.csv").write_bytes(b"altered")
    assert download.main() == 1


def test_hard_byte_cap_retains_previous_valid_cache(monkeypatch, tmp_path):
    class FakeResponse(io.BytesIO):
        status = 200
        headers = {}
    class FakeOpener:
        def open(self, *a, **k):
            return FakeResponse(b"12345")
    monkeypatch.setattr(download, "OUTPUT", tmp_path)
    monkeypatch.setattr(download, "MAX_BYTES", 4)
    monkeypatch.setattr(download, "build_opener", lambda *a: FakeOpener())
    (tmp_path / "all_teams.csv").write_bytes(b"previous valid cache")
    assert download.worker() == 1
    assert (tmp_path / "all_teams.csv").read_bytes() == b"previous valid cache"
    assert json.loads((tmp_path / "download.json").read_text())["result"] == "failed"


@pytest.mark.parametrize("body,expected", [(gzip.compress(b"a" * 1000), "expansion"), (gzip.compress(b"ok")[:-4], "truncated")])
def test_compressed_expansion_and_truncation_are_rejected(monkeypatch, tmp_path, body, expected):
    class FakeResponse(io.BytesIO):
        status = 200
        headers = {"Content-Encoding": "gzip"}
    class FakeOpener:
        def open(self, *a, **k): return FakeResponse(body)
    monkeypatch.setattr(download, "OUTPUT", tmp_path)
    monkeypatch.setattr(download, "MAX_BYTES", 20)
    monkeypatch.setattr(download, "build_opener", lambda *a: FakeOpener())
    (tmp_path / "all_teams.csv").write_bytes(b"previous")
    assert download.worker(compressed=True) == 1
    assert (tmp_path / "all_teams.csv").read_bytes() == b"previous"


def test_valid_gzip_has_separate_wire_and_decoded_byte_counts(monkeypatch, tmp_path):
    raw = b"test data" * 30
    body = gzip.compress(raw)
    class FakeResponse(io.BytesIO):
        status = 200
        headers = {"Content-Encoding": "gzip", "Content-Length": str(len(body))}
    class FakeOpener:
        def open(self, *a, **k): return FakeResponse(body)
    monkeypatch.setattr(download, "OUTPUT", tmp_path)
    monkeypatch.setattr(download, "build_opener", lambda *a: FakeOpener())
    assert download.worker(compressed=True) == 0
    result = json.loads((tmp_path / "download.json").read_text())
    assert result["bytes"] == len(raw) and result["wire_bytes"] == len(body)
    assert (tmp_path / "all_teams.csv").read_bytes() == raw
