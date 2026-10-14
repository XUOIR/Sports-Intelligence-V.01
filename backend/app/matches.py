"""Shared NHL score cache. Browser reads never call a metered provider.

Dates are bounded to a fortnight. A durable queue, adaptive per-day cache and
distributed leases keep upstream traffic independent of browser/tab count.
Scores are display data only; they cannot supply pregame model evidence.
"""
import re
from datetime import date, datetime, time, timedelta
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert
from . import db
from .clock import now, aware
from .config import settings, PACIFIC
from .models import ProviderState, RuntimeLimit, Fixture, State
from .limits import limits, BudgetExceeded
from .http import http, ProviderError
from .readiness import fresh_recommendation

LIVE={'LIVE','CRIT'}
FINAL={'FINAL','OFF'}

def selected_date(value=None):
    if value is None:return now().date()
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
        raise ValueError('Choose a date in YYYY-MM-DD format')
    day=date.fromisoformat(value)
    if abs((day-now().date()).days)>7:raise ValueError('Choose a date within seven days of today')
    return day

def text(value):
    if isinstance(value,dict):value=value.get('default')
    if not isinstance(value,str) or not 1<=len(value.strip())<=160:raise ProviderError('NHL team name changed')
    return value.strip()

def score(value):
    if value is None:return None
    if type(value) is not int or not 0<=value<=99:raise ProviderError('NHL score changed')
    return value

def parse_scores(payload,day):
    if not isinstance(payload,dict) or payload.get('currentDate')!=str(day):raise ProviderError('NHL score date changed')
    games=payload.get('games')
    if not isinstance(games,list) or len(games)>32:raise ProviderError('NHL score games changed')
    result=[];seen=set()
    for game in games:
        try:
            gid=game['id'];start=aware(game['startTimeUTC']);state=game['gameState']
            if type(gid) is not int or gid<=0 or gid in seen or game['gameDate']!=str(day):raise ValueError()
            if state not in LIVE|FINAL|{'FUT','PRE'}:raise ValueError()
            if abs((start.date()-day).days)>1:raise ValueError()
            teams={side:game[side+'Team'] for side in ('home','away')}
            scores={side:score(team.get('score')) for side,team in teams.items()}
            if state in LIVE|FINAL and any(v is None for v in scores.values()):raise ValueError()
            schedule=game.get('gameScheduleState','OK')
            if schedule not in {'OK','PPD','SUSP','CNCL','TBD'}:raise ValueError()
            period=game.get('periodDescriptor') or {};clock=game.get('clock') or {}
            number=period.get('number');remaining=clock.get('timeRemaining')
            if number is not None and (type(number) is not int or not 1<=number<=20):raise ValueError()
            if remaining is not None and (not isinstance(remaining,str) or not re.fullmatch(r'\d{2}:\d{2}',remaining)):raise ValueError()
            result.append({'id':f'nhl:{gid}','sport':'NHL','commence_time':start.isoformat(),
                'game_state':state,'schedule_state':schedule,
                **{side:text(team.get('name') or team.get('commonName')) for side,team in teams.items()},
                **{side+'_abbrev':text(team['abbrev']) for side,team in teams.items()},
                **{side+'_score':value if state in LIVE|FINAL else None for side,value in scores.items()},
                'period':number,'period_type':period.get('periodType') if period.get('periodType') in {'REG','OT','SO'} else None,
                'clock':remaining,'intermission':clock.get('inIntermission') is True})
            seen.add(gid)
        except (KeyError,TypeError,ValueError):raise ProviderError('NHL score schema changed; previous scores retained') from None
    return result

def interval(games,day):
    if day<now().date()-timedelta(days=1):return 86400
    if any(g['game_state'] in LIVE for g in games):return 30
    if day<now().date():return 86400
    if day>now().date():return 3600
    # Look more often around puck drop, without pretending an overdue game is live.
    if any(g['game_state'] not in FINAL and g['schedule_state']=='OK' and
           abs((aware(g['commence_time'])-now()).total_seconds())<3600 for g in games):return 60
    return 300 if any(g['game_state'] not in FINAL for g in games) else 900

def due(cached):
    # The scheduler is on a fixed cadence. Allow a small timer/DB jitter window,
    # while the durable leases prevent concurrent repeats across instances.
    return not cached or aware(cached.info['next_at'])<=now()+timedelta(seconds=2)

async def enqueue(day):
    async with db.Session.begin() as session:
        # One date request is shared across visitors. It cannot reset cache TTLs,
        # reservations or cooldowns. Active views renew demand every ten minutes.
        await session.execute(insert(ProviderState).values(provider=f'nhl-request:{day}',observed_at=now(),info={'date':str(day)})
            .on_conflict_do_update(index_elements=[ProviderState.provider],set_={'observed_at':now()},
                where=ProviderState.observed_at<now()-timedelta(minutes=10)))

async def refresh_day(day):
    async with db.Session() as session:
        cached=await session.get(ProviderState,f'nhl-score:{day}')
        if not due(cached):return
    if not await limits.lease(f'nhl-score:{day}',25):return
    try:
        started=now()
        games=parse_scores(await http.request('nhl_scores','GET',f'https://api-web.nhle.com/v1/score/{day}'),day)
        seconds=interval(games,day)
        await limits.observe(f'nhl-score:{day}',{'games':games,'interval_seconds':seconds,
            'next_at':(started+timedelta(seconds=seconds)).isoformat(),'error':None})
    except (ProviderError,BudgetExceeded):
        # Failed fetches keep the original successful observation timestamp.
        # Store the failure separately, including when no good payload exists.
        await limits.observe(f'nhl-error:{day}',{'at':now().isoformat()})
        if not await limits.blocked('nhl_scores'):await limits.trip('nhl_scores')

