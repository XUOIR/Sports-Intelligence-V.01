"""Saved forward-cohort grading, paired market comparison and closing value.

No provider calls, retroactive forecasts, manual wagers or approval decisions.
"""
from datetime import timedelta
import math
from sqlalchemy import select
from .clock import now,aware
from .models import PaperForecast,PaperPriceObservation,ProviderState


def probability(value):
    value=float(value)
    if not math.isfinite(value) or not 0<value<1:raise ValueError('Invalid saved forecast probability')
    return value


def score(probabilities,outcomes):
    if not probabilities:return {'games':0,'brier':None,'log_loss':None,'accuracy':None,'directional_games':0}
    if len(probabilities)!=len(outcomes):raise ValueError('Paired scoring arrays required')
    p=[probability(v) for v in probabilities]
    if any(type(y) is not bool for y in outcomes):raise ValueError('Explicit final outcomes required')
    decisive=[(q,y) for q,y in zip(p,outcomes) if q!=.5]
    return {'games':len(p),'brier':sum((q-int(y))**2 for q,y in zip(p,outcomes))/len(p),
        'log_loss':-sum(math.log(q if y else 1-q) for q,y in zip(p,outcomes))/len(p),
        'accuracy':sum((q>.5)==y for q,y in decisive)/len(decisive) if decisive else None,
        'directional_games':len(decisive)}


def calibration(probabilities,outcomes):
    rows=[];z=1.95996398454
    for i in range(10):
        group=[(probability(p),int(y)) for p,y in zip(probabilities,outcomes) if i/10<=float(p)<(i+1)/10]
        if not group:continue
        n=len(group);observed=sum(y for _,y in group)/n;denominator=1+z*z/n
        center=(observed+z*z/(2*n))/denominator
        half=z*math.sqrt(observed*(1-observed)/n+z*z/(4*n*n))/denominator
        rows.append({'lower':i/10,'upper':(i+1)/10,'games':n,'mean_probability':sum(p for p,_ in group)/n,
            'observed_home_win_rate':observed,'wilson_low':center-half,'wilson_high':center+half})
    return rows


def admitted_price(observation,forecast):
    try:
        data=observation.data;observed=aware(observation.observed_at);source=aware(data['source_at'])
        start=aware(forecast.start_at)
        if (observation.forecast_id!=forecast.id or observation.status!='VALID' or observed>=start or observed<aware(forecast.captured_at)
                or observed>now() or not timedelta(0)<=observed-source<=timedelta(minutes=5)
                or data.get('bookmaker') not in {'playnow','bclc'}):return None
        h,a=float(data['home_odds']),float(data['away_odds'])
        if not all(math.isfinite(x) and x>1 for x in (h,a)):return None
        return {'home_odds':h,'away_odds':a,'market_home_probability':(1/h)/(1/h+1/a),
            'source_at':source.isoformat(),'observed_at':observed.isoformat(),'forecast_id':forecast.id,'bookmaker':data['bookmaker'],
            'home_edge':float(forecast.home_probability)-1/h,
            'away_edge':1-float(forecast.home_probability)-1/a,'observation_id':observation.id}
    except (KeyError,TypeError,ValueError,OverflowError):return None


