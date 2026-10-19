"""Freeze a separate forward-only candidate after the declared offline comparison."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from app.nhl_candidate_model import CONTRACT
from app.nhl_candidate_features import FEATURES
from app.nhl_paper_model import load_bundle


def freeze(experiment,destination):
    experiment=Path(experiment);report=json.loads((experiment/'report.json').read_text(encoding='utf-8'))
    fitted=json.loads((experiment/'fitted_before_test.json').read_text(encoding='utf-8'))
    if not report['uncertainty_supports_progression']:
        raise ValueError('The declared candidate did not qualify for forward collection')
    base,digest=load_bundle();chosen=fitted['models']['xg_goaltending']
    bundle={'contract':CONTRACT,'features':FEATURES,'mode':'paper_only','approved_for_wagers':False,
        'created_at':datetime.now(timezone.utc).isoformat(),'base_model_sha256':digest,
        'fit':chosen['fit'],'calibration':chosen['calibration'],'research':report,
        'source_manifest_sha256':hashlib.sha256((experiment/'source_manifest.json').read_bytes()).hexdigest(),
        'collection':{'threshold':.03,'quote_max_age_seconds':300,'units':1,
            'market':'h2h_final_including_ot_so','operational_checkpoint_days':14,'operational_checkpoint_pairs':100,
            'real_money_release':'Separate validation and review required; never automatic'}}
    root=Path(__file__).resolve().parents[1]/'app'
    bundle['inference_code_sha256']={name:hashlib.sha256((root/name).read_text(encoding='utf-8').replace('\r\n','\n').encode()).hexdigest()
        for name in ('nhl_candidate_features.py','nhl_candidate_model.py','nhl_candidate.py')}
    raw=(json.dumps(bundle,indent=2,allow_nan=False)+'\n').encode();destination=Path(destination)
    with destination.open('xb') as handle:handle.write(raw)
    with destination.with_suffix('.sha256').open('x') as handle:handle.write(hashlib.sha256(raw).hexdigest()+'\n')
    return {'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'approved_for_wagers':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();print(json.dumps(freeze(args.experiment,args.output)))
