"""Deterministic, chronological team baselines for offline research only.

No application settings, database, providers or network are imported. Parameters
are chosen before the held-out test; outcomes update ratings only on later dates.
"""
from collections import defaultdict, deque
from datetime import date
from itertools import groupby
import math

import numpy as np

FEATURE_NAMES = ('rating_difference', 'rest_difference', 'back_to_back_difference',
                 'recent_goal_difference', 'recent_win_rate_difference')


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))


def chronological_features(games, k, home_points, carry, *, minimum_prior=10, rolling=10):
    """Generate forecasts before observing any result on the same calendar date."""
    if not 0 < k <= 100 or not 0 <= home_points <= 200 or not 0 <= carry <= 1:
        raise ValueError('Invalid declared Elo configuration')
    ratings = defaultdict(lambda: 1500.0)
    recent = defaultdict(lambda: deque(maxlen=rolling))
    last_day = {}
    counts = defaultdict(int)
    rows = []
    season = None
    ordered = sorted(games, key=lambda g: (g['date'], g['id']))
    for day_string, iterator in groupby(ordered, key=lambda g: g['date']):
        day = date.fromisoformat(day_string)
        batch = list(iterator)
        seasons = {g['season'] for g in batch}
        if len(seasons) != 1:
            raise ValueError('Overlapping seasons on one game date')
        current = batch[0]['season']
        if season != current:
            if season is not None and current <= season:
                raise ValueError('Nonchronological season transition')
            for team in ratings:
                ratings[team] = 1500 + carry * (ratings[team] - 1500)
            season = current
        seen = set()
        updates = []
        for game in batch:
            home, away = game['home'], game['away']
            if home == away or home in seen or away in seen:
                raise ValueError('Duplicate team on a game date')
            seen.update((home, away))
            difference = ratings[home] - ratings[away]
            p = 1 / (1 + 10 ** (-(difference + home_points) / 400))
            outcome = game['home_win']
            if type(outcome) is not int or outcome not in (0, 1):
                raise ValueError('An explicit final-winner target is required')
            if min(counts[home], counts[away]) >= minimum_prior:
                rests = [min(4, max(0, (day - last_day[t]).days - 1)) for t in (home, away)]
                mean_goal = [sum(r[0] for r in recent[t]) / len(recent[t]) for t in (home, away)]
                mean_win = [sum(r[1] for r in recent[t]) / len(recent[t]) for t in (home, away)]
                rows.append({**game, 'elo': p, 'features': [difference / 400, rests[0] - rests[1],
                    int(rests[0] == 0) - int(rests[1] == 0), mean_goal[0] - mean_goal[1], mean_win[0] - mean_win[1]],
                    'latest_input_date': max(last_day[home], last_day[away]).isoformat(),
                    'minimum_prior_games': min(counts[home], counts[away])})
            updates.append((home, away, k * (outcome - p), game))
        # Predictions for the complete date are frozen before applying results.
        for home, away, delta, game in updates:
            ratings[home] += delta
            ratings[away] -= delta
            goal_difference = game['home_hockey_goals'] - game['away_hockey_goals']
            recent[home].append((goal_difference, game['home_win']))
            recent[away].append((-goal_difference, 1 - game['home_win']))
            counts[home] += 1
            counts[away] += 1
            last_day[home] = last_day[away] = day
    return rows


