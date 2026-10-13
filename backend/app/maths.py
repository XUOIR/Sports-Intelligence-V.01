import math
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from .model_config import KELLY_MULTIPLIER, MAX_BANKROLL_FRACTION, NHL_WEIGHTS, CS2_WEIGHTS, BASELINE_LOGIT_SCALE

def decimal(value) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Invalid numeric value") from None
    if not result.is_finite():
        raise ValueError("Finite number required")
    return result

def money(value) -> Decimal:
    return decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def parse_odds(value, format: str = "auto") -> Decimal:
    raw = str(value).strip()
    number = decimal(raw)
    american = format == "american" or (format == "auto" and (raw.startswith(("+", "-")) or abs(number) >= 100))
    if format not in {"auto", "american", "decimal"}:
        raise ValueError("Unknown odds format")
    if american:
        if abs(number) < 100:
            raise ValueError("American odds must be >= +100 or <= -100")
        number = 1 + (number / 100 if number > 0 else 100 / abs(number))
    if number <= Decimal("1.0001") or number > 10000:
        raise ValueError("Odds outside supported range")
    return number.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

def implied(odds) -> Decimal:
    return (Decimal(1) / parse_odds(odds, "decimal")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

def stake(probability, odds, bankroll, available=None) -> Decimal:
    p, d, bank = decimal(probability), parse_odds(odds, "decimal"), decimal(bankroll)
    if not 0 <= p <= 1 or bank < 0:
        raise ValueError("Invalid probability or bankroll")
    fraction = max(Decimal(0), min(MAX_BANKROLL_FRACTION, KELLY_MULTIPLIER * (d * p - 1) / (d - 1)))
    cap = bank * MAX_BANKROLL_FRACTION
    amount = min(bank * fraction, cap, bank if available is None else max(Decimal(0), decimal(available)))
    rounded = money(amount)
    # HALF_UP must never round a safety cap upward by half a cent.
    if rounded > min(cap, amount):
        rounded -= Decimal("0.01")
    return max(Decimal(0), rounded)

def profit(outcome: str, odds, amount) -> Decimal:
    if outcome == "WIN":
        return money(decimal(amount) * (parse_odds(odds, "decimal") - 1))
    return -money(amount) if outcome == "LOSS" else Decimal("0.00")

def roi(net, settled_stakes) -> Decimal:
    total = decimal(settled_stakes)
    return money(decimal(net) / total * 100) if total > 0 else Decimal("0.00")

def baseline(sport: str, factors: dict) -> Decimal:
    weights = NHL_WEIGHTS if sport == "NHL" else CS2_WEIGHTS if sport == "CS2" else None
    if weights is None:
        raise ValueError("No validated baseline for this sport")
    if set(factors) != set(weights):
        raise ValueError("Complete factor evidence required")
    values = {k: float(decimal(v)) for k, v in factors.items()}
    if any(not -1 <= v <= 1 for v in values.values()):
        raise ValueError("Factors must be normalized differences in [-1, 1]")
    score = sum(weights[k] * values[k] for k in weights)
    return decimal(1 / (1 + math.exp(-BASELINE_LOGIT_SCALE * score))).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

def calibrated(p, parameters: dict) -> Decimal:
    p = float(decimal(p))
    if not 0 < p < 1:
        raise ValueError("Probability must be inside (0, 1)")
    z = parameters["slope"] * math.log(p / (1-p)) + parameters["intercept"]
    return decimal(1 / (1 + math.exp(-max(-30, min(30, z))))).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
