from copy import deepcopy
import csv
from datetime import date, timedelta
import json
from pathlib import Path
import unittest
import tempfile

import numpy as np

from research.nhl_experiment import integral_score, official_game, partition, reconcile_moneypuck
from research.nhl_team_model import (block_improvement, calibrate, chronological_features,
    fit_logistic, fit_platt, metrics, predict_logistic, reliability)


def games(count=60):
    result = []
    for i in range(count):
        winner = int(i % 3 != 0)
        result.append({'id': 2018020001 + i, 'season': 2018,
                       'date': (date(2018, 10, 1) + timedelta(days=i)).isoformat(),
                       'home': 1 if i % 2 else 2, 'away': 2 if i % 2 else 1,
                       'home_win': winner, 'home_hockey_goals': 3 if winner else 1,
                       'away_hockey_goals': 1 if winner else 3})
    return result


class ChronologyTests(unittest.TestCase):
    def test_current_and_future_outcomes_cannot_change_current_features(self):
        source = games()
        changed = deepcopy(source)
        for row in changed[30:]:
            row['home_win'] = 1 - row['home_win']
            row['home_hockey_goals'], row['away_hockey_goals'] = row['away_hockey_goals'], row['home_hockey_goals']
        first = chronological_features(source, 20, 65, .5)
        second = chronological_features(changed, 20, 65, .5)
        before = [r for r in first if r['id'] <= source[30]['id']]
        compare = [r for r in second if r['id'] <= source[30]['id']]
        self.assertEqual([r['features'] for r in before], [r['features'] for r in compare])
        self.assertEqual([r['elo'] for r in before], [r['elo'] for r in compare])
        self.assertTrue(all(r['latest_input_date'] < r['date'] for r in first))
        self.assertNotEqual(first[-1]['elo'], second[-1]['elo'])

    def test_cold_start_is_explicit_and_output_order_is_deterministic(self):
        source = games()
        first = chronological_features(source, 20, 65, .5)
        second = chronological_features(list(reversed(source)), 20, 65, .5)
        self.assertEqual(first, second)
        self.assertEqual(len(first), len(source) - 10)
        self.assertGreaterEqual(min(r['minimum_prior_games'] for r in first), 10)

    def test_duplicate_club_on_same_date_is_rejected(self):
        source = games()
        source[1]['date'] = source[0]['date']
        with self.assertRaisesRegex(ValueError, 'Duplicate team'):
            chronological_features(source, 20, 65, .5)

    def test_season_regression_occurs_before_next_season_prediction(self):
        source = games()
        next_game = {**source[-1], 'id': 2019020001, 'season': 2019, 'date': '2019-10-01'}
        reset = chronological_features(source + [next_game], 20, 65, 0)[-1]
        carry = chronological_features(source + [next_game], 20, 65, 1)[-1]
        self.assertEqual(reset['features'][0], 0)
        self.assertNotEqual(carry['features'][0], 0)

    def test_partitions_reject_post_target_features_and_overlap(self):
        plan = {'minimum_partition_gap_days': 1, 'minimum_records': dict(fit=1, selection=1, calibration=1, test=1)}
        source = []
        for year, name in zip(range(2018, 2022), ('fit', 'selection', 'calibration', 'test')):
            plan[name + '_seasons'] = [year]
            source.append({'season': year, 'date': f'{year}-10-02', 'latest_input_date': f'{year}-10-01'})
        self.assertEqual(len(partition(source, plan)), 4)
        source[-1]['latest_input_date'] = source[-1]['date']
        with self.assertRaisesRegex(ValueError, 'leakage'):
            partition(source, plan)


