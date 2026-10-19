"""Shared retrospective/live candidate features; no network or model approval.

Team goaltending uses prior appearances only, never the eventual starter from
the forecasted game. Individual starter news remains separately recorded context.
"""
from datetime import date, datetime
import math

FEATURES = ['rating_difference','rest_difference','back_to_back_difference',
            'five_on_five_share_difference','team_goaltending_form_difference']
MINIMUM = 5
PRIOR_GOALIE_SECONDS = 8 * 3600


def team_goaltending(rows, target, team, season, *, limit=10):
    if not isinstance(target,date) or isinstance(target,datetime) or not MINIMUM <= limit <= 10:
        raise ValueError('A bounded prior-game goalie window is required')
    groups,seen = {},set()
    for row in rows:
        if row['season'] != str(season) or row['playerTeam'] != team or row['situation'] != 'all':
            continue
        day = datetime.strptime(row['gameDate'],'%Y%m%d').date()
        if day >= target or row['gameId'][4:6] != '02':
            continue
        identity=(row['gameId'],row['playerId'])
        if identity in seen:
            raise ValueError('Duplicate prior goalie appearance')
        seen.add(identity)
        ice,xga,goals = (float(row[key]) for key in ('icetime','xGoals','goals'))
        if any(not math.isfinite(x) or x < 0 for x in (ice,xga,goals)) or not goals.is_integer():
            raise ValueError('Malformed prior goalie appearance')
        if ice <= 0:
            continue
        game=groups.setdefault((day,row['gameId']),[0.,0.])
        game[0] += xga-goals
        game[1] += ice
    selected=sorted(groups,reverse=True)[:limit]
    gsax=sum(groups[key][0] for key in selected)
    ice=sum(groups[key][1] for key in selected)
    return {'status':'available' if len(selected) >= MINIMUM else 'insufficient_sample',
        'sample_games':len(selected),'latest_game_date':str(selected[0][0]) if selected else None,
        'game_ids':[key[1] for key in selected], 'gsax':str(gsax),'ice_time_seconds':str(ice),
        'shrunk_gsax_per_60':str(gsax*3600/(ice+PRIOR_GOALIE_SECONDS)),
        'prior_seconds':PRIOR_GOALIE_SECONDS,'team':team,'season':season,
        'target_date':str(target),'specific_starting_goalie_used':False}


def vector(base, teams, goalies, target):
    day=date.fromisoformat(str(target))
    if len(base) != 3 or any(not math.isfinite(value) for value in base):
        raise ValueError('Compatible prior-result baseline required')
    values={}
    for side in ('home','away'):
        team,goalie=teams[side],goalies[side]
        for row in (team,goalie):
            if (row.get('status') != 'available' or type(row.get('sample_games')) is not int
                    or not MINIMUM <= row['sample_games'] <= 10 or row.get('target_date') != str(day)
                    or not row.get('latest_game_date') or date.fromisoformat(row['latest_game_date']) >= day):
                raise ValueError('Five valid prior games per team and goalie window are required')
        if team['team'] != goalie['team'] or team['season'] != goalie['season']:
            raise ValueError('Candidate team/season identities disagree')
        share=float(team['xg_share'])
        form=float(goalie['shrunk_gsax_per_60'])
        if not math.isfinite(share) or not 0 <= share <= 1 or not math.isfinite(form):
            raise ValueError('Invalid candidate statistic')
        values[side]=(share,form)
    return list(base)+[values['home'][0]-values['away'][0],values['home'][1]-values['away'][1]]