def fit_logistic(x, y, penalty=1.0, *, standardize=True):
    """Small ridge logistic fit using stable Newton steps and line search."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if x.ndim != 2 or len(x) != len(y) or len(y) < 3 or not np.isfinite(x).all():
        raise ValueError('Invalid fitting matrix')
    if not set(np.unique(y)).issubset({0.0, 1.0}) or not 0 < y.mean() < 1 or penalty <= 0:
        raise ValueError('Both outcomes and positive regularization required')
    center = x.mean(axis=0) if standardize else np.zeros(x.shape[1])
    scale = x.std(axis=0) if standardize else np.ones(x.shape[1])
    scale = np.where(scale > 1e-10, scale, 1.0)
    design = np.column_stack([np.ones(len(x)), (x - center) / scale])
    beta = np.zeros(design.shape[1])
    beta[0] = math.log(y.mean() / (1 - y.mean()))
    ridge = np.eye(len(beta)) * penalty
    ridge[0, 0] = 0

    def objective(b):
        z = design @ b
        return float(np.sum(np.logaddexp(0, z) - y * z) + .5 * b @ ridge @ b)

    converged = False
    for _ in range(100):
        probability = sigmoid(design @ beta)
        gradient = design.T @ (probability - y) + ridge @ beta
        hessian = design.T @ (design * np.maximum(probability * (1 - probability), 1e-10)[:, None]) + ridge
        step = np.linalg.solve(hessian + np.eye(len(beta)) * 1e-10, gradient)
        if np.max(np.abs(gradient)) < 1e-7:
            converged = True
            break
        alpha = 1.0
        before = objective(beta)
        while alpha >= 2 ** -20:
            candidate = beta - alpha * step
            if objective(candidate) <= before:
                beta = candidate
                break
            alpha /= 2
        else:
            raise ValueError('Logistic line search did not converge')
        if np.max(np.abs(alpha * step)) < 1e-8:
            converged = True
            break
    if not converged or not np.isfinite(beta).all():
        raise ValueError('Logistic fit did not converge')
    return {'center': center.tolist(), 'scale': scale.tolist(), 'coefficients': beta.tolist(),
            'penalty': penalty, 'converged': True}


def predict_logistic(model, x):
    x = np.asarray(x, dtype=float)
    design = np.column_stack([np.ones(len(x)), (x - np.array(model['center'])) / np.array(model['scale'])])
    return sigmoid(design @ np.array(model['coefficients']))


def fit_platt(probabilities, outcomes):
    p = np.clip(np.asarray(probabilities), 1e-9, 1 - 1e-9)
    model = fit_logistic(np.log(p / (1 - p))[:, None], outcomes, .1, standardize=False)
    if not .01 <= model['coefficients'][1] <= 10:
        raise ValueError('Calibration slope outside predeclared admissible range')
    return model


def calibrate(model, probabilities):
    p = np.clip(np.asarray(probabilities), 1e-9, 1 - 1e-9)
    return predict_logistic(model, np.log(p / (1 - p))[:, None])


def metrics(outcomes, probabilities):
    y, p = np.asarray(outcomes), np.asarray(probabilities)
    if not len(y) or len(y) != len(p) or not np.isfinite(p).all() or ((p <= 0) | (p >= 1)).any():
        raise ValueError('Invalid probability evaluation')
    return {'games': len(y), 'brier': float(np.mean((p - y) ** 2)),
            'log_loss': float(-np.mean(y * np.log(p) + (1 - y) * np.log1p(-p))),
            'winner_accuracy': float(np.mean((p >= .5) == y)),
            'mean_home_probability': float(p.mean()), 'actual_home_win_rate': float(y.mean()),
            'minimum_probability': float(p.min()), 'maximum_probability': float(p.max())}


def reliability(outcomes, probabilities):
    y, p = np.asarray(outcomes), np.asarray(probabilities)
    rows = []
    for i in range(10):
        selected = (p >= i / 10) & (p < (i + 1) / 10)
        n = int(selected.sum())
        if not n:
            continue
        observed = float(y[selected].mean())
        z = 1.95996398454
        denominator = 1 + z * z / n
        center = (observed + z * z / (2 * n)) / denominator
        half = z * math.sqrt(observed * (1 - observed) / n + z * z / (4 * n * n)) / denominator
        rows.append({'lower_bin': i / 10, 'upper_bin': (i + 1) / 10, 'games': n,
                     'mean_probability': float(p[selected].mean()), 'observed_home_win_rate': observed,
                     'wilson_low': center - half, 'wilson_high': center + half})
    return rows


def block_improvement(rows, outcomes, reference, predicted, *, replications=2000, seed=20261015):
    y, base, p = map(np.asarray, (outcomes, reference, predicted))
    differences = (base - y) ** 2 - (p - y) ** 2
    clusters = defaultdict(list)
    for i, row in enumerate(rows):
        iso = date.fromisoformat(row['date']).isocalendar()
        clusters[(row['season'], iso.year, iso.week)].append(i)
    keys = sorted(clusters)
    if len(keys) < 10:
        raise ValueError('Too few calendar-week blocks for uncertainty estimate')
    sums = np.array([differences[clusters[key]].sum() for key in keys])
    sizes = np.array([len(clusters[key]) for key in keys])
    samples = np.random.default_rng(seed).integers(0, len(keys), size=(replications, len(keys)))
    estimates = sums[samples].sum(axis=1) / sizes[samples].sum(axis=1)
    low, high = np.quantile(estimates, [.025, .975])
    return {'metric': 'reference_brier_minus_model_brier', 'estimate': float(differences.mean()),
            'percentile_95_low': float(low), 'percentile_95_high': float(high),
            'clusters': len(keys), 'cluster_unit': 'season_iso_calendar_week',
            'replications': replications, 'seed': seed,
            'interpretation': 'Exploratory paired week-cluster uncertainty; not proof of a market edge.'}