class OutcomeTests(unittest.TestCase):
    def setUp(self):
        self.row = {'id': 2025020001, 'season': 20252026, 'gameType': 2, 'gameStateId': 7,
                    'gameScheduleStateId': 1, 'gameDate': '2025-10-07', 'homeTeamId': 1,
                    'visitingTeamId': 2, 'homeScore': 3, 'visitingScore': 2, 'period': 5}
        self.teams = {1: {'triCode': 'AAA'}, 2: {'triCode': 'BBB'}}

    def test_shootout_winner_comes_from_official_final_not_tied_hockey_goals(self):
        game = official_game(self.row, self.teams)
        self.assertEqual(game['home_win'], 1)
        self.assertEqual(game['home_hockey_goals'], game['away_hockey_goals'])
        self.row.update(homeScore=2, visitingScore=3)
        self.assertEqual(official_game(self.row, self.teams)['home_win'], 0)

    def test_csv_decimal_scores_do_not_silently_truncate(self):
        self.assertEqual(integral_score('3.0'), 3)
        for invalid in ('3.5', 'nan', '-1', '31'):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                integral_score(invalid)

    def test_nonfinal_tied_wrong_season_and_impossible_overtime_are_rejected(self):
        for update in ({'gameStateId': 1}, {'homeScore': 2}, {'season': 20242025}, {'homeScore': 5}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                official_game({**self.row, **update}, self.teams)

    def test_reconciliation_inventories_score_differences_without_guessing_winners(self):
        game = official_game(self.row, self.teams)
        fields = ['gameId', 'season', 'gameDate', 'situation', 'playerTeam', 'opposingTeam',
                  'home_or_away', 'goalsFor', 'goalsAgainst', 'playoffGame']
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'teams.csv'
            with path.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for side, other, venue in (('AAA', 'BBB', 'HOME'), ('BBB', 'AAA', 'AWAY')):
                    writer.writerow(dict(gameId='2025020001', season='2025', gameDate='20251007',
                        situation='all', playerTeam=side, opposingTeam=other, home_or_away=venue,
                        goalsFor='1.0', goalsAgainst='1.0', playoffGame='0'))
            audit = reconcile_moneypuck(path, [game])
            self.assertEqual(audit['score_difference_team_rows'], 2)
            self.assertEqual(audit['shootout_winners_resolved_from_official_finals'], 1)
            self.assertEqual(game['home_win'], 1)

    def test_conflicting_start_date_cannot_enter_history(self):
        with self.assertRaisesRegex(ValueError, 'start date'):
            official_game({**self.row, 'easternStartTime': '2025-10-08T01:00:00'}, self.teams)


class StatisticalTests(unittest.TestCase):
    def test_fitting_only_uses_supplied_partition_and_does_not_mutate_on_prediction(self):
        x = np.arange(100, dtype=float)[:, None]
        y = np.array([int(i > 40) for i in range(100)])
        model = fit_logistic(x, y, 10)
        frozen = json.dumps(model, sort_keys=True)
        self.assertEqual(model['center'], [49.5])
        p = predict_logistic(model, [[-1000], [1000]])
        self.assertLess(p[0], p[1])
        self.assertEqual(json.dumps(model, sort_keys=True), frozen)

    def test_calibration_uses_separate_supplied_outcomes_and_preserves_order(self):
        p = np.array([.3, .4, .6, .7] * 50)
        y = np.array([0, 1, 0, 1] * 50)
        fitted = fit_platt(p, y)
        adjusted = calibrate(fitted, [.2, .8])
        self.assertLess(adjusted[0], adjusted[1])
        self.assertTrue(np.isfinite(adjusted).all())

    def test_metrics_and_reliability_count_actual_observations(self):
        result = metrics([0, 1], [.25, .75])
        self.assertAlmostEqual(result['brier'], .0625)
        self.assertEqual(result['winner_accuracy'], 1)
        self.assertEqual(sum(b['games'] for b in reliability([0, 1], [.25, .75])), 2)

    def test_week_cluster_interval_is_reproducible_and_paired(self):
        rows = [{'date': (date(2024, 1, 1) + timedelta(days=i)).isoformat(), 'season': 2023} for i in range(100)]
        y = np.array([i % 2 for i in range(100)])
        a = block_improvement(rows, y, np.full(100, .5), np.full(100, .5), replications=100)
        b = block_improvement(rows, y, np.full(100, .5), np.full(100, .5), replications=100)
        self.assertEqual(a, b)
        self.assertEqual(a['percentile_95_low'], 0)

    def test_plan_does_not_select_primary_model_using_test_scores(self):
        plan = json.loads((Path(__file__).parents[1] / 'plans/nhl-team-v1.json').read_text())
        self.assertEqual(plan['primary_final_model'], 'logistic_calibrated')
        self.assertTrue(set(plan['test_seasons']).isdisjoint(plan['selection_seasons'] + plan['calibration_seasons'] + plan['fit_seasons']))


if __name__ == '__main__':
    unittest.main()
