"""Bounded offline inventory of cached NHL sources; never a model approval.

Run with explicit local files. No network, application configuration or database
is imported. Historical results are not relabeled as pregame observations.
"""
import argparse
from collections import defaultdict
import hashlib
import io
import json
from pathlib import Path
import zipfile
from .nhl_data import TEAM_FIELDS, GOALIE_FIELDS, csv_rows, validate_team, validate_goalie


def fingerprint(path, maximum):
    if not 0 < path.stat().st_size <= maximum:
        raise ValueError('Local source exceeds the audit byte budget')
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return {'sha256': digest.hexdigest(), 'bytes': path.stat().st_size}


def audit(team_path, goalie_path, season=2026):
    sources={'team':fingerprint(team_path,160*1024*1024),'goalie':fingerprint(goalie_path,2_000_000)}
    historical=defaultdict(set); teams=defaultdict(dict); goalie_games=set(); team_rows=goalie_rows=0
    with team_path.open(encoding='utf-8-sig',newline='') as handle:
        for row in csv_rows(handle,TEAM_FIELDS):
            team_rows+=1
            if row['season']!=str(season):
                if row['situation']=='all':historical[row['season']].add(row['gameId'])
                continue
            validate_team(row)
            if row['gameId'][4:6]!='02' or row['situation']!='all':continue
            if row['playerTeam'] in teams[row['gameId']]:raise ValueError('Duplicate current-season team game')
            teams[row['gameId']][row['playerTeam']]=row
    with zipfile.ZipFile(goalie_path) as archive:
        members=archive.infolist()
        if len(members)!=1 or members[0].file_size>8*1024*1024 or members[0].is_dir():
            raise ValueError('Goalie archive contract rejected')
        seen=set()
        with archive.open(members[0]) as raw, io.TextIOWrapper(raw,encoding='utf-8-sig',newline='') as handle:
            for row in csv_rows(handle,GOALIE_FIELDS,maximum=100_000):
                goalie_rows+=1
                validate_goalie(row)
                key=(row['gameId'],row['playerId'],row['situation'])
                if key in seen:raise ValueError('Duplicate goalie game/situation')
                seen.add(key)
                if row['season']==str(season) and row['gameId'][4:6]=='02':goalie_games.add(row['gameId'])
    dates=[]; appearances=defaultdict(list); paired=0; enough_prior=0
    for gid,pair in sorted(teams.items(),key=lambda item:(next(iter(item[1].values()))['gameDate'],item[0])):
        if len(pair)!=2:raise ValueError('Unpaired current-season team game')
        first,second=pair.values()
        if first['opposingTeam']!=second['playerTeam'] or second['opposingTeam']!=first['playerTeam']:
            raise ValueError('Opposing team identities disagree')
        paired+=1;day=first['gameDate'];dates.append(day)
        if all(sum(prior<day for prior in appearances[code])>=5 for code in pair):enough_prior+=1
        for code in pair:appearances[code].append(day)
    return {'classification':'offline_source_inventory_not_model_validation','season':season,
        'sources':sources,'team_rows_read':team_rows,'goalie_rows_read':goalie_rows,
        'paired_regular_season_games':paired,'team_goalie_game_overlap':len(set(teams)&goalie_games),
        'both_teams_have_five_prior_games':enough_prior,
        'first_game_date':min(dates) if dates else None,'latest_game_date':max(dates) if dates else None,
        'other_season_team_game_ids_not_validated':{key:len(value) for key,value in sorted(historical.items())},
        'required_validation_partitions':[300,100,100], 'model_approved':False,
        'blockers':['These downloads do not establish pregame starter confirmations or original pregame observation times.',
            'Historical team seasons lack matching audited goalie archives and point-in-time provenance.',
            'Passing chronological validation requires genuinely qualified frozen records; source rows are not forecasts.'],
        'provider_requests':0,'production_writes':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--teams',type=Path,required=True)
    parser.add_argument('--goalies',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=audit(args.teams,args.goalies)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({key:report[key] for key in ('paired_regular_season_games','team_goalie_game_overlap',
        'both_teams_have_five_prior_games','model_approved','provider_requests')},indent=2))


if __name__=='__main__':main()
