"""Manual NHL odds refreshes with durable identities and no automatic resend."""
import asyncio
import hashlib
from datetime import timedelta
from sqlalchemy import select
from . import db
from .clock import now,aware
from .config import settings
from .http import ProviderError
from .ingestion import ingest_odds
from .limits import limits,BudgetExceeded
from .models import ProviderCall,Fixture

def call_id(request_id):
    return hashlib.sha256(f'odds:manual:NHL:{request_id}'.encode()).hexdigest()

async def lookup(request_id):
    async with db.Session() as session:
        row=await session.get(ProviderCall,call_id(request_id))
        if row is None:return None
        completed=row.status=='SUCCEEDED' and row.response_metadata.get('odds_sync_status')=='complete'
        state='succeeded' if completed else row.status.lower() if row.status in {'FAILED','UNKNOWN'} else 'in_progress' if now()-aware(row.created_at)<=timedelta(seconds=60) else 'unknown'
        return {'request_id':str(request_id),'status':state,'attempted_at':aware(row.created_at),
            'credits_reserved':row.units,'synced_at':row.response_metadata.get('synced_at'),
            'ingestion':row.response_metadata.get('ingestion'),'message':row.response_metadata.get('message')}

async def refresh(request_id):
    request_id=str(request_id)
    # The deadline covers preflight, provider I/O, and database ingestion.
    # It intentionally does not await AI: the existing gate scheduler does that.
    try:
        async with asyncio.timeout(45):
            prior=await lookup(request_id)
            if prior:return prior
            if settings.active_sports!=('NHL',):raise BudgetExceeded('Manual odds refresh is restricted to the NHL phase')
            if not settings.odds_key:raise ProviderError('Odds API credential is not configured')
            window=await limits.odds_window()
            if not window['remaining']:raise BudgetExceeded('Five odds refresh attempts already used in the last 24 hours')
            if window['in_progress'] or window['needs_resume']:raise BudgetExceeded('A previous refresh is unfinished; check its status or resume the provider')
            async with db.Session() as session:
                scheduled=await session.scalar(select(Fixture.id).where(Fixture.sport=='NHL',Fixture.commence_time>now(),
                    Fixture.commence_time<=now()+timedelta(hours=48)).limit(1))
            if not scheduled:return {'request_id':request_id,'status':'skipped','message':'No upcoming NHL games within 48 hours; no credits used'}
            report={}
            await ingest_odds(refresh_id=request_id,report=report)
            message=f"Saved {report['quotes_saved']} quotes ({report['playnow_quotes_saved']} PlayNow) from {report['events_matched']} matched games."
            if not report['events_matched']:
                message='The provider responded, but no events matched official fixtures. Odds refresh is paused to protect credits.'
                await limits.trip('odds',reason=message)
            elif not report['quotes_saved']:
                message='No new valid prices were saved. Existing prices are retained; refresh is paused to avoid repeated empty requests.'
                await limits.trip('odds',reason=message)
            elif not report['playnow_quotes_saved']:
                message+=' No new PlayNow quotes were supplied; other books are comparison prices only.'
            await limits.finish(call_id(request_id),'SUCCEEDED',metadata={'odds_sync_status':'complete','synced_at':now().isoformat(),'ingestion':report,'message':message})
            result=await lookup(request_id)
            if result is None:raise ProviderError('Refresh was not admitted; no automatic resend')
            return result
    except BudgetExceeded:
        # Another tab may have admitted the same identity concurrently.
        prior=await lookup(request_id)
        if prior:return prior
        raise
    except (Exception,asyncio.CancelledError) as exc:
        try:
            async with asyncio.timeout(3):
                prior=await lookup(request_id)
                if prior and prior['status']!='succeeded':
                    await limits.finish(call_id(request_id),'UNKNOWN' if prior['status']=='unknown' or isinstance(exc,(TimeoutError,asyncio.CancelledError)) else 'FAILED',
                        category=type(exc).__name__,metadata={'odds_sync_status':'failed'})
                    await limits.trip('odds',reason='Manual refresh failed or was interrupted; no automatic resend')
        except Exception:pass
        if isinstance(exc,asyncio.CancelledError):raise
        if isinstance(exc,ProviderError):raise
        raise ProviderError('Odds refresh could not finish safely; check the saved request status') from None
