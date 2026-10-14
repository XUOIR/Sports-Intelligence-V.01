import hashlib
from datetime import timedelta
from decimal import Decimal
from sqlalchemy import select, update,or_,and_
from sqlalchemy.dialects.postgresql import insert
from . import db
from .clock import now, aware
from .models import RuntimeLimit, JobLease, EvaluationCycle, ProviderCall, ProviderState, AuditLog
from .config import settings
from .model_config import MAX_LLM_RETRIES

PAID = {'odds','pandascore','openrouter'}
MICRO = Decimal(1_000_000)

class BudgetExceeded(RuntimeError):
    pass

class Limits:
    async def _increment(self, session, key, amount, cap):
        await session.execute(insert(RuntimeLimit).values(key=key,used=0).on_conflict_do_nothing())
        result=await session.execute(update(RuntimeLimit).where(RuntimeLimit.key==key,
            RuntimeLimit.used+amount<=cap).values(used=RuntimeLimit.used+amount).returning(RuntimeLimit.key))
        if result.scalar_one_or_none() is None:
            raise BudgetExceeded(f'{key.split(":")[0]} budget reached')

    async def reserve(self, provider: str, cost: int = 1, *, identity=None, usd=Decimal(0), fixture_id=None, cycle_id=None):
        caps={'odds':settings.odds_daily_credits,'pandascore':settings.pandascore_daily_requests,
            'openrouter':settings.llm_daily_requests,'nhl':settings.nhl_daily_requests,'odds_meta':24,
            'openrouter_meta':max(24,settings.llm_daily_requests+6),'openrouter_wallet':4,'pandascore_meta':4}
        if provider not in caps or type(cost) is not int or not 1<=cost<=1000:
            raise BudgetExceeded('Invalid provider or request cost')
        usd=Decimal(str(usd))
        if not usd.is_finite() or usd<0 or usd!=usd.quantize(Decimal('.000001')):
            raise BudgetExceeded('Invalid spend reservation')
        if provider=='pandascore' and not set(settings.active_sports)&{'CS2','VAL','LOL'}:
            raise BudgetExceeded('Esports ingestion is disabled')
        if provider=='openrouter' and (cost!=1 or not settings.llm_enabled or not fixture_id or not cycle_id or usd!=settings.llm_request_usd):
            raise BudgetExceeded('AI reviews require configured USD budgets, a fixture, and a bounded reservation')
        if provider in PAID and (not isinstance(identity,str) or not 1<=len(identity)<=500):
            raise BudgetExceeded('Paid requests require a durable request identity')
        at=now();request_id=hashlib.sha256(f'{provider}:{identity}'.encode()).hexdigest() if provider in PAID else None
        async with db.Session.begin() as session:
            # The control row serializes admissions across providers and instances.
            await session.execute(insert(RuntimeLimit).values(key='control:paid',used=0).on_conflict_do_nothing())
            control=await session.get(RuntimeLimit,'control:paid',with_for_update=True)
            circuit=await session.get(RuntimeLimit,f'circuit:{provider}')
            if provider in PAID and control.used:
                raise BudgetExceeded('Paid requests paused by the operator')
            if circuit and (circuit.used or circuit.blocked_until and aware(circuit.blocked_until)>at):
                raise BudgetExceeded(f'{provider} circuit open')
            if request_id and await session.get(ProviderCall,request_id):
                raise BudgetExceeded('This paid request was already attempted; automatic repetition disabled')
            if provider=='odds':
                window=await self.odds_window(session)
                if window['in_progress'] or window['needs_resume']:
                    raise BudgetExceeded('A previous odds refresh is unfinished; check its status before another request')
                if not window['remaining']:
                    raise BudgetExceeded('The five-refresh limit for the rolling 24-hour window has been reached')
            if request_id:
                admitted=await session.execute(insert(ProviderCall).values(id=request_id,provider=provider,
                    fixture_id=fixture_id,units=cost,reserved_usd=usd,status='STARTED',response_metadata={},created_at=at,updated_at=at)
                    .on_conflict_do_nothing().returning(ProviderCall.id))
                if admitted.scalar_one_or_none() is None:
                    raise BudgetExceeded('This paid request was already attempted; automatic repetition disabled')
            await self._increment(session,f'{provider}:{at.date()}',cost,caps[provider])
            if provider=='odds':
                await self._increment(session,f'odds-month:{at:%Y-%m}',cost,settings.odds_monthly_credits)
            if provider=='openrouter':
                micro=int(usd*MICRO)
                await self._increment(session,f'openrouter-usd:{at.date()}',micro,int(settings.llm_daily_usd*MICRO))
                await self._increment(session,f'openrouter-usd-month:{at:%Y-%m}',micro,int(settings.llm_monthly_usd*MICRO))
                await self._increment(session,f'openrouter-fixture:{fixture_id}',1,MAX_LLM_RETRIES)
                attempted=await session.execute(update(EvaluationCycle).where(EvaluationCycle.id==cycle_id,
                    EvaluationCycle.fixture_id==fixture_id,
                    EvaluationCycle.llm_attempts<MAX_LLM_RETRIES).values(llm_attempts=EvaluationCycle.llm_attempts+1).returning(EvaluationCycle.id))
                if attempted.scalar_one_or_none() is None:
                    raise BudgetExceeded('Fixture evaluation attempt cap reached')
        # A reserved identity remains consumed even if the process crashes or a
        # response cannot be reconciled. Never refund an uncertain remote call.
        return request_id

    async def attempted(self,provider,identity):
        request_id=hashlib.sha256(f'{provider}:{identity}'.encode()).hexdigest()
        async with db.Session() as session:
            return await session.get(ProviderCall,request_id) is not None

    async def finish(self, request_id, status, *, category=None, metadata=None):
        if not request_id:return
        async with db.Session.begin() as session:
            row=await session.get(ProviderCall,request_id,with_for_update=True)
            if row:
                row.status,row.error_category,row.updated_at=status,category,now()
                row.response_metadata={**row.response_metadata,**(metadata or {})}

    async def odds_window(self,session=None):
        if session is None:
            async with db.Session() as opened:return await self.odds_window(opened)
        at=now();cutoff=at-timedelta(hours=24)
        rows=(await session.scalars(select(ProviderCall).where(ProviderCall.provider=='odds',or_(
            ProviderCall.created_at>cutoff,ProviderCall.status=='STARTED',and_(ProviderCall.status=='SUCCEEDED',
                ProviderCall.fixture_id.like('odds-refresh:%')))).order_by(ProviderCall.created_at))).all()
        recent=[r for r in rows if aware(r.created_at)>cutoff]
        pending=[r for r in rows if r.status=='STARTED' or r.status=='SUCCEEDED' and r.fixture_id and r.fixture_id.startswith('odds-refresh:') and r.response_metadata.get('odds_sync_status')!='complete']
        maximum=settings.odds_refreshes_24h
        next_at=aware(recent[len(recent)-maximum].created_at)+timedelta(hours=24) if maximum and len(recent)>=maximum else None
        return {'limit':maximum,'used':len(recent),'remaining':max(0,maximum-len(recent)),
            'next_available_at':next_at,'credit_cost':3,'mode':'manual',
            'in_progress':any(at-aware(r.created_at)<=timedelta(seconds=60) for r in pending),
            'needs_resume':any(at-aware(r.created_at)>timedelta(seconds=60) for r in pending),
            'active_request_id':next((r.fixture_id.split(':',1)[1] for r in pending if r.fixture_id and r.fixture_id.startswith('odds-refresh:')),None)}

    async def observe(self, provider, info):
        async with db.Session.begin() as session:
            stmt=insert(ProviderState).values(provider=provider,observed_at=now(),info=info)
            await session.execute(stmt.on_conflict_do_update(index_elements=[ProviderState.provider],
                set_={'observed_at':stmt.excluded.observed_at,'info':stmt.excluded.info}))

    async def observation(self, provider, max_age=600):
        async with db.Session() as session:
            row=await session.get(ProviderState,provider)
            if row and timedelta(0)<=now()-aware(row.observed_at)<=timedelta(seconds=max_age):
                return row.info
        return None

    async def blocked(self, provider: str):
        async with db.Session() as session:
            control=await session.get(RuntimeLimit,'control:paid')
            row=await session.get(RuntimeLimit,f'circuit:{provider}')
            return bool(provider in PAID and control and control.used or row and (row.used or row.blocked_until and aware(row.blocked_until)>now()))

    async def trip(self, provider: str, seconds=None, reason='Provider request failed'):
        # Paid failures latch until an explicit operator resume. Free requests
        # can recover after a bounded cooldown without consuming paid credits.
        permanent=provider in PAID
        duration=seconds if seconds is not None else 900
        async with db.Session.begin() as session:
            await session.execute(insert(RuntimeLimit).values(key='control:paid',used=0).on_conflict_do_nothing())
            await session.get(RuntimeLimit,'control:paid',with_for_update=True)
            stmt=insert(RuntimeLimit).values(key=f'circuit:{provider}',used=int(permanent),blocked_until=None if permanent else now()+timedelta(seconds=duration))
            await session.execute(stmt.on_conflict_do_update(index_elements=[RuntimeLimit.key],set_={'used':stmt.excluded.used,'blocked_until':stmt.excluded.blocked_until}))
            session.add(AuditLog(action='PROVIDER_HALTED',entity_id=provider,details={'reason':reason[:200]}))

    async def pause(self, paused: bool):
        async with db.Session.begin() as session:
            stmt=insert(RuntimeLimit).values(key='control:paid',used=int(paused))
            await session.execute(stmt.on_conflict_do_update(index_elements=[RuntimeLimit.key],set_={'used':int(paused)}))
            session.add(AuditLog(action='PAID_REQUESTS_PAUSED' if paused else 'PAID_REQUESTS_RESUMED',entity_id='providers',details={}))

    async def resume(self, provider):
        if provider not in PAID:raise ValueError('Unknown paid provider')
        async with db.Session.begin() as session:
            await session.execute(update(RuntimeLimit).where(RuntimeLimit.key==f'circuit:{provider}').values(used=0,blocked_until=None))
            if provider=='odds':
                unfinished=(await session.scalars(select(ProviderCall).where(ProviderCall.provider=='odds',
                    ProviderCall.created_at<now()-timedelta(seconds=60),or_(ProviderCall.status=='STARTED',
                        and_(ProviderCall.status=='SUCCEEDED',ProviderCall.fixture_id.like('odds-refresh:%')))))).all()
                for row in unfinished:
                    if row.status=='STARTED' or row.response_metadata.get('odds_sync_status')!='complete':
                        row.status,row.error_category,row.updated_at='UNKNOWN','InterruptedRefresh',now()
            session.add(AuditLog(action='PROVIDER_RESUMED',entity_id=provider,details={}))
        # Existing request identities and spend reservations are never reset.

    async def llm_attempt(self, cycle_id: str):
        async with db.Session.begin() as session:
            result=await session.execute(update(EvaluationCycle).where(EvaluationCycle.id==cycle_id,
                EvaluationCycle.llm_attempts<MAX_LLM_RETRIES).values(llm_attempts=EvaluationCycle.llm_attempts+1).returning(EvaluationCycle.id))
            if result.scalar_one_or_none() is None:raise BudgetExceeded('Fixture evaluation attempt cap reached')

    async def lease(self, key: str, seconds=300) -> bool:
        async with db.Session.begin() as session:
            stmt=insert(JobLease).values(key=key,expires_at=now()+timedelta(seconds=seconds))
            result=await session.execute(stmt.on_conflict_do_update(index_elements=[JobLease.key],
                set_={'expires_at':stmt.excluded.expires_at},where=JobLease.expires_at<now()).returning(JobLease.key))
            return result.scalar_one_or_none() is not None

limits = Limits()
