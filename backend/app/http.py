import asyncio
import json
import math
import random
from decimal import Decimal
import httpx
from .config import settings
from .limits import limits, PAID

class ProviderError(RuntimeError):
    pass

class SafeHTTP:
    def __init__(self, guard=limits, transport=None):
        self.guard,self.transport=guard,transport

    async def request(self, provider: str, method: str, url: str, *, cost=1, cycle_id=None, identity=None, usd=Decimal(0), fixture_id=None, **kwargs):
        paid=provider in PAID
        method=method.upper()
        if self.transport is None:
            target=httpx.URL(url)
            hosts={'nhl':'api-web.nhle.com','nhl_scores':'api-web.nhle.com','odds':'api.the-odds-api.com','odds_meta':'api.the-odds-api.com',
                'pandascore':'api.pandascore.co','pandascore_meta':'api.pandascore.co',
                'openrouter':'openrouter.ai','openrouter_meta':'openrouter.ai','openrouter_wallet':'openrouter.ai'}
            if provider not in hosts or target.scheme!='https' or target.host!=hosts[provider] or target.port not in (None,443) or target.userinfo:
                raise ProviderError('Provider destination rejected')
            expected_method='POST' if provider=='openrouter' else 'GET'
            if method!=expected_method:raise ProviderError('Provider method rejected')
        if await self.guard.blocked(provider):raise ProviderError(f'{provider} circuit open')
        request_id=None
        metadata={}
        try:
            async with asyncio.timeout(15 if provider.startswith('openrouter') or provider=='nhl_scores' else 45):
                async with httpx.AsyncClient(timeout=15,follow_redirects=False,transport=self.transport) as client:
                    # Paid requests get one attempt, including 429s. An uncertain
                    # response is never followed by another billable request.
                    for attempt in range(1 if paid or provider=='nhl_scores' else 3):
                        request_id=await self.guard.reserve(provider,cost,identity=identity or cycle_id,usd=usd,fixture_id=fixture_id,cycle_id=cycle_id)
                        async with client.stream(method,url,**kwargs) as response:
                            status=response.status_code
                            if status==429:
                                if provider=='nhl_scores':
                                    try:cooldown=int(response.headers.get('retry-after','900'))
                                    except ValueError:cooldown=900
                                    await self.guard.trip(provider,min(86400,max(900,cooldown)))
                                    raise ProviderError('NHL scores rate limited; cooldown active')
                                if paid:raise ProviderError('Rate limited; paid request halted without retry')
                                if attempt==2:raise ProviderError('Rate-limit retry cap reached')
                                try:
                                    delay=float(response.headers.get('retry-after',2**attempt))
                                    if not math.isfinite(delay) or delay<0:raise ValueError()
                                except ValueError:delay=2**attempt
                                if delay>4:
                                    await self.guard.trip(provider,min(86400,max(900,int(delay))))
                                    raise ProviderError('Provider requested cooldown; request halted')
                                await asyncio.sleep(delay+random.uniform(0,.25));continue
                            if status>=400:raise ProviderError(f'{provider} rejected request ({status})')
                            if 300<=status<400:
                                location=response.headers.get('location')
                                if provider=='nhl' and method=='GET' and location:
                                    destination=response.url.join(location)
                                    if destination.scheme=='https' and destination.host=='api-web.nhle.com' and destination.port in (None,443) and not destination.userinfo and destination.path.startswith('/v1/'):
                                        url=str(destination);continue
                                raise ProviderError('Upstream redirect rejected')
                            content=bytearray()
                            async for chunk in response.aiter_bytes(chunk_size=65_536):
                                if len(content)+len(chunk)>settings.max_response_bytes:raise ProviderError('Upstream payload size limit exceeded')
                                content.extend(chunk)
                            try:data=json.loads(content)
                            except (ValueError,UnicodeError):raise ProviderError('Upstream returned malformed JSON') from None
                            if provider in {'odds','odds_meta'}:
                                try:
                                    quota={name:int(response.headers[f'x-requests-{name}']) for name in ('remaining','used','last')}
                                    if any(value<0 for value in quota.values()) or quota['last']>(cost if paid else 0):raise ValueError()
                                except (KeyError,ValueError):raise ProviderError('Provider quota headers changed; paid sync halted') from None
                                metadata={'quota':quota};await self.guard.observe('odds',quota)
                                if quota['remaining']<3:await self.guard.trip('odds',reason='Insufficient remaining provider credits')
                            if provider=='openrouter':
                                usage=data.get('usage',{}) if isinstance(data,dict) else {}
                                if usage.get('cost') is not None:
                                    try:
                                        actual=Decimal(str(usage['cost']))
                                        if not actual.is_finite() or actual<0 or actual>Decimal(str(usd)):raise ValueError()
                                    except (ValueError,ArithmeticError):raise ProviderError('Reported AI cost exceeded its reservation or was invalid') from None
                                    metadata['reported_usd']=str(actual)
                                metadata['cost_reconciled']='reported_usd' in metadata
                            if provider=='pandascore_meta':
                                info={}
                                for key,names in {'hourly_limit':('x-rate-limit-limit','x-ratelimit-limit'),
                                    'hourly_remaining':('x-rate-limit-remaining','x-ratelimit-remaining'),
                                    'hourly_used':('x-rate-limit-used','x-ratelimit-used')}.items():
                                    for name in names:
                                        if name in response.headers:
                                            try:info[key]=max(0,int(response.headers[name]))
                                            except ValueError:pass
                                            break
                                if 'hourly_limit' not in info and 'hourly_remaining' in info and 'hourly_used' in info:
                                    info['hourly_limit']=info['hourly_remaining']+info['hourly_used']
                                await self.guard.observe('pandascore',info)
                            if request_id:await self.guard.finish(request_id,'SUCCEEDED',metadata=metadata)
                            return data
        except asyncio.CancelledError:
            if paid:
                try:
                    async with asyncio.timeout(3):
                        await self.guard.finish(request_id,'UNKNOWN',category='Cancelled',metadata=metadata)
                        await self.guard.trip(provider,reason='Cancelled request may already have been billed')
                except Exception:pass
            raise
        except (TimeoutError,httpx.HTTPError,ProviderError) as exc:
            category=type(exc).__name__
            if paid or not await self.guard.blocked(provider):await self.guard.trip(provider)
            if request_id:await self.guard.finish(request_id,'UNKNOWN' if isinstance(exc,(TimeoutError,httpx.HTTPError)) else 'FAILED',category=category,metadata=metadata)
            # HTTP exception strings can contain secret query parameters.
            if isinstance(exc,ProviderError):raise
            raise ProviderError(f'{provider} timeout/network failure; automatic paid retry disabled') from None
        await self.guard.trip(provider)
        raise ProviderError('Request attempts exhausted')

http=SafeHTTP()
