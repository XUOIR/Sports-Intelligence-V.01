from decimal import Decimal
import hashlib
import json

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

def baseline_digest(sport):
    from .features import FEATURE_NAMES
    from .nhl_history import HISTORY_CONTRACT
    weights=NHL_WEIGHTS if sport=='NHL' else CS2_WEIGHTS if sport=='CS2' else {}
    contract={'version':MODEL_VERSION,'weights':weights,
        'logit_scale':BASELINE_LOGIT_SCALE,'features':FEATURE_NAMES,'anchor_seconds':1800}
    if sport=='NHL':contract['history_contract']=HISTORY_CONTRACT
    return hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest()
