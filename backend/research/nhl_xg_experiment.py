"""Predeclared chronological xG/goaltending experiment from explicit local files.

Retrospective source vintages are not point-in-time verified. No market inputs,
provider requests, production writes, model approval or simulated game labels.
"""
import argparse
from collections import defaultdict
from datetime import date, datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import zipfile

from app.nhl_candidate_features import FEATURES, vector, team_goaltending
from app.nhl_data import csv_rows, TEAM_FIELDS, GOALIE_FIELDS, validate_team, validate_goalie, rolling
from app.nhl_paper_model import canonical
from .nhl_experiment import load_official, official_game, normalized_code, fingerprint, write_new
from .nhl_team_model import (chronological_features, fit_logistic, predict_logistic,
    fit_platt, calibrate, metrics, reliability, block_improvement)

PLAN = {'contract':'nhl-xg-goaltending-research-v1',
    'target':'home_final_winner_including_ot_so', 'fit_seasons':[2018,2019,2020,2021],
    'selection_seasons':[2022], 'calibration_seasons':[2023], 'test_seasons':[2024,2025],
    'elo':{'k':10,'home_points':35,'carry':.75}, 'rolling_games':10,'minimum_prior_stat_games':5,
    'goaltending_prior_seconds':28800,'penalties':[1.,10.,100.],
    'selection':'brier_then_log_loss_then_declared_order', 'features':FEATURES,
    'lineup':'prior team goalie appearances only; no eventual starter from target game',
    'historical_sources':'downloaded now; historical point-in-time source versions not established',
    'prior_research':'these test seasons have been examined in earlier team-only research',
    'progression':'Brier and log loss must beat the same-game team-only comparator; uncertainty reported',
    'approval':False,'paid_requests':0,'production_writes':0}