async def tick():
    if 'NHL' not in settings.active_sports or not settings.nhl_score_daily_requests:return
    if not await limits.lease('nhl-score-tick',25) or await limits.blocked('nhl_scores'):return
    today=now().date()
    async with db.Session() as session:
        pending=(await session.scalars(select(ProviderState).where(ProviderState.provider.like('nhl-request:%'))
            .where(ProviderState.observed_at>now()-timedelta(minutes=20)).order_by(ProviderState.observed_at).limit(15))).all()
        previous=await session.get(ProviderState,f'nhl-score:{today-timedelta(days=1)}')
        caches=(await session.scalars(select(ProviderState).where(ProviderState.provider.like('nhl-score:%')))).all()
        next_at={row.provider:aware(row.info['next_at']) for row in caches}
    # Today's feed always runs; yesterday continues if a game crosses midnight.
    days=[today]
    if previous and any(g['game_state'] in LIVE for g in previous.info['games']):days.append(today-timedelta(days=1))
    for row in pending:
        try:day=selected_date(row.info['date'])
        except ValueError:continue
        if day not in days and next_at.get(f'nhl-score:{day}',now())<=now()+timedelta(seconds=2):days.append(day);break
    for day in days:
        if await limits.blocked('nhl_scores'):break
        await refresh_day(day)
    async with db.Session.begin() as session:
        await session.execute(delete(ProviderState).where(ProviderState.provider.like('nhl-request:%'),ProviderState.observed_at<now()-timedelta(days=1)))
        await session.execute(delete(ProviderState).where(ProviderState.provider.like('nhl-score:%'),ProviderState.observed_at<now()-timedelta(days=8)))
        await session.execute(delete(ProviderState).where(ProviderState.provider.like('nhl-error:%'),ProviderState.observed_at<now()-timedelta(days=8)))

async def feed(session,day):
    cached=await session.get(ProviderState,f'nhl-score:{day}')
    failed=await session.get(ProviderState,f'nhl-error:{day}')
    circuit=await session.get(RuntimeLimit,'circuit:nhl_scores')
    budget=await session.get(RuntimeLimit,f'nhl_scores:{now().date()}')
    blocked=bool(not settings.nhl_score_daily_requests or budget and budget.used>=settings.nhl_score_daily_requests or
                 circuit and circuit.blocked_until and aware(circuit.blocked_until)>now())
    names=await session.get(ProviderState,'nhl-team-names')
    fixtures=(await session.scalars(select(Fixture).where(Fixture.sport=='NHL',
        Fixture.commence_time>=datetime.combine(day,time.min,tzinfo=PACIFIC),Fixture.commence_time<datetime.combine(day+timedelta(days=1),time.min,tzinfo=PACIFIC)).limit(40))).all()
    lookup={f.id:f for f in fixtures}
    games=[dict(g) for g in cached.info['games']] if cached else []
    stale=not cached or now()<aware(cached.observed_at) or now()>aware(cached.info['next_at'])+timedelta(seconds=60)
    if cached and failed and aware(failed.observed_at)>=aware(cached.observed_at):stale=True
    for game in games:
        if names:
            game.update({side:names.info['teams'].get(game[side+'_abbrev'],game[side]) for side in ('home','away')})
        fixture=lookup.get(game['id'])
        state='WATCH';reason='No verified pregame decision recorded';verified=False
        if fixture:
            game.update(home=fixture.home,away=fixture.away)
            state=fixture.state.value;reason=fixture.reason
            if state=='RECOMMEND':
                verified=not stale and fresh_recommendation(fixture) and game['game_state'] in {'FUT','PRE'} and game['schedule_state']=='OK'
                if not verified:state='HOLD';reason='Fresh pregame re-verification required'
        game.update(decision=state,reason=reason,verified_play=verified,detail_available=fixture is not None)
    if not cached:
        games=[{'id':f.id,'sport':'NHL','home':f.home,'away':f.away,'commence_time':aware(f.commence_time).isoformat(),
            'game_state':'UNKNOWN','schedule_state':'OK','home_score':None,'away_score':None,'period':None,'clock':None,
            'decision':'HOLD' if f.state==State.RECOMMEND else f.state.value,'verified_play':False,'reason':'Score feed awaiting sync',
            'detail_available':True} for f in fixtures]
    rank=lambda g:0 if g['game_state'] in LIVE else 2 if g['game_state'] in FINAL else 1
    games.sort(key=lambda g:(rank(g),g['commence_time'],g['id']))
    return {'date':str(day),'today':str(now().date()),'min_date':str(now().date()-timedelta(days=7)),
        'max_date':str(now().date()+timedelta(days=7)),'games':games,'source':'NHL public score feed',
        'observed_at':aware(cached.observed_at) if cached else None,'stale':stale,'paused':blocked,
        'interval_seconds':cached.info['interval_seconds'] if cached else None,'server_time':now(),
        'valid_until':aware(cached.info['next_at'])+timedelta(seconds=60) if cached else None,
        'next_attempt_at':aware(circuit.blocked_until) if circuit and circuit.blocked_until and blocked else None}
