from datetime import timedelta
from types import SimpleNamespace
import math
import pytest
from sqlalchemy import select
from app.clock import now
from app.nhl_forward_metrics import score,calibration,admitted_price,cohort
from app.models import Fixture,PaperForecast,PaperPriceObservation,PersonalBet


def test_brier_log_loss_and_calibration_use_probabilities_and_explicit_outcomes():
    value=score([.75,.25],[True,False])
    assert value['brier']==.0625 and value['log_loss']==pytest.approx(-math.log(.75))
    assert value['accuracy']==1 and value['games']==2
    bins=calibration([.75,.25],[True,False])
    assert sum(r['games'] for r in bins)==2
    assert all(0<=r['wilson_low']<r['wilson_high']<=1 for r in bins)
    with pytest.raises(ValueError):score([.75],[None])
    assert score([],[])['brier'] is None
    assert score([.5],[True])['accuracy'] is None


def pair(row,at,h=2.,a=2.):
    return SimpleNamespace(id=1,forecast_id=row.id,status='VALID',observed_at=at,
        data={'source_at':at.isoformat(),'bookmaker':'playnow','home_odds':str(h),'away_odds':str(a)})


@pytest.mark.parametrize('change',['postgame','stale','future','other_forecast','other_book'])
def test_invalid_price_observations_cannot_populate_matched_market_metrics(change):
    at=now();row=SimpleNamespace(id=1,start_at=at+timedelta(hours=1),captured_at=at-timedelta(hours=1),home_probability='.6')
    obs=pair(row,at)
    if change=='postgame':row.start_at=at
    if change=='stale':obs.data['source_at']=(at-timedelta(minutes=6)).isoformat()
    if change=='future':obs.observed_at=at+timedelta(seconds=1)
    if change=='other_forecast':obs.forecast_id=2
    if change=='other_book':obs.data['bookmaker']='pinnacle'
    assert admitted_price(obs,row) is None


@pytest.mark.asyncio
async def test_same_game_market_comparison_closing_value_and_version_isolation(database):
    start=now()-timedelta(hours=3)
    async with database.begin() as s:
        s.add(Fixture(id='nhl:2026020001',sport='NHL',home='Home',away='Away',commence_time=start))
        row=PaperForecast(fixture_id='nhl:2026020001',model_version='tested',first_seen_at=start-timedelta(hours=2),
            captured_at=start-timedelta(hours=2),start_at=start,home='Home',away='Away',home_probability='.6',
            result_home_win=True,resolution='FINAL',settled_at=now())
        s.add(row);await s.flush()
        at=start-timedelta(hours=1)
        obs=PaperPriceObservation(forecast_id=row.id,identity='first',observed_at=at,status='VALID',
            data={'source_at':at.isoformat(),'bookmaker':'playnow','home_odds':'2.00','away_odds':'1.90'})
        s.add(obs);await s.flush()
        row.position={'home':True,'selection':'Home','units':'1','odds':'2.00','bookmaker':'playnow',
            'observation_id':obs.id,'source_at':at.isoformat(),'observed_at':at.isoformat()}
        close=start-timedelta(minutes=2)
        s.add(PaperPriceObservation(forecast_id=row.id,identity='close',observed_at=close,status='VALID',
            data={'source_at':close.isoformat(),'bookmaker':'playnow','home_odds':'1.80','away_odds':'2.10'}))
        s.add(PaperForecast(fixture_id='nhl:2026020001',model_version='other',first_seen_at=at,captured_at=at,
            start_at=start,home='Home',away='Away',home_probability='.01',result_home_win=True,resolution='FINAL'))
    async with database() as s:
        result=await cohort(s,'tested')
        assert result['forecasts']==result['resolved']==result['resolved_price_pairs']==1
        assert result['scores']['brier']==pytest.approx(.16)
        assert result['paired_market']['brier']>result['paired_model']['brier']
        assert result['roi_percent']==100 and result['wins']==1
        assert result['closing_pairs']==1 and result['mean_closing_value_percent']==pytest.approx(100*(2/1.8-1))
        assert result['approved_for_wagers'] is False and result['operational_review_ready'] is False


@pytest.mark.asyncio
async def test_nonclosing_quotes_cannot_be_labeled_closing_value(database):
    start=now()-timedelta(hours=3)
    async with database.begin() as s:
        s.add(Fixture(id='nhl:2026020001',sport='NHL',home='Home',away='Away',commence_time=start))
        row=PaperForecast(fixture_id='nhl:2026020001',model_version='tested',first_seen_at=start-timedelta(hours=2),
            captured_at=start-timedelta(hours=2),start_at=start,home='Home',away='Away',home_probability='.6')
        s.add(row);await s.flush()
        at=start-timedelta(minutes=10)
        obs=PaperPriceObservation(forecast_id=row.id,identity='only',observed_at=at,status='VALID',
            data={'source_at':at.isoformat(),'bookmaker':'playnow','home_odds':'2','away_odds':'2'})
        s.add(obs);await s.flush()
        row.position={'home':True,'selection':'Home','units':'1','odds':'2','bookmaker':'playnow',
            'observation_id':obs.id,'source_at':at.isoformat(),'observed_at':at.isoformat()}
    async with database() as s:
        result=await cohort(s,'tested')
        assert result['positions']==1 and result['closing_pairs']==0
        assert result['mean_closing_value_percent'] is None
