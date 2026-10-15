from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
import pytest
from app.clock import now
from app.nhl_factors import normalized_factors
from app.nhl_data import team_context


def inputs():
    at=now();observed=at-timedelta(minutes=2)
    sample={'status':'available','sample_games':5,'latest_game_date':str((at-timedelta(days=1)).date())}
    stats={'classification':'observed_pre_anchor_descriptive_statistics','as_of_date':str(at.date()),
        'cache_observed_at':observed.isoformat(),'sources':{key:{'observed_at':observed.isoformat(),
        'published_at':(at-timedelta(hours=2)).isoformat()} for key in ('team','goalie')},
        'teams':{},'team_context':{},'goalie_candidates':[]}
    for side,team,goalie in [('home','TOR','Home Starter'),('away','EDM','Away Starter')]:
        stats['teams'][side]={**sample,'team':team,'xg_share':'.52'}
        stats['team_context'][side]={key:{**sample,'xgf_per_60':'2','xga_per_60':'2'}
            for key in ('power_play','penalty_kill','home_venue','away_venue')}
        stats['goalie_candidates'].append({**sample,'latest_team':team,'name':goalie,'gsax':'2',
            'ice_time_seconds':'18000'})
    starters={'source_at':observed.isoformat(),'observed_at':observed.isoformat(),
        'payload':{'confirmed':True,'home':'Home Starter','away':'Away Starter','source_url':'https://www.nhl.com/news/starters'}}
    form={side:{'days_rest':2} for side in ('home','away')}
    return stats,starters,form,at


def test_equal_evidence_produces_neutral_research_inputs_not_a_prediction():
    result=normalized_factors(*inputs())
    assert all(Decimal(value)==0 for value in result['factors'].values())
    assert result['approved_for_prediction'] is False and result['classification']=='normalized_inputs_not_validated_prediction'
    assert 'probability' not in result


def test_goalie_rate_is_exposure_invariant_and_missing_exposure_is_rejected():
    stats,starters,form,at=inputs()
    stats['goalie_candidates'][0].update(gsax='4',ice_time_seconds='36000')
    assert Decimal(normalized_factors(stats,starters,form,at)['factors']['goalie_personnel'])==0
    del stats['goalie_candidates'][0]['ice_time_seconds']
    with pytest.raises(KeyError):normalized_factors(stats,starters,form,at)


def test_direction_and_clipping_with_unequal_samples_preserve_observed_facts():
    stats,starters,form,at=inputs()
    stats['teams']['home']['xg_share']='.8';form['home']['days_rest']=10;form['away']['days_rest']=0
    stats['goalie_candidates'][0]['gsax']='100'
    result=normalized_factors(stats,starters,form,at)['factors']
    assert all(Decimal(result[key])==1 for key in ('goalie_personnel','expected_goals','rest_fatigue'))
    assert stats['goalie_candidates'][0]['gsax']=='100'


@pytest.mark.parametrize('mutation',[
    lambda c,s,f,a:c.update(cache_observed_at=(a+timedelta(seconds=1)).isoformat()),
    lambda c,s,f,a:c['sources']['team'].update(published_at=(a+timedelta(seconds=1)).isoformat()),
    lambda c,s,f,a:s.update(observed_at=(a+timedelta(seconds=1)).isoformat()),
    lambda c,s,f,a:s['payload'].update(confirmed=False),
    lambda c,s,f,a:s['payload'].update(home='Probable Starter'),
    lambda c,s,f,a:c['goalie_candidates'].append(deepcopy(c['goalie_candidates'][0])),
    lambda c,s,f,a:c['teams']['home'].update(latest_game_date=str(a.date())),
    lambda c,s,f,a:c['team_context']['home']['power_play'].update(sample_games=2),
    lambda c,s,f,a:f['home'].update(days_rest=True),
])
def test_missing_ambiguous_or_post_anchor_facts_cannot_be_normalized(mutation):
    values=inputs();mutation(*values)
    with pytest.raises(ValueError):normalized_factors(*values)


def test_strength_rates_sum_exposure_and_exclude_target_day_and_playoffs():
    at=now().date();rows=[]
    for i in range(4):
        day=at-timedelta(days=i)
        for situation in ('all','5on4','4on5'):
            rows.append({'season':'2026','gameId':f'202602{i+1:04}','gameDate':day.strftime('%Y%m%d'),
                'playerTeam':'TOR','opposingTeam':'EDM','home_or_away':'HOME','situation':situation,
                'xGoalsFor':str(i),'xGoalsAgainst':'1','goalsFor':'1','goalsAgainst':'1',
                'iceTime':str(600*i),'playoffGame':'0','xGoalsPercentage':'.5'})
    playoff={**rows[-1],'gameId':'2026030001','playoffGame':'1','xGoalsFor':'1000'};rows.append(playoff)
    result=team_context(rows,at,'TOR')
    assert result['power_play']['sample_games']==3
    assert Decimal(result['power_play']['xgf_per_60'])==6
    assert result['home_venue']['sample_games']==3
    assert result['away_venue']['status']=='insufficient_sample'
