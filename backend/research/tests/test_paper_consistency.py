"""Ensure server inference agrees with the frozen research mathematics."""
from datetime import date, timedelta
from itertools import groupby
import unittest
import numpy as np

from app.nhl_paper_model import blank_state, apply_day, features, load_bundle, probability
from research.nhl_team_model import chronological_features, predict_logistic, calibrate


class PaperConsistency(unittest.TestCase):
    def test_forward_state_matches_chronological_features_across_utah_rename(self):
        games=[]
        for season in (2024,2025):
            for i in range(40):
                home,away=(59,10) if i%2 else (10,59)
                games.append({'id':season*1000000+20000+i, 'season':season,
                    'date':str(date(season,10,1)+timedelta(days=i*2)),
                    'home':home,'away':away,'home_win':int(i%3==0),
                    'home_hockey_goals':3 if i%3==0 else 1,'away_hockey_goals':1 if i%3==0 else 3})
        expected={r['id']:r['features'][:3] for r in chronological_features(games,10,35,.75)}
        state=blank_state();checked=0
        for _,batch in groupby(games,key=lambda g:g['date']):
            batch=list(batch)
            for row in batch:
                if row['id'] in expected:
                    home=68 if row['home']==59 and row['season']==2025 else row['home']
                    away=68 if row['away']==59 and row['season']==2025 else row['away']
                    actual=features(state,home,away,row['date'],row['season'])
                    np.testing.assert_allclose(actual,expected[row['id']],atol=1e-12,rtol=0)
                    checked+=1
            apply_day(state,batch)
        self.assertEqual(checked,70)

    def test_pure_python_inference_matches_numpy_fit_and_calibration(self):
        bundle,_=load_bundle()
        vectors=np.random.default_rng(20261015).normal(0,.4,size=(100,3))
        expected=calibrate(bundle['calibration'],predict_logistic(bundle['fit'],vectors))
        actual=[probability(bundle,x.tolist()) for x in vectors]
        np.testing.assert_allclose(actual,expected,atol=1e-12,rtol=0)


if __name__=='__main__':unittest.main()
