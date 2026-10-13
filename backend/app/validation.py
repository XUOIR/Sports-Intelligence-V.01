import math
from decimal import Decimal
from .clock import aware
from .maths import decimal

def chronological_split(records: list[dict]):
    dates = sorted({aware(r["commence_time"]).date() for r in records})
    a, b = math.floor(.60 * len(dates)), math.floor(.80 * len(dates))
    if a >= b or b >= len(dates):
        raise ValueError("Insufficient distinct Pacific dates")
    train_dates, calibration_dates, test_dates = set(dates[:a]), set(dates[a+1:b]), set(dates[b+1:])
    partitions = [[r for r in records if aware(r["commence_time"]).date() in selected]
        for selected in (train_dates, calibration_dates, test_dates)]
    for part, minimum in zip(partitions, (300, 100, 100)):
        if len(part) < minimum:
            raise ValueError(f"Chronological partition requires at least {minimum} records")
    return (*partitions, [dates[a], dates[b]])

def brier(probabilities, outcomes) -> Decimal:
    if not probabilities or len(probabilities) != len(outcomes):
        raise ValueError("Paired nonempty probability/outcome arrays required")
    total = Decimal(0)
    for p, y in zip(probabilities, outcomes):
        p = decimal(p)
        if not 0 <= p <= 1 or y not in (0, 1) or type(y) not in (bool, int):
            raise ValueError("Invalid Brier input")
        total += (p - Decimal(int(y))) ** 2
    return total / len(probabilities)

def fit_platt(records: list[dict]) -> dict:
    # Bounded optimizer; fit only calibration partition, never test outcomes.
    if len({int(r["outcome"]) for r in records}) != 2:
        raise ValueError("Calibration needs both outcome classes")
    x = [math.log(float(r["probability"]) / (1-float(r["probability"]))) for r in records]
    y = [int(r["outcome"]) for r in records]
    slope, intercept = 1.0, 0.0
    for _ in range(1500):
        pred = [1/(1+math.exp(-max(-30, min(30, slope*v+intercept)))) for v in x]
        slope = max(0.01, min(10, slope - .05 * (sum((p-t)*v for p,t,v in zip(pred,y,x))/len(y)+.001*slope)))
        intercept = max(-10, min(10, intercept - .05*sum(p-t for p,t in zip(pred,y))/len(y)))
    return {"slope": slope, "intercept": intercept}
