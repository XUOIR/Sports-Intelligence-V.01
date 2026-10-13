from decimal import Decimal

UNIT_VALUE_CAD = Decimal("100.00")
INITIAL_BANKROLL_CAD = Decimal("1100.00")
KELLY_MULTIPLIER = Decimal("0.25")
MAX_BANKROLL_FRACTION = Decimal("0.015")
MAX_OPEN_EXPOSURE = Decimal("0.06")
MIN_EDGE = Decimal("0.03")
SHARP_MOVEMENT = Decimal("0.0100")
MAX_LLM_RETRIES = 3
BASELINE_LOGIT_SCALE = 2.0
MODEL_VERSION = "baseline-v0.1"
NHL_WEIGHTS = {"goalie_personnel": .40, "expected_goals": .35, "rest_fatigue": .15, "venue_special_teams": .10}
CS2_WEIGHTS = {"roster": .40, "map_win_rate": .30, "recent_form": .20, "side_pistols": .10}
GATE_NAMES = ("price", "personnel", "form", "maps_veto", "other_markets", "opposing_case", "overlap_exposure", "probability")
