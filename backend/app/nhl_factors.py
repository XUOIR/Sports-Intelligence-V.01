"""Reproducible research inputs, never an approved forecast or a gate grant.

Versioned scales are fixed before evaluation, not tuned to current outcomes.
Missing facts fail closed. No network, database, fallback or zero imputation.
"""
from datetime import timedelta
from decimal import Decimal
import unicodedata
from .clock import aware
from .maths import decimal

CONTRACT='nhl-factor-research-v1'


def clip(value):return max(Decimal(-1),min(Decimal(1),value))


def normalized_factors(context, starters, form, anchor):
    at=aware(anchor)
    if (context.get('classification')!='observed_pre_anchor_descriptive_statistics'
            or context.get('as_of_date')!=at.date().isoformat()
            or not timedelta(0)<=at-aware(context['cache_observed_at'])<=timedelta(hours=26)):
        raise ValueError('Current pre-anchor statistics required')
    sources=context.get('sources',{})
    if set(sources)!={'team','goalie'} or any(aware(s['observed_at'])>at or aware(s['published_at'])>at for s in sources.values()):
        raise ValueError('Pre-anchor source publication/observation required')
    if (not starters.get('payload',{}).get('confirmed') is True
            or not at-timedelta(minutes=30)<=aware(starters['source_at'])<=aware(starters['observed_at'])<=at
            or not starters['payload'].get('source_url','').startswith('https://')):
        raise ValueError('Both confirmed starters require current pre-anchor evidence')

    def name(value):
        return ' '.join(unicodedata.normalize('NFKC',str(value)).casefold().split())

    def sample(row):
        if (not isinstance(row,dict) or row.get('status')!='available' or type(row.get('sample_games')) is not int
                or not 3<=row['sample_games']<=10 or not row.get('latest_game_date')
                or row['latest_game_date']>=at.date().isoformat()):
            raise ValueError('At least three eligible prior games required for every factor')
        return row

    values={}
    for side in ('home','away'):
        team=sample(context['teams'][side]);code=team['team']
        matches=[g for g in context['goalie_candidates'] if g.get('latest_team')==code
                 and name(g.get('name'))==name(starters['payload'].get(side))]
        if len(matches)!=1:raise ValueError('Confirmed starter must match exactly one same-team goalie')
        goalie=sample(matches[0]);ice=decimal(goalie['ice_time_seconds'])
        if ice<=0:raise ValueError('Positive goalie exposure required')
        share=decimal(team['xg_share'])
        if not 0<=share<=1:raise ValueError('Invalid 5v5 xG share')
        rest=form[side]['days_rest']
        if type(rest) is not int or not 0<=rest<=366:raise ValueError('Verified rest days required')
        splits=context['team_context'][side]
        pp=sample(splits['power_play']);pk=sample(splits['penalty_kill'])
        venue=sample(splits['home_venue' if side=='home' else 'away_venue'])
        rates=[decimal(r[k]) for r,k in ((pp,'xgf_per_60'),(pk,'xga_per_60'),(venue,'xgf_per_60'),(venue,'xga_per_60'))]
        if any(rate<0 for rate in rates):raise ValueError('Nonnegative expected-goal rates required')
        values[side]={'goalie':decimal(goalie['gsax'])*3600/ice,'xg':share,'rest':min(rest,4),
            'pp':rates[0],'pk':rates[1],'venue':rates[2]-rates[3]}
    h,a=values['home'],values['away']
    venue=clip((h['venue']-a['venue'])/2)
    special=clip(((h['pp']+a['pk'])-(a['pp']+h['pk']))/4)
    factors={'goalie_personnel':clip(h['goalie']-a['goalie']),
        'expected_goals':clip((h['xg']-a['xg'])/Decimal('.20')),
        'rest_fatigue':clip(Decimal(h['rest']-a['rest'])/3),
        'venue_special_teams':(venue+special)/2}
    return {'contract':CONTRACT,'classification':'research_inputs_only',
        'factors':{k:str(v) for k,v in factors.items()},'raw':{s:{k:str(v) for k,v in row.items()} for s,row in values.items()},
        'starter_evidence':starters,'approved_for_prediction':False}
