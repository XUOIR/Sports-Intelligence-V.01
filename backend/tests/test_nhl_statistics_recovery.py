from dataclasses import replace
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from app import nhl_advanced as advanced, nhl_statistics_recovery as recovery
from app.clock import now
from app.config import settings
from app.models import ProviderState, RuntimeLimit, ProviderCall
from test_nhl_advanced import source_files, transport_for


async def failed_hosting_import(database):
    await advanced.reserve_batch()
    async with database.begin() as session:
        session.add(ProviderState(provider=advanced.STATUS_KEY,
            info={'status':'failed','date':str(now().date())}))
        session.add(ProviderState(provider=advanced.PROBE_KEY,
            info={'status':'failed','date':str(now().date()),
                  'sources':[{'source':'team','http_status':302},{'source':'goalie','http_status':403}]}))


async def test_recovery_requires_failed_import_and_recent_transport_diagnostic(database):
    with pytest.raises(advanced.BudgetExceeded): await advanced.reserve_manual_recovery()
    await failed_hosting_import(database)
    async with database.begin() as session:
        row=await session.get(ProviderState,advanced.PROBE_KEY)
        row.observed_at=now()-timedelta(hours=2)
    with pytest.raises(advanced.BudgetExceeded): await advanced.reserve_manual_recovery()
    async with database() as session:
        assert await session.get(RuntimeLimit,f'moneypuck-manual-recovery:{now().date()}') is None


async def test_recovery_is_once_per_day_without_resetting_original_attempt(database):
    await failed_hosting_import(database)
    await advanced.reserve_manual_recovery()
    with pytest.raises(advanced.BudgetExceeded): await advanced.reserve_manual_recovery()
    with pytest.raises(advanced.BudgetExceeded): await advanced.reserve_batch()
    async with database() as session:
        assert (await session.get(RuntimeLimit,f'moneypuck-batch:{now().date()}')).used==1
        assert (await session.get(RuntimeLimit,f'moneypuck-manual-recovery:{now().date()}')).used==1
        assert (await session.get(RuntimeLimit,f'moneypuck-wire:{now():%Y-%m}')).used==2*advanced.RESERVATION


async def test_recovery_cannot_exceed_shared_monthly_cap(database,monkeypatch):
    await failed_hosting_import(database)
    monkeypatch.setattr(advanced,'settings',replace(settings,nhl_advanced_monthly_bytes=advanced.RESERVATION))
    with pytest.raises(advanced.BudgetExceeded): await advanced.reserve_manual_recovery()
    async with database() as session:
        assert await session.get(RuntimeLimit,f'moneypuck-manual-recovery:{now().date()}') is None


async def test_recovery_uses_existing_full_validation_and_records_provenance(database,monkeypatch):
    enabled=replace(settings,nhl_advanced_enabled=True)
    monkeypatch.setattr(advanced,'settings',enabled)
    monkeypatch.setattr(recovery,'settings',enabled)
    await failed_hosting_import(database)
    team,goalies,reference=source_files();calls=[]
    result=await recovery.recover(transport=transport_for(team,goalies,reference,calls))
    assert result['status']=='succeeded' and len(calls)==3
    assert result['acquisition']=='operator_public_download'
    async with database() as session:
        batch=(await session.get(ProviderState,advanced.CACHE_KEY)).info
        assert batch['acquisition']=='operator_public_download'
        assert batch['model_approved_by_import'] is False and batch['starters_confirmed_by_import'] is False
        assert (await session.get(RuntimeLimit,f'moneypuck-wire:{now():%Y-%m}')).used==advanced.RESERVATION+result['wire_accounted']
        assert (await session.scalars(select(ProviderCall))).all()==[]
    with pytest.raises(advanced.BudgetExceeded): await recovery.recover(transport=transport_for(team,goalies,reference,calls))
    assert len(calls)==3


async def test_failed_recovery_retains_cache_and_consumed_admission(database,monkeypatch):
    enabled=replace(settings,nhl_advanced_enabled=True)
    monkeypatch.setattr(advanced,'settings',enabled)
    monkeypatch.setattr(recovery,'settings',enabled)
    await failed_hosting_import(database)
    previous={'as_of_date':str(now().date()-timedelta(days=1)),'unchanged':True}
    async with database.begin() as session:
        session.add(ProviderState(provider=advanced.CACHE_KEY,info=previous))
    calls=[]
    def denied(request):calls.append(request);return httpx.Response(403)
    assert (await recovery.recover(transport=httpx.MockTransport(denied)))['status']=='failed'
    with pytest.raises(advanced.BudgetExceeded):await recovery.recover(transport=httpx.MockTransport(denied))
    assert len(calls)==1
    async with database() as session:
        assert (await session.get(ProviderState,advanced.CACHE_KEY)).info==previous


async def test_disabled_recovery_uses_no_network_or_budget(database):
    with pytest.raises(advanced.BudgetExceeded):
        await recovery.recover(transport=httpx.MockTransport(lambda r:pytest.fail('Unexpected network')))
    async with database() as session:
        assert await session.get(RuntimeLimit,f'moneypuck-manual-recovery:{now().date()}') is None
