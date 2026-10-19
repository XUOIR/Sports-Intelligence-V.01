"""Pure, frozen xG/team-goaltending paper inference. Never a release approval."""
import hashlib
import json
import math
from pathlib import Path
from .nhl_candidate_features import FEATURES

CONTRACT='nhl-xg-paper-v1'
BUNDLE=Path(__file__).with_name('data')/'nhl-xg-paper-v1.json'


def probability(bundle,values):
    if len(values)!=len(FEATURES) or any(not math.isfinite(x) for x in values):
        raise ValueError('Invalid candidate feature vector')
    fit=bundle['fit']; raw=fit['coefficients'][0]
    for value,center,scale,coefficient in zip(values,fit['center'],fit['scale'],fit['coefficients'][1:]):
        if not math.isfinite(scale) or scale<=0:raise ValueError('Invalid frozen scaling')
        raw+=(value-center)/scale*coefficient
    p=1/(1+math.exp(-max(-35.,min(35.,raw))))
    p=max(1e-9,min(1-1e-9,p))
    calibration=bundle['calibration']
    logit=math.log(p/(1-p))
    value=calibration['coefficients'][0]+calibration['coefficients'][1]*logit
    return 1/(1+math.exp(-max(-35.,min(35.,value))))


def load_bundle():
    raw=BUNDLE.read_bytes();digest=hashlib.sha256(raw).hexdigest();bundle=json.loads(raw)
    if (digest!=BUNDLE.with_suffix('.sha256').read_text().strip() or bundle.get('contract')!=CONTRACT
            or bundle.get('features')!=FEATURES or bundle.get('approved_for_wagers') is not False
            or bundle.get('mode')!='paper_only'):
        raise ValueError('Candidate bundle integrity or contract mismatch')
    expected={'nhl_candidate_features.py','nhl_candidate_model.py','nhl_candidate.py'}
    if set(bundle.get('inference_code_sha256',{}))!=expected:
        raise ValueError('Candidate inference implementation is not frozen')
    for name,expected_hash in bundle['inference_code_sha256'].items():
        raw=Path(__file__).with_name(name).read_text(encoding='utf-8').replace('\r\n','\n').encode()
        if hashlib.sha256(raw).hexdigest()!=expected_hash:
            raise ValueError('Candidate inference changed; freeze a new version before collection')
    return bundle,digest
