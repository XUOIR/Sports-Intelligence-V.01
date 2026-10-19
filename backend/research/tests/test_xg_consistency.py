"""Runtime/research consistency and bounded historical source acquisition."""
from pathlib import Path
import tempfile
import unittest
import numpy as np
from app.nhl_candidate_model import load_bundle,probability
from research.nhl_team_model import predict_logistic,calibrate
from research.moneypuck_goalies_fetch import acquire,MAX_BYTES


class Source:
    status=200
    def __init__(self,raw,status=200):self.raw=raw;self.status=status;self.headers={'Content-Length':str(len(raw))}
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,maximum):return self.raw[:maximum]


class Opener:
    def __init__(self,response):self.response=response;self.calls=0
    def open(self,*args,**kwargs):self.calls+=1;return self.response


class CandidateConsistency(unittest.TestCase):
    def test_frozen_runtime_matches_research_calibration_for_realistic_vectors(self):
        bundle,_=load_bundle()
        values=np.random.default_rng(20261019).normal(0,.2,(100,5))
        expected=calibrate(bundle['calibration'],predict_logistic(bundle['fit'],values))
        actual=[probability(bundle,list(row)) for row in values]
        np.testing.assert_allclose(actual,expected,atol=1e-12,rtol=0)

    def test_success_is_reused_only_after_matching_saved_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            opener=Opener(Source(b'PK\x03\x04test-public-archive'))
            first=acquire(directory,2025,opener)
            assert acquire(directory,2025,opener)['cache_hit'] and opener.calls==1
            Path(directory,'2025.zip').write_bytes(b'corrupt')
            with self.assertRaises(ValueError):acquire(directory,2025,opener)
            assert first['bytes']<MAX_BYTES and opener.calls==1

    def test_failed_archive_cannot_be_automatically_repeated(self):
        with tempfile.TemporaryDirectory() as directory:
            opener=Opener(Source(b'access denied',403))
            with self.assertRaises(ValueError):acquire(directory,2025,opener)
            with self.assertRaises(ValueError):acquire(directory,2025,opener)
            assert opener.calls==1


if __name__=='__main__':unittest.main()
