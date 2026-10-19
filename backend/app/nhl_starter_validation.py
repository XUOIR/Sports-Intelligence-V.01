"""Grade observed goalie reports against explicit official postgame starter flags.

One bounded free request per completed fixture. Never confirms a pregame
lineup, infers a starter from ice time, changes a wager or calls paid providers.
"""
import asyncio
from datetime import timedelta
import hashlib
import json
import re
import math
from statistics import median
import httpx
from sqlalchemy import select,and_,or_
from sqlalchemy.dialects.postgresql import insert
from . import db
from .clock import now,aware
from .config import settings
from .limits import limits,BudgetExceeded
from .models import Evidence,Fixture,ProviderState,RuntimeLimit,AuditLog
from .dfo_public import canonical

PREFIX='starter-result:'
CONTRACT='nhl-explicit-postgame-starters-v2'
MAX_BYTES=1_000_000


def official_starters(payload,fixture):
    if (str(payload.get('id'))!=fixture.id.removeprefix('nhl:')
            or payload.get('gameState') not in {'OFF','FINAL'} or payload.get('gameType')!=2
            or aware(payload['startTimeUTC'])!=aware(fixture.commence_time)):
        raise ValueError('Official final fixture identity changed')
    result={}
    for side in ('home','away'):
        if payload[side+'Team']['abbrev']!=fixture.metrics.get(side+'_abbrev'):
            raise ValueError('Official starter team identity changed')
        goalies=payload['playerByGameStats'][side+'Team']['goalies']
        if not isinstance(goalies,list) or not 1<=len(goalies)<=4:
            raise ValueError('Official goalie list changed')
        starters=[row for row in goalies if row.get('starter') is True]
        if len(starters)!=1:
            raise ValueError('An explicit unique official starter flag is required')
        row=starters[0];identifier=row['playerId']
        if type(identifier) is not int or not 1_000_000<=identifier<=9_999_999:
            raise ValueError('Official starter ID is malformed')
        name=row.get('name',{}).get('default')
        if not isinstance(name,str) or not 2<=len(name)<=100:
            raise ValueError('Official starter name is malformed')
        result[side]={'player_id':str(identifier),'name':name}
    return result


def grade(reports,truth,cutoff):
    """Use the last *observed* report before the cutoff; no news-time backdating."""
    eligible=[]
    for row in reports:
        try:
            at=aware(row['observed_at']);payload=row['payload']
            if (payload.get('contract')!='dfo-public-goalie-report-v1'
                    or aware(payload['fixture_start_at'])!=aware(truth['start_at']) or at>cutoff):
                continue
            eligible.append((at,row['id'],payload))
        except (KeyError,TypeError,ValueError):
            continue
    if not eligible:return {side:{'status':'not_observed_before_cutoff'} for side in ('home','away')}
    at,identifier,payload=max(eligible,key=lambda item:(item[0],item[1]))
    if payload.get('missing_from_page'):
        return {side:{'status':'source_removed','report_id':identifier,'observed_at':at.isoformat()} for side in ('home','away')}
    report=payload['report']
    sides={}
    for side in ('home','away'):
        row=report['sides'][side];status=row.get('reported_status')
        admissible=(timedelta(0)<=cutoff-at<=timedelta(minutes=20)
            and status in {'expected','confirmed'} and re.fullmatch(r'\d{7}',row.get('player_id') or '')
            and (not row.get('reported_at') or aware(row['reported_at'])<=at))
        sides[side]={'status':'matched' if row['player_id']==truth['sides'][side]['player_id'] else 'mismatched',
            'report_status':status,'report_id':identifier,'observed_at':at.isoformat(),
            'reported_name':row.get('name'),'reported_player_id':row.get('player_id'),
            'reported_at':row.get('reported_at')} if admissible else {
                'status':'stale' if cutoff-at>timedelta(minutes=20) else 'unconfirmed_or_unmatched'}
    return sides


