"""Fail-closed checks for compatibility of an approved frozen model."""
import math
from datetime import timedelta
from .clock import now, aware
from .model_config import MODEL_VERSION, baseline_digest
from .maths import decimal

def fresh_recommendation(fixture):
    try:
        metrics=fixture.metrics
        return (not fixture.dirty and aware(fixture.commence_time)>now()
            and metrics.get('recommendation_baseline_digest')==baseline_digest(fixture.sport)
            and all(fixture.gates.get(key) is True for key in ('price','personnel','form','maps_veto','other_markets','opposing_case','overlap_exposure','probability'))
            and timedelta(0)<=now()-aware(metrics['recommendation_verified_at'])<=timedelta(minutes=5)
            and timedelta(0)<=now()-aware(metrics['recommended_quote_source_at'])<=timedelta(minutes=5)
            and timedelta(0)<=now()-aware(metrics['confirmed_at'])<=timedelta(minutes=30))
    except (KeyError,TypeError,ValueError):return False

def validated_model(model,snapshot=None):
    if model is None or not model.approved:return False
    try:
        report=model.report
        if report.get('baseline_version')!=MODEL_VERSION or report.get('baseline_digest')!=baseline_digest(model.sport) or report.get('passing') is not True:return False
        if any(type(report.get(key)) is not int or report[key]<minimum for key,minimum in [('train_records',300),('calibration_records',100),('test_records',100)]):return False
        if not 0<=decimal(report['test_brier'])<decimal(report['reference_brier'])<=1:return False
        slope=float(model.parameters['slope']);intercept=float(model.parameters['intercept'])
        if not math.isfinite(slope) or not .01<=slope<=10 or not math.isfinite(intercept) or not -10<=intercept<=10:return False
        if not timedelta(0)<=now()-aware(model.created_at)<=timedelta(days=90):return False
        if snapshot is not None:
            return (snapshot.model_version==MODEL_VERSION and snapshot.baseline_home_probability is not None
                and aware(model.created_at)<=aware(snapshot.anchor_at)
                and aware(report['test_through']).date()<snapshot.game_date)
        return aware(report['test_through'])<aware(model.created_at)
    except (KeyError,TypeError,ValueError,ArithmeticError):return False
