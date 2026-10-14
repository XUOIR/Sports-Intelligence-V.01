"""Private operational status. Reading this module never contacts a provider."""
from datetime import timedelta
from decimal import Decimal
from sqlalchemy import select,func
from .clock import now,aware
from .config import settings
from .models import RuntimeLimit,ProviderCall,ProviderState,Fixture,Snapshot,ModelValidation,MarketOdds
from .readiness import validated_model
from .model_config import NHL_WEIGHTS

async def operational_status(session):
    at=now()
    rows=(await session.scalars(select(RuntimeLimit).where(RuntimeLimit.key.in_([
        'control:paid',*[f'circuit:{p}' for p in ('odds','openrouter','pandascore')],
        f'odds:{at.date()}',f'odds-month:{at:%Y-%m}',f'openrouter:{at.date()}',f'pandascore:{at.date()}',
        f'openrouter-usd:{at.date()}',f'openrouter-usd-month:{at:%Y-%m}'])))).all()
    limits={r.key:r for r in rows}
    def used(key):return limits[key].used if key in limits else 0
    paused=bool(used('control:paid'))
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
    fresh_quotes=(await session.scalars(select(MarketOdds).where(MarketOdds.fixture_id.in_(ids),MarketOdds.bookmaker.in_(['playnow','bclc']),
        MarketOdds.market=='h2h',MarketOdds.source_at>=at-timedelta(minutes=5),MarketOdds.source_at<=at))).all() if ids else []
    pairs={(q.fixture_id,q.bookmaker,q.selection) for q in fresh_quotes}
    prices=0
    for fixture in future:
        try:
            if (fixture.metrics.get('execution_source_present') is True
                and timedelta(0)<=at-aware(fixture.metrics['execution_verified_at'])<=timedelta(minutes=5)
                and any((fixture.id,book,fixture.home) in pairs and (fixture.id,book,fixture.away) in pairs for book in ('playnow','bclc'))):prices+=1
        except (KeyError,TypeError,ValueError):pass
    personnel=0
    for fixture in future:
        try:
            if fixture.metrics.get('personnel_confirmed') is True and timedelta(0)<=at-aware(fixture.metrics['confirmed_at'])<=timedelta(minutes=30):personnel+=1
        except (KeyError,ValueError,TypeError):pass
    factors=sum(set(f.metrics.get('factors',{}))==set(NHL_WEIGHTS) for f in future)
    usable=sum(s.baseline_home_probability is not None for s in snapshots)
    return {'active_sports':list(settings.active_sports),'paid_paused':paused,'providers':providers,
        'odds_monthly_used':used(f'odds-month:{at:%Y-%m}'),'odds_monthly_cap':settings.odds_monthly_credits,
        'ai_daily_reserved_usd':str(Decimal(used(f'openrouter-usd:{at.date()}'))/1_000_000),'ai_daily_cap_usd':str(settings.llm_daily_usd),
        'ai_monthly_reserved_usd':str(Decimal(used(f'openrouter-usd-month:{at:%Y-%m}'))/1_000_000),'ai_monthly_cap_usd':str(settings.llm_monthly_usd),
        'ai_request_reservation_usd':str(settings.llm_request_usd),
        'nhl':{'upcoming':len(future),'fresh_price_pairs':prices,'confirmed_personnel':personnel,'advanced_factors':factors,
            'frozen_inputs':len(snapshots),'usable_frozen_inputs':usable,'labeled_training_records':int(mature or 0),
            'model_approved':validated_model(model),'required_partitions':[300,100,100]},
        'server_time':at,'odds_interval_minutes':120,'cost_note':'Budgets retain failed and unconfirmed reservations. They are conservative limits, not a provider invoice.'}