async def verify_fixture(fixture_id,*,transport=None):
    at=now();key=PREFIX+fixture_id
    async with db.Session.begin() as session:
        fixture=await session.get(Fixture,fixture_id)
        if (not fixture or fixture.sport!='NHL' or not re.fullmatch(r'nhl:\d{4}02\d{4}',fixture.id)
                or aware(fixture.commence_time)>=at or fixture.final_home_win is None):
            return {'status':'awaiting_final'}
        inserted=await session.execute(insert(ProviderState).values(provider=key,observed_at=at,
            info={'status':'started','contract':CONTRACT}).on_conflict_do_nothing().returning(ProviderState.provider))
        if inserted.scalar_one_or_none() is None:return {'status':'already_attempted'}
        circuit=await session.get(RuntimeLimit,'circuit:nhl')
        if circuit and (circuit.used or circuit.blocked_until and aware(circuit.blocked_until)>at):
            raise BudgetExceeded('Official NHL source is paused')
        await limits._increment(session,f'nhl:{at.date()}',1,settings.nhl_daily_requests)
        await limits._increment(session,f'nhl-starter-check:{at.date()}',1,16)
        await limits._increment(session,f'nhl-starter-wire:{at:%Y-%m}',MAX_BYTES,200_000_000)
        reports=(await session.scalars(select(Evidence).where(Evidence.fixture_id==fixture_id,
            Evidence.kind.in_(['nhl_goalie_report','nhl_goalie_observation']))
            .order_by(Evidence.observed_at,Evidence.id).limit(512))).all()
        revisions={r.payload['fingerprint']:r.payload for r in reports
            if r.kind=='nhl_goalie_report' and not r.payload.get('missing_from_page') and r.payload.get('fingerprint')}
        observations=[]
        for row in reports:
            payload=row.payload
            if row.kind=='nhl_goalie_observation' and not payload.get('missing_from_page'):
                revision=revisions.get(payload.get('fingerprint'))
                if revision is None:continue
                payload={**revision,**payload}
            observations.append({'id':row.id,'observed_at':aware(row.observed_at).isoformat(),
                'payload':{k:payload[k] for k in ('contract','fixture_start_at','report','missing_from_page') if k in payload}})
        start=aware(fixture.commence_time)
    try:
        url=f'https://api-web.nhle.com/v1/gamecenter/{fixture_id[4:]}/boxscore'
        async with httpx.AsyncClient(timeout=15,follow_redirects=False,transport=transport) as client:
            async with client.stream('GET',url,headers={'Accept-Encoding':'identity',
                    'User-Agent':'GSportsIntelligence/0.1 (bounded postgame starter verification)'}) as response:
                if (response.status_code!=200 or response.headers.get('content-encoding','identity')!='identity'
                        or response.headers.get('content-type','').split(';')[0] not in {'application/json'}):
                    raise ValueError('Official starter source response rejected')
                raw=bytearray()
                async for chunk in response.aiter_raw(chunk_size=16384):
                    if len(raw)+len(chunk)>MAX_BYTES:raise ValueError('Official starter response exceeds byte cap')
                    raw.extend(chunk)
        sides=official_starters(json.loads(raw),fixture)
        observed=now()
        truth={'status':'verified','contract':CONTRACT,'fixture_id':fixture_id,'start_at':start.isoformat(),
            'home':fixture.home,'away':fixture.away,'sides':sides,'observed_at':observed.isoformat(),
            'source_url':url,'source_sha256':hashlib.sha256(raw).hexdigest(),
            'observation_ids':[r['id'] for r in observations],
            'report_revisions':[r for r in observations if any(e.id==r['id'] and e.kind=='nhl_goalie_report' for e in reports)],
            'paid_credits':0}
        truth['at_t30']=grade(observations,truth,start-timedelta(minutes=30))
        truth['last_pregame']=grade(observations,truth,start-timedelta(microseconds=1))
        async with db.Session.begin() as session:
            row=await session.get(ProviderState,key,with_for_update=True)
            row.info,row.observed_at=truth,observed
            session.add(AuditLog(action='NHL_STARTER_RESULT_VERIFIED',entity_id=fixture_id,
                details={'source_sha256':truth['source_sha256'],'report_count':len(observations),'paid_credits':0}))
        return {'status':'verified','paid_credits':0}
    except (Exception,asyncio.CancelledError) as exc:
        async with db.Session.begin() as session:
            row=await session.get(ProviderState,key,with_for_update=True)
            row.info={**row.info,'status':'unavailable','category':type(exc).__name__,
                'reason':'Postgame starter verification did not complete; no automatic retry.',
                'failed_at':now().isoformat(),'paid_credits':0}
        if isinstance(exc,asyncio.CancelledError):raise
        return {'status':'unavailable','paid_credits':0}


