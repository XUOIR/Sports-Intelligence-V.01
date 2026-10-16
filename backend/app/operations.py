"""Private operational status. Reading this module never contacts a provider."""
from datetime import timedelta,timezone
from decimal import Decimal
from sqlalchemy import select,func
from .clock import now,aware
from .config import settings
from .models import RuntimeLimit,ProviderCall,ProviderState,Fixture,Snapshot,ModelValidation
from .readiness import validated_model
from .model_config import NHL_WEIGHTS
from .limits import limits as guard
from .verification import price_pair
from .market_display import latest_quotes

async def reported_ai_usage(session, at):
    row=await session.get(ProviderState,'allowance:openrouter')
    result={'status':'not_checked','checked_at':None,'daily_usd':None,'monthly_usd':None,'period_timezone':'UTC'}
    if row is None:return result
    info=row.info
    result['checked_at']=aware(row.observed_at).isoformat()
    if info.get('status')!='verified':return {**result,'status':'unavailable'}
    if not timedelta(0)<=at-aware(row.observed_at)<=timedelta(hours=1):return {**result,'status':'stale'}
    # A cached total from yesterday must not be labeled as today's spending.
    checked=aware(row.observed_at).astimezone(timezone.utc)
    current=at.astimezone(timezone.utc)
    for key,field,same_period in [('daily_usd','key_daily_used_usd',checked.date()==current.date()),
        ('monthly_usd','key_monthly_used_usd',(checked.year,checked.month)==(current.year,current.month))]:
        try:
            value=Decimal(info[field])
            if same_period and value.is_finite() and value>=0:result[key]=str(value)
        except (KeyError,TypeError,ArithmeticError):pass
    result['status']='verified' if result['daily_usd'] is not None and result['monthly_usd'] is not None else 'partial'
    return result