def sources(official_cache, team_path, goalie_directory):
    raw,teams,provenance=load_official(official_cache)
    games=[official_game(row,teams) for row in raw]
    by_id={str(g['id']):g for g in games}
    team_rows=defaultdict(dict)
    with Path(team_path).open(encoding='utf-8-sig',newline='') as handle:
        for row in csv_rows(handle,TEAM_FIELDS):
            if (row['gameId'] not in by_id or int(row['season']) < 2018
                    or row['situation'] not in {'all','5on5'}):
                continue
            validate_team(row)
            key=(row['home_or_away'],row['situation'])
            if key in team_rows[row['gameId']]:
                raise ValueError('Duplicate historical team record')
            team_rows[row['gameId']][key]=row
    goalie_rows=defaultdict(lambda:defaultdict(list)); archives=[]
    directory=Path(goalie_directory)
    with sqlite3.connect(directory/'admission.sqlite3') as conn:
        admissions={r[0]:r[1:] for r in conn.execute('SELECT season,status,bytes,sha256,observed_at,url FROM attempt')}
    for season in range(2018,2026):
        path=directory/f'{season}.zip'; meta=fingerprint(path)
        admission=admissions[season]
        if admission[:3] != ('SUCCEEDED',meta['bytes'],meta['sha256']):
            raise ValueError('Historical goalie archive admission/hash mismatch')
        archives.append({**meta,'observed_at':admission[3],'url':admission[4]})
        with zipfile.ZipFile(path) as archive:
            members=archive.infolist()
            if len(members)!=1 or not members[0].filename.endswith('.csv') or members[0].file_size>8*1024*1024:
                raise ValueError('Bounded goalie ZIP contract changed')
            with archive.open(members[0]) as raw,io.TextIOWrapper(raw,encoding='utf-8-sig',newline='') as handle:
                seen=set()
                for row in csv_rows(handle,GOALIE_FIELDS,20_000):
                    validate_goalie(row)
                    key=(row['gameId'],row['playerId'],row['situation'])
                    if row['season']!=str(season) or key in seen:
                        raise ValueError('Historical goalie season or identity conflict')
                    seen.add(key)
                    if row['gameId'] in by_id and row['situation']=='all':
                        goalie_rows[row['gameId']][row['home_or_away']].append(row)
    admitted_teams=defaultdict(list);admitted_goalies=defaultdict(list);excluded={}
    for gid,pair in team_rows.items():
        game=by_id[gid]; reason=None
        if set(pair)!={('HOME','all'),('AWAY','all'),('HOME','5on5'),('AWAY','5on5')}:
            excluded[gid]='incomplete_team_pair';continue
        for side,venue,other in [('home','HOME','away'),('away','AWAY','home')]:
            all_row,five=pair[(venue,'all')],pair[(venue,'5on5')]
            goalies=goalie_rows[gid][venue]
            for row in (all_row,five,*goalies):
                if (normalized_code(row['playerTeam'])!=normalized_code(game[side+'_code'])
                        or normalized_code(row['opposingTeam'])!=normalized_code(game[other+'_code'])
                        or row['gameDate']!=game['date'].replace('-','')):
                    raise ValueError('Historical official/statistics identity mismatch')
            if (float(all_row['goalsFor'])!=game[side+'_hockey_goals']
                    or float(all_row['goalsAgainst'])!=game[other+'_hockey_goals']):
                reason='official_score_disagreement'
            if not goalies:
                reason='missing_goalie_appearances'
            elif (sum(float(r['goals']) for r in goalies)>float(all_row['goalsAgainst'])
                    or sum(float(r['xGoals']) for r in goalies)>float(all_row['xGoalsAgainst'])+.02):
                reason='goalie_team_totals_disagree'
        h,a=pair[('HOME','5on5')],pair[('AWAY','5on5')]
        if (abs(float(h['xGoalsFor'])-float(a['xGoalsAgainst']))>.002
                or abs(float(h['xGoalsAgainst'])-float(a['xGoalsFor']))>.002):
            reason='five_on_five_totals_disagree'
        if reason:
            excluded[gid]=reason;continue
        for venue in ('HOME','AWAY'):
            row=pair[(venue,'5on5')]
            key=(game['season'],normalized_code(row['playerTeam']))
            admitted_teams[key].append({**row,'playerTeam':key[1]})
            admitted_goalies[key].extend({**r,'playerTeam':key[1]} for r in goalie_rows[gid][venue])
    corrected=[{**g,'home':canonical(g['home']),'away':canonical(g['away'])} for g in games]
    baseline=chronological_features(corrected,10,35,.75)
    prepared=[]; blocked=defaultdict(int)
    for row in baseline:
        if row['season']<2018:continue
        teams_at,goalies_at={},{}
        for side in ('home','away'):
            code=normalized_code(row[side+'_code']);key=(row['season'],code)
            teams_at[side]=rolling(admitted_teams[key],date.fromisoformat(row['date']),team=code,
                                   season=row['season'],minimum=5)
            goalies_at[side]=team_goaltending(admitted_goalies[key],date.fromisoformat(row['date']),code,row['season'])
        try:
            inputs=vector(row['features'][:3],teams_at,goalies_at,row['date'])
        except ValueError:
            blocked[row['season']]+=1;continue
        prepared.append({**row,'features':inputs})
    return prepared, {'official':provenance,'teams':fingerprint(team_path),'goalie_archives':archives,
        'quarantined_games':excluded,'insufficient_prior_games':dict(blocked),
        'statistic_games':sum(len(rows) for rows in admitted_teams.values())//2}


def run(official_cache,team_path,goalie_directory,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    write_new(output/'pre_evaluation_plan.json',{'declared_at':datetime.now(timezone.utc).isoformat(),'plan':PLAN})
    rows,provenance=sources(official_cache,team_path,goalie_directory)
    write_new(output/'source_manifest.json',provenance)
    write_new(output/'prepared_games.json',rows)
    parts={name:[r for r in rows if r['season'] in PLAN[name+'_seasons']]
           for name in ('fit','selection','calibration','test')}
    if any(len(part)<100 for part in parts.values()) or len(parts['fit'])<300:
        raise ValueError('Insufficient chronological comparison samples')
    x=lambda group,n:[r['features'][:n] for r in group]
    y=lambda group:[r['home_win'] for r in group]
    selected={};selection={}
    for name,n in [('team_only',3),('xg_goaltending',5)]:
        choices=[]
        for penalty in PLAN['penalties']:
            fit=fit_logistic(x(parts['fit'],n),y(parts['fit']),penalty)
            score=metrics(y(parts['selection']),predict_logistic(fit,x(parts['selection'],n)))
            choices.append((score['brier'],score['log_loss'],penalty))
        _,_,penalty=min(choices)
        fit_rows=parts['fit']+parts['selection']
        fit=fit_logistic(x(fit_rows,n),y(fit_rows),penalty)
        calibration=fit_platt(predict_logistic(fit,x(parts['calibration'],n)),y(parts['calibration']))
        selected[name]={'fit':fit,'calibration':calibration,'feature_count':n,'penalty':penalty}
        selection[name]=choices
    write_new(output/'fitted_before_test.json',{'models':selected,'selection_scores':selection})
    predictions={name:calibrate(model['calibration'],predict_logistic(model['fit'],x(parts['test'],model['feature_count'])))
                 for name,model in selected.items()}
    scores={name:metrics(y(parts['test']),p) for name,p in predictions.items()}
    uncertainty=block_improvement(parts['test'],y(parts['test']),predictions['team_only'],predictions['xg_goaltending'])
    improves=all(scores['xg_goaltending'][key]<scores['team_only'][key] for key in ('brier','log_loss'))
    report={'classification':'retrospective_exploration_not_production_validation','plan':PLAN,
        'partitions':{name:len(part) for name,part in parts.items()},'scores':scores,
        'paired_improvement':uncertainty,'candidate_improves_both_scores':improves,
        'uncertainty_supports_progression':improves and uncertainty['percentile_95_low']>0,
        'calibration':{name:reliability(y(parts['test']),p) for name,p in predictions.items()},
        'market_edge_demonstrated':False,'approved_for_wagers':False,
        'limitations':['Historical source vintages not verified; reconstructed features are not original pregame observations.',
            'Test seasons were examined in earlier team-only research; they are not newly untouched holdouts.',
            'Team goaltending form is not an individual named starter adjustment.',
            'No historical PlayNow prices; prospective matched-price grading remains necessary.']}
    write_new(output/'report.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('official-cache','teams','goalies','output'):parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args()
    result=run(args.official_cache,args.teams,args.goalies,args.output)
    print(json.dumps({k:result[k] for k in ('partitions','scores','paired_improvement','candidate_improves_both_scores')}))