async def cycle():
    if 'NHL' not in settings.active_sports:return
    async with db.Session() as session:
        pilot=await session.get(ProviderState,'nhl-goalie-pilot')
        if pilot is None or not pilot.info.get('expires_at'):return
        end=aware(pilot.info['expires_at']);began=end-timedelta(hours=72)
        ids=(await session.scalars(select(Fixture.id).outerjoin(Evidence,and_(Evidence.fixture_id==Fixture.id,
                Evidence.kind=='nhl_goalie_report'))
            .outerjoin(ProviderState,ProviderState.provider==PREFIX+Fixture.id)
            .where(Fixture.sport=='NHL',Fixture.final_home_win.is_not(None),
                or_(Evidence.id.is_not(None),and_(Fixture.commence_time>=began,Fixture.commence_time<end)),
                Fixture.commence_time<now(),Fixture.commence_time>now()-timedelta(days=7),ProviderState.provider.is_(None))
            .distinct().order_by(Fixture.id).limit(4))).all()
    for fixture_id in ids:await verify_fixture(fixture_id)


async def summary(session):
    rows=(await session.scalars(select(ProviderState).where(ProviderState.provider.like(PREFIX+'%'))
        .order_by(ProviderState.observed_at.desc()).limit(300))).all()
    verified=[r.info for r in rows if r.info.get('status')=='verified']
    pilot=await session.get(ProviderState,'nhl-goalie-pilot')
    first_seen={}
    if pilot and pilot.info.get('expires_at'):
        began=aware(pilot.info['expires_at'])-timedelta(hours=72)
        revisions=(await session.scalars(select(Evidence).where(Evidence.kind=='nhl_goalie_report',
            Evidence.observed_at>=began).order_by(Evidence.observed_at,Evidence.id).limit(512))).all()
        for row in revisions:
            try:
                if row.payload.get('missing_from_page') or aware(row.observed_at)>=aware(row.payload['fixture_start_at']):continue
                for side,report in row.payload['report']['sides'].items():
                    published=aware(report['reported_at']) if report.get('reported_at') else None
                    if published is None or not began<=published<=aware(row.observed_at):continue
                    key=(row.fixture_id,side,canonical(report.get('name') or ''),report.get('reported_status'),report['reported_at'])
                    first_seen.setdefault(key,(aware(row.observed_at)-published).total_seconds()/60)
            except (KeyError,TypeError,ValueError):continue
    ages=sorted(first_seen.values())
    upcoming=(await session.scalars(select(Fixture.id).join(Evidence,Evidence.fixture_id==Fixture.id)
        .where(Fixture.sport=='NHL',Evidence.kind=='nhl_goalie_report',Evidence.observed_at<Fixture.commence_time,
            Fixture.commence_time>now(),Fixture.commence_time<now()+timedelta(hours=24)).distinct())).all()
    def counts(checkpoint,status=None):
        values=[v for r in verified for v in r[checkpoint].values() if not status or v.get('report_status')==status]
        scored=[v for v in values if v['status'] in {'matched','mismatched'}]
        correct=sum(v['status']=='matched' for v in scored)
        return {'graded_sides':len(scored),'correct':correct,'accuracy':correct/len(scored) if scored else None,
            'missing_or_stale':len(values)-len(scored)}
    return {'mode':'source_validation','paid_credits':0,'completed_games_checked':len(verified),
        'upcoming_games_observed':len(upcoming),
        'unavailable_checks':len(rows)-len(verified),'at_t30':counts('at_t30'),
        'last_pregame':counts('last_pregame'),'confirmed':counts('last_pregame','confirmed'),
        'expected':counts('last_pregame','expected'),
        'new_report_age':{'samples':len(ages),'median_minutes':median(ages) if ages else None,
            'p95_minutes':ages[max(0,math.ceil(.95*len(ages))-1)] if ages else None},
        'records':[{k:r[k] for k in ('fixture_id','home','away','start_at','sides','at_t30','last_pregame','observed_at')}
                   for r in verified[:30]],
        'note':'Only reports actually observed before the cutoff are graded. Official postgame flags identify actual starters; they never confirm a pregame lineup.'}
