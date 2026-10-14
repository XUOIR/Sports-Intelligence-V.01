from dataclasses import replace
from datetime import timedelta
import httpx
import pytest
from app.clock import aware,now
from app.config import settings
from app.models import ProviderState,RuntimeLimit
from app import allowances,operations


async def test_actual_usage_is_separate_from_reservations_and_caps(database,monkeypatch):
    at=now()
    monkeypatch.setattr(operations,'settings',replace(settings,llm_daily_usd='.30',llm_monthly_usd='3'))
    async with database.begin() as session:
        session.add(RuntimeLimit(key=f'openrouter-usd:{at.date()}',used=10000))
        session.add(ProviderState(provider='allowance:openrouter',observed_at=at,info={
            'status':'verified','key_daily_used_usd':'0.00042','key_monthly_used_usd':'0.001'}))
    async with database() as session:
        status=await operations.operational_status(session)
        assert status['ai_daily_reserved_usd']=='0.01'
        assert status['ai_daily_cap_usd']=='.30'
        assert status['ai_actual_usage']['daily_usd']=='0.00042'
        assert status['ai_actual_usage']['monthly_usd']=='0.001'
        assert status['ai_actual_usage']['period_timezone']=='UTC'


async def test_old_missing_invalid_and_previous_utc_day_usage_never_become_zero(database):
    at=aware('2026-10-14T17:05:00-07:00')
    async with database() as session:
        assert (await operations.reported_ai_usage(session,at))['status']=='not_checked'
    async with database.begin() as session:
        session.add(ProviderState(provider='allowance:openrouter',observed_at=at-timedelta(minutes=10),info={
            'status':'verified','key_daily_used_usd':'.1','key_monthly_used_usd':'.2'}))
    async with database() as session:
        usage=await operations.reported_ai_usage(session,at)
        assert usage['status']=='partial' and usage['daily_usd'] is None and usage['monthly_usd']=='0.2'
    async with database.begin() as session:
        row=await session.get(ProviderState,'allowance:openrouter');row.observed_at=at-timedelta(hours=2)
    async with database() as session:
        usage=await operations.reported_ai_usage(session,at)
        assert usage['status']=='stale' and usage['daily_usd'] is None
    async with database.begin() as session:
        row=await session.get(ProviderState,'allowance:openrouter');row.observed_at=at
        row.info={'status':'verified','key_daily_used_usd':'NaN'}
    async with database() as session:
        usage=await operations.reported_ai_usage(session,at)
        assert usage['daily_usd'] is None and usage['monthly_usd'] is None


async def test_nhl_phase_does_not_probe_esports_and_missing_usage_is_unknown(database,monkeypatch):
    monkeypatch.setattr(allowances,'settings',replace(settings,odds_key='',router_key='test',esports_key='test',active_sports=('NHL',)))
    calls=[]
    async def request(provider,*args,**kwargs):
        calls.append(provider)
        if provider=='openrouter_meta':return {'data':{'limit':3,'limit_remaining':3,'limit_reset':'monthly'}}
        if provider=='openrouter_wallet':return {'data':{'total_credits':10,'total_usage':0}}
        pytest.fail('Unexpected provider call')
    monkeypatch.setattr(allowances.http,'request',request)
    result=await allowances.provider_allowances()
    assert calls==['openrouter_meta','openrouter_wallet']
    assert result[2]['status']=='disabled'
    assert 'key_daily_used_usd' not in result[1] and 'key_monthly_used_usd' not in result[1]
