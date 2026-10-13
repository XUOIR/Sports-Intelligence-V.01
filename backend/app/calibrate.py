"""Offline calibration; source JSON must contain genuinely frozen, outcome-labeled records."""
import argparse
import asyncio
import json
import hashlib
from pathlib import Path
from . import db
from .clock import aware
from .models import ModelValidation
from .model_config import MODEL_VERSION
from .maths import calibrated, decimal
from .maths import baseline
from .features import validate_source,frozen_vector
from .validation import chronological_split, fit_platt, brier

def validate(records):
    ids = set()
    for r in records:
        if r["fixture_id"] in ids:
            raise ValueError("Duplicate fixture in validation data")
        ids.add(r["fixture_id"])
        if r["model_version"] != MODEL_VERSION or len(r["vector"]) != 15:
            raise ValueError("Incompatible frozen model/vector")
        if not 0 < decimal(r["probability"]) < 1 or type(r["outcome"]) is not int or r["outcome"] not in (0,1):
            raise ValueError("Invalid model probability/outcome")
        if aware(r["collected_at"]) < aware(r["anchor_at"]) or (aware(r["collected_at"])-aware(r["anchor_at"])).total_seconds() > 5:
            raise ValueError("Snapshot missed its exact anchor")
        if (aware(r["commence_time"])-aware(r["anchor_at"])).total_seconds() != 1800:
            raise ValueError("Invalid anchor horizon")
        for kind in ('schedule','standings','history'):
            source=r['sources'][kind]
            validate_source(kind,source['source_at'],source['observed_at'],r['anchor_at'])
        standings=r['sources']['standings']['payload']
        recomputed=frozen_vector(standings['home'],standings['away'],r['sources']['history']['payload'],r['commence_time'])
        if recomputed!=r['vector'] or baseline(r['sport'],r['factors'])!=decimal(r['probability']):
            raise ValueError('Frozen vector/probability does not match its source evidence')

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input",type=Path)
    parser.add_argument("--sport",choices=["NHL","CS2"],required=True)
    parser.add_argument("--approve",action="store_true",help="Explicitly publish passing model validation to database")
    args = parser.parse_args()
    if args.input.stat().st_size > 20_000_000:
        raise ValueError("Validation file too large")
    records = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(records,list) or len(records)>100000:
        raise ValueError("Invalid validation input")
    validate(records)
    if any(r["sport"] != args.sport for r in records):
        raise ValueError("Cross-sport calibration prohibited")
    training, calibration, test, embargoes = chronological_split(records)
    # Initial deterministic weights are frozen; training evaluates baseline, calibration fits Platt.
    params = fit_platt(calibration)
    test_score = brier([calibrated(r["probability"],params) for r in test],[r["outcome"] for r in test])
    prevalence = sum(r["outcome"] for r in training)/len(training)
    reference = brier([prevalence]*len(test),[r["outcome"] for r in test])
    report = {"baseline_version":MODEL_VERSION,"train_records":len(training),"calibration_records":len(calibration),"test_records":len(test),
        "embargo_dates":[str(d) for d in embargoes],"train_brier":str(brier([r["probability"] for r in training],[r["outcome"] for r in training])),
        "test_brier":str(test_score),"reference_brier":str(reference),"test_through":max(aware(r["commence_time"]) for r in test).isoformat(),
        "passing":test_score < reference}
    print(json.dumps(report,indent=2))
    if args.approve:
        if not report["passing"]:
            raise ValueError("Model did not beat training-prevalence reference on untouched test set")
        db.configure_database()
        version = hashlib.sha256(args.input.read_bytes()+json.dumps(params,sort_keys=True).encode()).hexdigest()[:32]
        async with db.Session.begin() as session:
            if not await session.get(ModelValidation,version):
                session.add(ModelValidation(version=version,sport=args.sport,parameters=params,report=report,approved=True))
        await db.engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
