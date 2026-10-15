"""Freeze a forward-only paper candidate from the already admitted sources.

No HTTP or database access. The examined historical seasons are fitting data
now; this does not claim a new untouched historical test or approve a model.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from app.nhl_paper_model import CONTRACT, FEATURES, advance, blank_state, canonical
from .nhl_experiment import load_official, official_game
from .nhl_team_model import chronological_features, fit_logistic, fit_platt, predict_logistic


def freeze(cache, destination):
    raw, teams, provenance = load_official(cache)
    if not (teams[59]['franchiseId'] == teams[68]['franchiseId'] == 40):
        raise ValueError('Official Utah franchise continuity not verified')
    games = [official_game(row, teams) for row in raw]
    corrected = [{**g, 'home': canonical(g['home']), 'away': canonical(g['away'])} for g in games]
    rows = chronological_features(corrected, 10, 35, .75)
    fit_rows = [r for r in rows if 2018 <= r['season'] <= 2024]
    calibration_rows = [r for r in rows if r['season'] == 2025]
    fit = fit_logistic([r['features'][:3] for r in fit_rows], [r['home_win'] for r in fit_rows], 1.)
    calibration = fit_platt(predict_logistic(fit, [r['features'][:3] for r in calibration_rows]),
                            [r['home_win'] for r in calibration_rows])
    bundle = {'contract': CONTRACT, 'mode': 'paper_only', 'approved_for_wagers': False,
        'created_at': datetime.now(timezone.utc).isoformat(), 'features': FEATURES,
        'identity': {'68': 59, 'reason': 'Official franchise 40: Utah rename; Arizona not merged'},
        'fit_seasons': list(range(2018, 2025)), 'calibration_seasons': [2025],
        'fit_games': len(fit_rows), 'calibration_games': len(calibration_rows),
        'elo': {'k': 10, 'home_points': 35, 'season_carry': .75},
        'fit': fit, 'calibration': calibration, 'seed': advance(blank_state(), games),
        'teams': {str(i): {'code': t['triCode'], 'franchise': t['franchiseId']} for i, t in teams.items()},
        'source_provenance': provenance,
        'collection': {'threshold': .03, 'quote_max_age_seconds': 300, 'units': 1,
            'market': 'h2h_final_including_ot_so', 'maximum_positions_per_fixture': 1,
            'operational_checkpoint_days': 14, 'operational_checkpoint_pairs': 100,
            'real_money_release': 'Separate evidence review required; never automatic'},
        'limitations': ['Team-only; no goalie adjustment', 'Historical test seasons have already been examined',
                         'No demonstrated sportsbook edge; forward paper research only']}
    app_directory = Path(__file__).resolve().parents[1] / 'app'
    bundle['inference_code_sha256'] = {filename: hashlib.sha256(
        (app_directory / filename).read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest()
        for filename in ('nhl_paper_model.py', 'nhl_paper_history.py', 'nhl_paper.py')}
    content = (json.dumps(bundle, indent=2, allow_nan=False) + '\n').encode()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as handle:
        handle.write(content)
    with destination.with_suffix('.sha256').open('x') as handle:
        handle.write(hashlib.sha256(content).hexdigest() + '\n')
    return {'fit_games': len(fit_rows), 'calibration_games': len(calibration_rows),
            'seed_through': bundle['seed']['through'], 'sha256': hashlib.sha256(content).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(freeze(args.cache, args.output)))
