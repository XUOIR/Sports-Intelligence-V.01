"""Explicit, bounded account checks. No generations or paid odds are requested."""
import asyncio
from .clock import now
from .config import settings
from .limits import limits
from .http import http
from .maths import decimal

async def provider_allowances():
    async def check(provider):
        cached=await limits.observation(f'allowance:{provider}',max_age=3600)
        if cached:return cached
        result={'provider':provider,'checked_at':now().isoformat(),'status':'unavailable'}
        try:
            if provider=='odds':
                if not settings.odds_key:return {**result,'reason':'Credential not configured'}
                await http.request('odds_meta','GET','https://api.the-odds-api.com/v4/sports/',params={'apiKey':settings.odds_key})
                quota=await limits.observation('odds')
                result.update(status='verified',unit='credits per billing period',remaining=quota['remaining'],used=quota['used'],
                    period_allowance=quota['remaining']+quota['used'])
            elif provider=='openrouter':
                if not settings.router_key:return {**result,'reason':'Credential not configured'}
                key=(await http.request('openrouter_meta','GET','https://openrouter.ai/api/v1/key',headers={'Authorization':f'Bearer {settings.router_key}'}))['data']
                result.update(status='verified',unit='USD pay as you go',key_limit_usd=None if key.get('limit') is None else str(decimal(key['limit'])),
                    key_remaining_usd=None if key.get('limit_remaining') is None else str(decimal(key['limit_remaining'])),
                    key_reset=key.get('limit_reset'),key_used_usd=str(decimal(key.get('usage',0))),
                    key_monthly_used_usd=str(decimal(key.get('usage_monthly',0))))
                try:
                    wallet=(await http.request('openrouter_wallet','GET','https://openrouter.ai/api/v1/credits',headers={'Authorization':f'Bearer {settings.router_key}'}))['data']
                    result['wallet_remaining_usd']=str(decimal(wallet['total_credits'])-decimal(wallet['total_usage']))
                except Exception as exc:
                    result['wallet_status']=f'Unavailable through this key ({type(exc).__name__})'
            elif provider=='pandascore':
                if not settings.esports_key:return {**result,'reason':'Credential not configured'}
                await http.request('pandascore_meta','GET','https://api.pandascore.co/videogames',
                    headers={'Authorization':f'Bearer {settings.esports_key}'},params={'page[size]':50})
                quota=await limits.observation('pandascore') or {}
                result.update(status='verified' if quota.get('hourly_limit') is not None else 'partial',unit='requests per hour',**quota,
                    note='PandaScore uses plan-based hourly limits, not a monthly credit wallet. Exact plan pricing requires the account plan.')
        except Exception as exc:
            result['reason']=f'Account check could not be completed ({type(exc).__name__})'
        await limits.observe(f'allowance:{provider}',result)
        return result
    async def bounded_check(provider):
        try:
            async with asyncio.timeout(20):return await check(provider)
        except TimeoutError:
            result={'provider':provider,'checked_at':now().isoformat(),'status':'unavailable','reason':'Account check timed out; no paid request sent'}
            await limits.observe(f'allowance:{provider}',result)
            return result
    return list(await asyncio.gather(*(bounded_check(provider) for provider in ('odds','openrouter','pandascore'))))