async def cohort(session,version):
    rows=(await session.scalars(select(PaperForecast).where(PaperForecast.model_version==version)
        .order_by(PaperForecast.start_at,PaperForecast.id))).all()
    observations=(await session.scalars(select(PaperPriceObservation).join(PaperForecast)
        .where(PaperForecast.model_version==version).order_by(PaperPriceObservation.observed_at,PaperPriceObservation.id))).all()
    by_id={r.id:r for r in rows};valid={};first={};closing={}
    for obs in observations:
        row=by_id[obs.forecast_id]
        if row.captured_at is None:continue
        value=admitted_price(obs,row)
        if value is None:continue
        valid[obs.id]=value;first.setdefault(row.id,value)
        if (aware(value['source_at'])>=aware(row.start_at)-timedelta(minutes=5)
                and aware(value['observed_at'])>=aware(row.start_at)-timedelta(minutes=5)):
            closing[row.id]=value
    captured=[]
    for row in rows:
        if row.captured_at is None or not aware(row.captured_at)<aware(row.start_at) or aware(row.captured_at)>now():continue
        try:probability(row.home_probability)
        except (TypeError,ValueError):continue
        captured.append(row)
    resolved=[r for r in captured if r.resolution=='FINAL' and type(r.result_home_win) is bool and aware(r.start_at)<now()]
    paired=[r for r in resolved if r.id in first]
    p=[float(r.home_probability) for r in resolved];y=[r.result_home_win for r in resolved]
    all_score=score(p,y)
    paired_model=score([float(r.home_probability) for r in paired],[r.result_home_win for r in paired])
    market=score([first[r.id]['market_home_probability'] for r in paired],[r.result_home_win for r in paired])
    positions=[];clv=[]
    for row in captured:
        pos=row.position
        if not pos:continue
        observed=valid.get(pos.get('observation_id'))
        side='home' if pos.get('home') is True else 'away'
        try:
            odds=float(pos['odds']);edge=observed[side+'_edge'] if observed else None
            if (not observed or observed['forecast_id']!=row.id or odds!=observed[side+'_odds'] or edge<.03
                    or pos['selection']!=getattr(row,side) or float(pos['units'])!=1
                    or type(pos.get('home')) is not bool or pos.get('bookmaker')!=observed['bookmaker']
                    or aware(pos['source_at'])!=aware(observed['source_at'])
                    or aware(pos['observed_at'])!=aware(observed['observed_at'])):continue
        except (KeyError,TypeError,ValueError):continue
        positions.append(row)
        last=closing.get(row.id)
        if last and aware(row.start_at)<=now():clv.append(odds/last[side+'_odds']-1)
    settled=[r for r in positions if r in resolved]
    wins=sum(r.result_home_win==r.position['home'] for r in settled)
    net=sum(float(r.position['odds'])-1 if r.result_home_win==r.position['home'] else -1 for r in settled)
    first_at=min((aware(r.captured_at) for r in captured),default=None)
    return {'version':version,'forecasts':len(captured),'fixtures_seen':len(rows),'blocked':len(rows)-len(captured),
        'resolved':len(resolved),'pending':len(captured)-len(resolved)-sum(r.resolution=='VOID' for r in captured),
        'scores':all_score,'paired_model':paired_model,'paired_market':market,
        'paired_brier_improvement':market['brier']-paired_model['brier'] if paired else None,
        'calibration':calibration(p,y),'matched_prices':len(first),'resolved_price_pairs':len(paired),
        'positions':len(positions),'settled_positions':len(settled),'wins':wins,'losses':len(settled)-wins,
        'profit_units':net,'roi_percent':100*net/len(settled) if settled else None,
        'closing_pairs':len(clv),'mean_closing_value_percent':100*sum(clv)/len(clv) if clv else None,
        'days_collecting':(now()-first_at).total_seconds()/86400 if first_at else 0,
        'first_captured_at':first_at.isoformat() if first_at else None,
        'operational_review_ready':bool(first_at and now()-first_at>=timedelta(days=14) and len(paired)>=100),
        'approved_for_wagers':False,
        'records':[{'fixture_id':r.fixture_id,'home':r.home,'away':r.away,'start_at':aware(r.start_at).isoformat(),
            'captured_at':aware(r.captured_at).isoformat() if r.captured_at else None,
            'home_probability':str(r.home_probability) if r.home_probability is not None else None,
            'issue':r.issue,'resolution':r.resolution,'result_home_win':r.result_home_win,
            'position':r.position if r in positions else None,'prices':first.get(r.id)} for r in reversed(rows[-100:])],
        'note':'Forward forecasts only. Closing value requires both prices actually observed in the final five minutes before scheduled puck drop. Missing closing observations stay unscored. A workflow review is not model approval.'}
