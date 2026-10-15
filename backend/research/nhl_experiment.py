"""Run the predeclared NHL team experiment using explicit local source files.

No network or application configuration is used. This cannot create production
forecasts, approve a model, execute bets or alter a bankroll.
"""
import argparse
from collections import Counter, defaultdict
from contextlib import closing
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import urllib.parse

import numpy as np

from .nhl_team_model import (FEATURE_NAMES, block_improvement, calibrate,
    chronological_features, fit_logistic, fit_platt, metrics, predict_logistic, reliability)

EXPECTED_FILTER = 'season>=20152016 and season<=20252026 and gameType=2'


def fingerprint(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return {'path': str(path.resolve()), 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write('\n')


def load_official(cache):
    sources, pages, teams = [], [], None
    with closing(sqlite3.connect(Path(cache) / 'admission.sqlite3')) as conn:
        attempts = conn.execute('SELECT url,at,status,bytes,sha256 FROM attempt ORDER BY at,id').fetchall()
    for url, at, status, length, digest in attempts:
        if status != 'SUCCEEDED':
            raise ValueError('Acquisition ledger contains an unresolved attempt')
        key = hashlib.sha256(url.encode()).hexdigest()
        path = Path(cache) / (key + '.json')
        raw = path.read_bytes()
        if len(raw) != length or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Official source failed immutable-cache verification')
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != 'https' or parsed.netloc != 'api.nhle.com':
            raise ValueError('Unexpected official source host')
        query = urllib.parse.parse_qs(parsed.query)
        payload = json.loads(raw)
        used = False
        if parsed.path == '/stats/rest/en/team':
            if teams is not None:
                raise ValueError('Ambiguous team reference')
            teams = {r['id']: r for r in payload['data']}
            used = True
        elif (parsed.path == '/stats/rest/en/game' and query.get('cayenneExp') == [EXPECTED_FILTER]
              and query.get('limit') == ['10000']):
            pages.append((int(query['start'][0]), payload))
            used = True
        sources.append({'url': url, 'observed_at': at, 'bytes': length, 'sha256': digest, 'used_in_dataset': used})
    if teams is None or len(teams) < 30 or len(pages) != 2 or sorted(p[0] for p in pages) != [0, 10000]:
        raise ValueError('Complete explicit historical pages and team reference required')
    if len({p['total'] for _, p in pages}) != 1:
        raise ValueError('Official page totals disagree')
    rows = [r for _, p in sorted(pages) for r in p['data']]
    if len(rows) != pages[0][1]['total'] or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Official result pagination incomplete or duplicated')
    return rows, teams, {'sources': sources, 'requests_in_ledger': len(attempts),
                         'downloaded_bytes': sum(a[3] for a in attempts), 'paid_requests': 0}


def official_game(row, teams):
    for key in ('id', 'season', 'gameType', 'gameStateId', 'gameScheduleStateId',
                'homeScore', 'visitingScore', 'homeTeamId', 'visitingTeamId', 'period'):
        if type(row.get(key)) is not int:
            raise ValueError('Official game has missing/noninteger field: ' + key)
    season = row['season'] // 10000
    gid = str(row['id'])
    day = date.fromisoformat(row['gameDate'])
    if row.get('easternStartTime') and row['easternStartTime'][:10] != day.isoformat():
        raise ValueError('Official start date disagrees with game date')
    if (row['season'] != season * 10000 + season + 1 or not 2015 <= season <= 2025
            or len(gid) != 10 or gid[:6] != str(season) + '02' or row['gameType'] != 2
            or row['gameStateId'] != 7 or row['gameScheduleStateId'] != 1
            or not date(season, 7, 1) <= day < date(season + 1, 7, 1)):
        raise ValueError('Official final/season/date contract failed')
    home, away = row['homeTeamId'], row['visitingTeamId']
    h, a = row['homeScore'], row['visitingScore']
    if (home == away or home not in teams or away not in teams or not 0 <= min(h, a) <= max(h, a) <= 30
            or h == a or row['period'] not in (3, 4, 5)):
        raise ValueError('Official winner/identity contract failed')
    if row['period'] > 3 and abs(h - a) != 1:
        raise ValueError('Unexpected overtime/shootout final score margin')
    winner = int(h > a)
    shootout = row['period'] == 5
    return {'id': row['id'], 'season': season, 'date': day.isoformat(), 'home': home, 'away': away,
            'home_code': teams[home]['triCode'], 'away_code': teams[away]['triCode'],
            'home_score': h, 'away_score': a, 'home_win': winner, 'shootout': shootout,
            'home_hockey_goals': h - int(shootout and winner == 1),
            'away_hockey_goals': a - int(shootout and winner == 0)}


def normalized_code(value):
    code = value.replace('.', '').upper()
    return {'LA': 'LAK', 'NJ': 'NJD', 'SJ': 'SJS', 'TB': 'TBL'}.get(code, code)


def integral_score(value):
    try:
        parsed = Decimal(value)
    except (ValueError, TypeError, InvalidOperation):
        raise ValueError('Invalid archived score') from None
    if not parsed.is_finite() or not 0 <= parsed <= 30 or parsed != parsed.to_integral_value():
        raise ValueError('Invalid archived score')
    return int(parsed)


def reconcile_moneypuck(path, games):
    if not 0 < Path(path).stat().st_size <= 160 * 1024 * 1024:
        raise ValueError('Cached team CSV exceeds byte budget')
    required = {'gameId', 'season', 'gameDate', 'situation', 'playerTeam', 'opposingTeam',
                'home_or_away', 'goalsFor', 'goalsAgainst', 'playoffGame'}
    groups = defaultdict(list)
    total = 0
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not required <= set(reader.fieldnames or []) or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError('Changed team CSV header')
        for row in reader:
            total += 1
            if total > 350000 or None in row or any(row[k] is None for k in required):
                raise ValueError('Team CSV row budget/width changed')
            if row['situation'] == 'all' and row['gameId'][4:6] == '02' and 2015 <= int(row['season']) <= 2025:
                groups[int(row['gameId'])].append(row)
    ids = {g['id'] for g in games}
    if set(groups) != ids:
        raise ValueError('Official and team-CSV game coverage differ: ' + str(sorted(set(groups) ^ ids)[:10]))
    shootouts = 0
    score_differences = []
    for game in games:
        pair = groups[game['id']]
        if len(pair) != 2 or {r['home_or_away'] for r in pair} != {'HOME', 'AWAY'}:
            raise ValueError('Team CSV pairing/venue mismatch')
        for side, venue, other in (('home', 'HOME', 'away'), ('away', 'AWAY', 'home')):
            row = next(r for r in pair if r['home_or_away'] == venue)
            if (normalized_code(row['playerTeam']) != normalized_code(game[side + '_code'])
                    or normalized_code(row['opposingTeam']) != normalized_code(game[other + '_code'])
                    or row['gameDate'] != game['date'].replace('-', '') or row['playoffGame'] != '0'):
                raise ValueError('Official/CSV date or identity mismatch: ' + str(game['id']))
            archived_for, archived_against = integral_score(row['goalsFor']), integral_score(row['goalsAgainst'])
            if archived_for != game[side + '_hockey_goals'] or archived_against != game[other + '_hockey_goals']:
                score_differences.append({'game_id': game['id'], 'team': game[side + '_code'],
                    'official_hockey_goals_for': game[side + '_hockey_goals'], 'archive_goals_for': archived_for,
                    'official_hockey_goals_against': game[other + '_hockey_goals'], 'archive_goals_against': archived_against})
        shootouts += int(game['shootout'])
    return {'all_csv_rows_read': total, 'paired_identities_dates_reconciled': len(games),
            'shootout_winners_resolved_from_official_finals': shootouts,
            'score_difference_team_rows': len(score_differences), 'score_differences': score_differences,
            'model_score_source': 'Official NHL final scores only; MoneyPuck goal differences are inventoried, never repaired or substituted.',
            'scope': 'All regular-season IDs in the two cached sources for 2015–2025; not independent proof the upstream feed has every scheduled game.',
            'xg_used': False, 'point_in_time_source_versions_verified': False}


def partition(rows, plan):
    result = {name: [r for r in rows if r['season'] in plan[name + '_seasons']]
              for name in ('fit', 'selection', 'calibration', 'test')}
    previous_end = None
    for name, selected in result.items():
        if len(selected) < plan['minimum_records'][name]:
            raise ValueError('Insufficient ' + name + ' records')
        first, last = min(r['date'] for r in selected), max(r['date'] for r in selected)
        if previous_end and (date.fromisoformat(first) - date.fromisoformat(previous_end)).days <= plan['minimum_partition_gap_days']:
            raise ValueError('Chronological partition overlap or inadequate date embargo')
        if any(r['latest_input_date'] >= r['date'] for r in selected):
            raise ValueError('Future/same-day input leakage')
        previous_end = last
    return result


def matrix(rows, group):
    if group not in ('rating_rest', 'rating_rest_recent'):
        raise ValueError('Unknown declared feature group')
    size = 3 if group == 'rating_rest' else 5
    return np.array([r['features'][:size] for r in rows], dtype=float)


def outcomes(rows):
    return np.array([r['home_win'] for r in rows], dtype=float)


def run(plan_path, cache, team_csv, output):
    plan_path, cache, team_csv, output = map(Path, (plan_path, cache, team_csv, output))
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    if plan['contract'] != 'nhl-team-offline-v1' or plan['primary_final_model'] != 'logistic_calibrated':
        raise ValueError('Unsupported experiment contract')
    source_rows, teams, acquisition = load_official(cache)
    games = sorted([official_game(r, teams) for r in source_rows], key=lambda g: (g['date'], g['id']))
    if sorted({g['season'] for g in games}) != plan['data_seasons']:
        raise ValueError('Declared season coverage does not match')
    reconciliation = reconcile_moneypuck(team_csv, games)
    output.mkdir(parents=True, exist_ok=False)
    frozen = {'created_at': datetime.now(timezone.utc).isoformat(), 'plan': plan,
              'plan_source': fingerprint(plan_path), 'team_source': fingerprint(team_csv),
              'code_sources': [fingerprint(Path(__file__)), fingerprint(Path(__file__).with_name('nhl_team_model.py'))],
              'official_acquisition': acquisition, 'reconciliation': reconciliation,
              'python': platform.python_version(), 'numpy': np.__version__,
              'prepared_dataset_sha256': hashlib.sha256(json.dumps(games, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
              'heldout_metrics_not_yet_computed': True}
    # Freeze configuration, source hashes and executable code before choosing
    # parameters or evaluating any held-out performance.
    write_new(output / 'pre_evaluation_manifest.json', frozen)
    write_new(output / 'prepared_games.json', games)
    development = [g for g in games if g['season'] <= max(plan['selection_seasons'])]
    candidates = []
    best_key, best_config = None, None
    for k in plan['elo_k']:
        for home in plan['elo_home_points']:
            for carry in plan['elo_season_carry']:
                rows = chronological_features(development, k, home, carry,
                    minimum_prior=plan['minimum_prior_games_per_team'], rolling=plan['rolling_games'])
                selected = [r for r in rows if r['season'] in plan['selection_seasons']]
                score = metrics(outcomes(selected), [r['elo'] for r in selected])
                config = {'k': k, 'home_points': home, 'carry': carry}
                candidates.append({'model': 'elo', 'config': config, 'selection': score})
                key = score['brier'], score['log_loss']
                if best_key is None or key < best_key:
                    best_key, best_config = key, config
    rows = chronological_features(games, **best_config,
        minimum_prior=plan['minimum_prior_games_per_team'], rolling=plan['rolling_games'])
    parts = partition(rows, plan)
    ridge_key, ridge_config = None, None
    for group in plan['feature_groups']:
        for penalty in plan['ridge_penalties']:
            model = fit_logistic(matrix(parts['fit'], group), outcomes(parts['fit']), penalty)
            score = metrics(outcomes(parts['selection']), predict_logistic(model, matrix(parts['selection'], group)))
            config = {'feature_group': group, 'penalty': penalty}
            candidates.append({'model': 'logistic', 'config': config, 'selection': score})
            key = score['brier'], score['log_loss']
            if ridge_key is None or key < ridge_key:
                ridge_key, ridge_config = key, config
    fitted_rows = parts['fit'] + parts['selection']
    group = ridge_config['feature_group']
    logistic = fit_logistic(matrix(fitted_rows, group), outcomes(fitted_rows), ridge_config['penalty'])
    calibration_y = outcomes(parts['calibration'])
    elo_platt = fit_platt([r['elo'] for r in parts['calibration']], calibration_y)
    logistic_platt = fit_platt(predict_logistic(logistic, matrix(parts['calibration'], group)), calibration_y)
    reference = float(outcomes(fitted_rows).mean())
    fitted = {'selected_elo': best_config, 'selected_logistic': ridge_config, 'logistic_fit': logistic,
              'elo_calibration': elo_platt, 'logistic_calibration': logistic_platt,
              'home_prevalence': reference, 'selection_candidates': candidates}
    write_new(output / 'fitted_before_test.json', fitted)
    test = parts['test']
    y = outcomes(test)
    elo_raw = np.array([r['elo'] for r in test])
    logistic_raw = predict_logistic(logistic, matrix(test, group))
    predictions = {'home_prevalence': np.full(len(test), reference), 'elo_raw': elo_raw,
                   'elo_calibrated': calibrate(elo_platt, elo_raw), 'logistic_raw': logistic_raw,
                   'logistic_calibrated': calibrate(logistic_platt, logistic_raw)}
    scores = {name: metrics(y, p) for name, p in predictions.items()}
    primary = plan['primary_final_model']
    uncertainty = block_improvement(test, y, predictions['home_prevalence'], predictions[primary],
        replications=plan['bootstrap']['replications'], seed=plan['bootstrap']['seed'])
    checks = {'primary_brier_better_than_home_prevalence': scores[primary]['brier'] < scores['home_prevalence']['brier'],
              'primary_log_loss_better_than_home_prevalence': scores[primary]['log_loss'] < scores['home_prevalence']['log_loss'],
              'week_cluster_brier_improvement_95pct_lower_bound_above_zero': uncertainty['percentile_95_low'] > 0}
    per_season = {}
    for season in plan['test_seasons']:
        idx = np.array([i for i, r in enumerate(test) if r['season'] == season])
        per_season[str(season)] = {name: metrics(y[idx], p[idx]) for name, p in predictions.items()}
    report = {'contract': plan['contract'], 'classification': plan['classification'],
              'completed_at': datetime.now(timezone.utc).isoformat(), 'primary_model_predeclared': primary,
              'input_games_by_season': dict(sorted(Counter(g['season'] for g in games).items())),
              'eligible_games_by_season': dict(sorted(Counter(r['season'] for r in rows).items())),
              'cold_start_exclusions_by_season': {str(s): sum(g['season'] == s for g in games) - sum(r['season'] == s for r in rows) for s in plan['data_seasons']},
              'partitions': {name: {'games': len(part), 'first_date': min(r['date'] for r in part),
                                   'last_date': max(r['date'] for r in part)} for name, part in parts.items()},
              'feature_names': list(FEATURE_NAMES[:3 if group == 'rating_rest' else 5]),
              'heldout_scores': scores, 'heldout_by_season': per_season,
              'primary_reliability': reliability(y, predictions[primary]), 'paired_brier_uncertainty': uncertainty,
              'research_progression_checks': checks, 'promising_for_further_paper_research': all(checks.values()),
              'production_approved': False, 'market_edge_demonstrated': False, 'historical_playnow_roi': None,
              'paid_requests': 0, 'ai_generations': 0, 'production_writes': 0,
              'limitations': ['Historical reconstruction, not original pregame source observations or live forecasts.',
                  'No matched historical PlayNow prices, market benchmark or ROI evidence.',
                  'No player injuries, specific expected/confirmed starters or historical roster features.',
                  'Two final test seasons and exploratory week-cluster intervals do not prove durable profitability.',
                  'Rolling game history and Elo ratings update on earlier observed outcomes; fitted coefficients/calibration stay fixed.',
                  'Cold-start teams require ten prior games; excluded fixtures remain visible in coverage counts.']}
    write_new(output / 'report.json', report)
    with (output / 'heldout_predictions.csv').open('x', encoding='utf-8', newline='') as handle:
        fields = ['game_id', 'date', 'season', 'home', 'away', 'home_win', 'latest_input_date', *predictions]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for i, row in enumerate(test):
            writer.writerow({'game_id': row['id'], 'date': row['date'], 'season': row['season'],
                             'home': row['home_code'], 'away': row['away_code'], 'home_win': row['home_win'],
                             'latest_input_date': row['latest_input_date'], **{name: float(p[i]) for name, p in predictions.items()}})
    print(json.dumps({'report': str((output / 'report.json').resolve()), 'partitions': report['partitions'],
                      'heldout_scores': scores, 'research_progression_checks': checks,
                      'production_approved': False, 'market_edge_demonstrated': False}, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--nhl-cache', type=Path, required=True)
    parser.add_argument('--teams', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.plan, args.nhl_cache, args.teams, args.output)


if __name__ == '__main__':
    main()
