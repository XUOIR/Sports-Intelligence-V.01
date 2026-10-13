import calendar
from datetime import datetime, timedelta
from .clock import aware
from .maths import decimal

FEATURE_NAMES = ("home_points_pct", "away_points_pct", "points_pct_diff", "home_season_games", "away_season_games",
    "home_recent_win_rate", "away_recent_win_rate", "recent_win_rate_diff", "home_recent_sample", "away_recent_sample",
    "home_days_rest", "away_days_rest", "rest_diff", "home_back_to_back", "away_back_to_back")
SOURCE_MAX_AGE = {"schedule": timedelta(hours=2), "standings": timedelta(hours=3), "history": timedelta(hours=26)}

def validate_source(kind: str, source_at: datetime, observed_at: datetime, anchor: datetime):
    source, observed, cutoff = aware(source_at), aware(observed_at), aware(anchor)
    if source > cutoff or observed > cutoff:
        raise ValueError(f"Post-anchor {kind} evidence rejected")
    if cutoff - source > SOURCE_MAX_AGE[kind]:
        raise ValueError(f"Stale {kind} evidence rejected")

def three_month_cutoff(anchor: datetime) -> datetime:
    anchor = aware(anchor)
    month = anchor.month - 3
    year = anchor.year
    if month < 1:
        month += 12
        year -= 1
    return anchor.replace(year=year, month=month, day=min(anchor.day, calendar.monthrange(year, month)[1]))

def eligible_history(games: list[dict], start: datetime, esports=False) -> list[dict]:
    start = aware(start)
    cutoff = three_month_cutoff(start) if esports else None
    accepted = []
    for game in games:
        ended = aware(game["ended_at"])
        began = aware(game["started_at"])
        if ended < began:
            raise ValueError("Overlapping/invalid history interval")
        if ended.date() >= start.date() or ended >= start - timedelta(minutes=30):
            continue
        if cutoff and began < cutoff:
            continue
        if type(game.get("win")) is not bool:
            raise ValueError("History outcome must be explicit")
        accepted.append(game)
    accepted.sort(key=lambda g: aware(g["ended_at"]), reverse=True)
    for previous, following in zip(accepted, accepted[1:]):
        if aware(following["ended_at"]) > aware(previous["started_at"]):
            raise ValueError("Overlapping history games rejected")
    return accepted

def frozen_vector(home: dict, away: dict, histories: dict, start: datetime) -> list[float | int]:
    start = aware(start)
    rows = []
    for side, standing in (("home", home), ("away", away)):
        games = int(standing["games"])
        points = decimal(standing["points_pct"])
        recent = eligible_history(histories[side], start)[:10]
        if games < 5 or not 0 <= points <= 1 or len(recent) < 3:
            raise ValueError("Minimum season/recent sample requirement not met")
        rest = max(0, (start.date() - aware(recent[0]["started_at"]).date()).days - 1)
        rows.append((float(points), games, sum(g["win"] for g in recent) / len(recent), len(recent), rest, int(rest == 0)))
    h, a = rows
    return [h[0], a[0], h[0]-a[0], h[1], a[1], h[2], a[2], h[2]-a[2], h[3], a[3], h[4], a[4], h[4]-a[4], h[5], a[5]]