async def operational_status(session):
    at=now()
    rows=(await session.scalars(select(RuntimeLimit).where(RuntimeLimit.key.in_([
        'control:paid',*[f'circuit:{p}' for p in ('odds','openrouter','pandascore')],
        f'odds:{at.date()}',f'odds-month:{at:%Y-%m}',f'openrouter:{at.date()}',f'pandascore:{at.date()}',
        f'openrouter-usd:{at.date()}',f'openrouter-usd-month:{at:%Y-%m}'])))).all()
    limits={r.key:r for r in rows}
    def used(key):return limits[key].used if key in limits else 0
    paused=bool(used('control:paid'))
    score_budget=await session.get(RuntimeLimit,f'nhl_scores:{at.date()}')
    advanced_batch=await session.get(RuntimeLimit,f'moneypuck-batch:{at.date()}')
    advanced_wire=await session.get(RuntimeLimit,f'moneypuck-wire:{at:%Y-%m}')
    advanced_state=await session.get(ProviderState,'nhl-advanced-import')
    advanced_cache=await session.get(ProviderState,'nhl-advanced-statistics')
    providers=[]
    for provider,enabled,cap in [('odds',bool(settings.odds_key and settings.odds_daily_credits),settings.odds_daily_credits),
        ('openrouter',settings.llm_enabled,settings.llm_daily_requests),
        ('pandascore',bool(settings.esports_key and settings.pandascore_daily_requests and set(settings.active_sports)&{'CS2','VAL','LOL'}),settings.pandascore_daily_requests)]:
        circuit=limits.get(f'circuit:{provider}')
        blocked=bool(circuit and (circuit.used or circuit.blocked_until and aware(circuit.blocked_until)>at))
        last=await session.scalar(select(ProviderCall).where(ProviderCall.provider==provider).order_by(ProviderCall.created_at.desc()).limit(1))
        state=await session.get(ProviderState,provider)
        providers.append({'provider':provider,'enabled':enabled,'blocked':blocked,'daily_used':used(f'{provider}:{at.date()}'),
            'daily_cap':cap,'quota':state.info if state else None,'quota_observed_at':aware(state.observed_at) if state else None,
            'last_attempt':{'at':aware(last.created_at),'status':last.status,'category':last.error_category} if last else None})
    future=(await session.scalars(select(Fixture).where(Fixture.sport=='NHL',Fixture.commence_time>at,
        Fixture.commence_time<at+timedelta(days=3)).order_by(Fixture.commence_time).limit(100))).all()
    ids=[f.id for f in future]
    snapshots=(await session.scalars(select(Snapshot).where(Snapshot.fixture_id.in_(ids)))).all() if ids else []
    model=await session.scalar(select(ModelValidation).where(ModelValidation.sport=='NHL',ModelValidation.approved.is_(True)).order_by(ModelValidation.created_at.desc()).limit(1))
    mature=await session.scalar(select(func.count()).select_from(Snapshot).join(Fixture).where(Fixture.sport=='NHL',
        Snapshot.final_home_win.is_not(None),Snapshot.baseline_home_probability.is_not(None)))
    saved_quotes=await latest_quotes(session,ids)
    prices=0
    for fixture in future:
        try:
            pair=price_pair(saved_quotes.get(fixture.id,[]),fixture,at)
            if (fixture.metrics.get('execution_source_present') is True
                and timedelta(0)<=at-aware(fixture.metrics['execution_verified_at'])<=timedelta(minutes=5)
                and pair and timedelta(0)<=at-pair[0]<=timedelta(minutes=5)):prices+=1
        except (KeyError,TypeError,ValueError):pass
    personnel=0
    for fixture in future:
        try:
            if fixture.metrics.get('personnel_confirmed') is True and timedelta(0)<=at-aware(fixture.metrics['confirmed_at'])<=timedelta(minutes=30):personnel+=1
        except (KeyError,ValueError,TypeError):pass
    factors=sum(set(f.metrics.get('factors',{}))==set(NHL_WEIGHTS) for f in future)
    usable=sum(s.baseline_home_probability is not None for s in snapshots)
    return {'active_sports':list(settings.active_sports),'paid_paused':paused,'providers':providers,
        'nhl_scores':{'daily_used':score_budget.used if score_budget else 0,'daily_cap':settings.nhl_score_daily_requests,'paid_credits':0},
        'nhl_statistics':{'enabled':settings.nhl_advanced_enabled,'status':advanced_state.info.get('status') if advanced_state else 'pending',
            'failure_stage':advanced_state.info.get('stage') if advanced_state and advanced_state.info.get('status')=='failed' else None,
            'failure_reason':advanced_state.info.get('reason') if advanced_state and advanced_state.info.get('status')=='failed' else None,
            'daily_imports_used':advanced_batch.used if advanced_batch else 0,'daily_imports_cap':1,
            'bytes_monthly_used':advanced_wire.used if advanced_wire else 0,'bytes_monthly_cap':settings.nhl_advanced_monthly_bytes,
            'observed_at':aware(advanced_cache.observed_at) if advanced_cache else None,
            'as_of_date':advanced_cache.info.get('as_of_date') if advanced_cache else None,'paid_credits':0},
        'odds_monthly_used':used(f'odds-month:{at:%Y-%m}'),'odds_monthly_cap':settings.odds_monthly_credits,
        'ai_daily_reserved_usd':str(Decimal(used(f'openrouter-usd:{at.date()}'))/1_000_000),'ai_daily_cap_usd':str(settings.llm_daily_usd),
        'ai_monthly_reserved_usd':str(Decimal(used(f'openrouter-usd-month:{at:%Y-%m}'))/1_000_000),'ai_monthly_cap_usd':str(settings.llm_monthly_usd),
        'ai_request_reservation_usd':str(settings.llm_request_usd),
        'ai_actual_usage':await reported_ai_usage(session,at),
        'nhl':{'upcoming':len(future),'fresh_price_pairs':prices,'confirmed_personnel':personnel,'advanced_factors':factors,
            'frozen_inputs':len(snapshots),'usable_frozen_inputs':usable,'labeled_training_records':int(mature or 0),
            'model_approved':validated_model(model),'required_partitions':[300,100,100]},
        'server_time':at,'odds_interval_minutes':None,'odds_refresh':await guard.odds_window(session),
        'cost_note':'Budgets retain failed and unconfirmed reservations. They are conservative limits, not a provider invoice.'}
