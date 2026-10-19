from datetime import timedelta
import hashlib
import io
import json
from types import SimpleNamespace
import zipfile
import httpx
import pytest
from sqlalchemy import select
from app.clock import now,aware
from app import nhl_candidate_bootstrap as bootstrap
from app.nhl_candidate_features import team_goaltending,vector
from app.nhl_candidate import forecast
from app.nhl_candidate_model import probability
from app.models import ProviderState,RuntimeLimit
from app.limits import BudgetExceeded


def goalie_rows(target):
    return [{'season':'2026','playerTeam':'MTL','opposingTeam':'TOR','home_or_away':'HOME','situation':'all',
        'gameId':f'20260200{i:02}','gameDate':str(target-timedelta(days=i)).replace('-',''),
        'playerId':'8480001','name':'Home Goalie','icetime':'3600','xGoals':'3','goals':'2'} for i in range(1,7)]


def test_team_form_excludes_the_target_game_and_future_relievers():
    day=now().date();rows=goalie_rows(day)
    before=team_goaltending(rows,day,'MTL',2026)
    rows.append({**rows[0],'gameId':'2026029999','gameDate':str(day).replace('-',''),'goals':'25'})
    assert team_goaltending(rows,day,'MTL',2026)==before
    assert before['sample_games']==6 and float(before['shrunk_gsax_per_60'])==pytest.approx(6/14)
    assert before['specific_starting_goalie_used'] is False


def inputs():
    at=now();start=at+timedelta(hours=2)
    stats=SimpleNamespace(observed_at=at-timedelta(hours=1),info={'schema_version':1,'as_of_date':str(at.date()),
        'model_approved_by_import':False,'sources':{'team':{'observed_at':(at-timedelta(hours=1)).isoformat(),
        'published_at':(at-timedelta(hours=2)).isoformat(),'sha256':'teams'},'goalie':{
        'observed_at':(at-timedelta(hours=1)).isoformat(),'published_at':(at-timedelta(hours=2)).isoformat(),'sha256':'goalies'}},
        'teams':{},'team_goaltending':{}})
    for code in ('MTL','TOR'):
        stats.info['teams'][code]={'status':'available','sample_games':6,'latest_game_date':str(at.date()-timedelta(days=1)),
            'target_date':str(at.date()),'team':code,'season':2026,'xg_share':'.52' if code=='MTL' else '.48'}
        stats.info['team_goaltending'][code]={**stats.info['teams'][code],'shrunk_gsax_per_60':'.1'}
    base=SimpleNamespace(id=1,captured_at=at-timedelta(hours=3),start_at=start,home='Home',away='Away',
        inputs={'model_sha256':'base','features':[.2,1,0],'input_archive_sha256':'archive'})
    fixture=SimpleNamespace(commence_time=start,home='Home',away='Away',metrics={'home_abbrev':'MTL','away_abbrev':'TOR'})
    bundle={'base_model_sha256':'base','fit':{'center':[0]*5,'scale':[1]*5,'coefficients':[0,1,0,0,1,1]},
        'calibration':{'coefficients':[0,1]}}
    return at,fixture,base,stats,bundle


def test_named_goalie_or_market_changes_do_not_bias_candidate_probability():
    at,f,b,s,model=inputs()
    expected,data=forecast(model,b,f,s,None,at)
    f.metrics.update(goalie_confirmations={'home':'Different Starter'},home_market_odds='1.01')
    actual,again=forecast(model,b,f,s,None,at)
    assert actual==expected and data==again
    assert len(data['features'])==5 and data['approved_for_wagers'] is False


@pytest.mark.parametrize('change',['postgame','wrong_base','future_source','stale','missing_goalie','thin_sample','target_day_stat'])
def test_candidate_missing_future_or_incompatible_inputs_fail_closed(change):
    at,f,b,s,model=inputs()
    if change=='postgame':f.commence_time=at
    if change=='wrong_base':b.inputs['model_sha256']='other'
    if change=='future_source':s.info['sources']['goalie']['observed_at']=(at+timedelta(seconds=1)).isoformat()
    if change=='stale':s.observed_at=at-timedelta(hours=27)
    if change=='missing_goalie':s.info.pop('team_goaltending')
    if change=='thin_sample':s.info['teams']['MTL']['sample_games']=4
    if change=='target_day_stat':s.info['teams']['MTL']['latest_game_date']=str(at.date())
    with pytest.raises(ValueError):forecast(model,b,f,s,None,at)


def test_bootstrap_derivation_cannot_relabel_a_different_import_version():
    at,f,b,s,model=inputs();teams=s.info.pop('team_goaltending')
    derived=SimpleNamespace(observed_at=at,info={'as_of_date':str(at.date()),'goalie_source_sha256':'other',
        'parent_observed_at':aware(s.observed_at).isoformat(),'teams':teams})
    with pytest.raises(ValueError):forecast(model,b,f,s,derived,at)


@pytest.mark.asyncio
async def test_bootstrap_has_one_durable_admission_and_preserves_import_timestamp(database):
    at=now();raw=io.BytesIO()
    fields=list(goalie_rows(at.date())[0]);body=','.join(fields)+'\n'
    body+='\n'.join(','.join(row[key] for key in fields) for row in goalie_rows(at.date()))+'\n'
    with zipfile.ZipFile(raw,'w',compression=zipfile.ZIP_DEFLATED) as z:z.writestr('goalies.csv',body)
    archive=raw.getvalue();digest=hashlib.sha256(archive).hexdigest();original=at-timedelta(hours=1)
    info={'schema_version':1,'as_of_date':str(at.date()),'team_games':6,'teams':{'MTL':{}},
        'sources':{'goalie':{'sha256':digest}}}
    async with database.begin() as s:
        s.add(ProviderState(provider='nhl-advanced-statistics',observed_at=original,info=info))
        s.add(RuntimeLimit(key=f'moneypuck-batch:{at.date()}',used=1))
    calls=[]
    # HTTP last-modified is expressed in GMT, not local clock components.
    from datetime import timezone
    stamp=(at-timedelta(hours=2)).astimezone(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
    def handle(request):
        calls.append(1);return httpx.Response(200,headers={'last-modified':stamp,'content-length':str(len(archive))},stream=httpx.ByteStream(archive))
    assert (await bootstrap.run(transport=httpx.MockTransport(handle)))['status']=='succeeded'
    with pytest.raises(BudgetExceeded):await bootstrap.run(transport=httpx.MockTransport(handle))
    async with database() as s:
        cache=await s.get(ProviderState,'nhl-advanced-statistics')
        assert aware(cache.observed_at)==original and cache.info==info
        assert (await s.get(RuntimeLimit,f'moneypuck-batch:{at.date()}')).used==1
        saved=await s.get(ProviderState,bootstrap.OUTPUT)
        assert saved.info['goalie_source_sha256']==digest
        assert saved.info['teams']['MTL']['sample_games']==6
    assert len(calls)==1
