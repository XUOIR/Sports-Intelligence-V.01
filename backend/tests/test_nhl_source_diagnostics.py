import json
from datetime import timedelta

import httpx
import pytest

from app import nhl_advanced as advanced
from app.clock import now
from app.models import ProviderState
from app.nhl_source_diagnostics import response_metadata, SourceResponseError


def test_redirect_preserves_only_known_public_destination_without_secrets():
    response=httpx.Response(302,headers={
        'Location':'https://user:secret-password@www.moneypuck.com/data.htm?token=secret-query#secret-fragment',
        'Server':'cloudflare','CF-Mitigated':'challenge','CF-Ray':'1234567890abcdef-PDX',
        'Content-Type':'text/html; charset=UTF-8','Set-Cookie':'secret-cookie'})
    details=response_metadata(response,source_url=advanced.TEAM_URL)
    assert details['response_kind']=='redirect' and details['challenge_reported']
    assert details['redirect']=={'classification':'public_source_redirect','origin':'https://www.moneypuck.com',
                                'path':'/data.htm','details_withheld':True}
    assert details['edge_reference']=='1234567890abcdef-PDX'
    assert 'secret-' not in json.dumps(details)


@pytest.mark.parametrize('destination',[
    'https://secret-subdomain.attacker.test/secret-path?token=secret-query',
    'file:///secret-path','https://moneypuck.com:9999/secret-path',
    'https://moneypuck.com/\nsecret-path','https://[malformed/secret-path'])
def test_unknown_or_unsafe_redirect_destinations_are_withheld(destination):
    details=response_metadata(httpx.Response(302,headers={'Location':destination}),source_url=advanced.TEAM_URL)
    assert details['redirect']['classification']=='unrecognized_destination'
    assert details['redirect']['origin'] is None
    assert 'secret-' not in json.dumps(details)


def test_relative_redirect_unknown_path_and_bad_headers_are_redacted():
    details=response_metadata(httpx.Response(302,headers={'Location':'/challenge/secret-path?token=secret-query',
        'Server':'secret-server','CF-Ray':'secret-ray','Content-Length':'secret-length',
        'Last-Modified':'secret-date','Content-Encoding':'secret-encoding','Content-Type':'secret-type',
        'Retry-After':'secret-retry'}),source_url=advanced.TEAM_URL)
    assert details['redirect']['origin']=='https://moneypuck.com'
    assert details['redirect']['path'] is None and details['redirect']['details_withheld']
    assert details['last_modified'] is None and details['content_length'] is None
    assert details['server_family']=='other' and details['encoding']=='unrecognized'
    assert 'secret-' not in json.dumps(details)


async def test_normal_import_failure_keeps_transport_evidence_without_reading_body(database,monkeypatch):
    from dataclasses import replace
    monkeypatch.setattr(advanced,'settings',replace(advanced.settings,nhl_advanced_enabled=True))
    calls=[]
    class NoBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            pytest.fail('Denied response body was read')
            yield b''
    def denied(request):
        calls.append(str(request.url))
        return httpx.Response(302,headers={'Location':'https://www.moneypuck.com/data.htm?token=secret-token',
                                          'Server':'cloudflare'},stream=NoBody())
    assert (await advanced.sync(transport=httpx.MockTransport(denied)))['status']=='failed'
    assert calls==[advanced.TEAM_URL]
    async with database() as session:
        failure=(await session.get(ProviderState,advanced.STATUS_KEY)).info
        assert failure['transport']['http_status']==302
        assert failure['transport']['redirect']['origin']=='https://www.moneypuck.com'
        assert 'secret-token' not in json.dumps(failure)
        automation=(await session.get(ProviderState,advanced.AUTOMATION_KEY)).info
        assert automation['last_status']=='failed' and automation['consecutive_success_days']==0


def test_transport_contract_failures_also_record_fixed_diagnostics():
    with pytest.raises(SourceResponseError) as caught:
        advanced.source_headers(httpx.Response(200,headers={'Content-Encoding':'gzip','Last-Modified':'bad date'}),
                                compressed=True,observed=now(),source_url=advanced.TEAM_URL)
    failure=advanced.import_failure(caught.value,'team_download')
    assert failure['reason']=='NHL file publication time is missing, future or too old'
    assert failure['transport']['http_status']==200


async def test_only_adjacent_scheduled_days_count_and_duplicate_results_are_idempotent(database):
    today=now().date()
    for offset in (-2,-1,0):
        result={'status':'succeeded','date':str(today+timedelta(days=offset)),'completed_at':now().isoformat()}
        await advanced.record_import_state({'status':'running','date':result['date']},'scheduled_public_download')
        await advanced.record_import_state(result,'scheduled_public_download')
        await advanced.record_import_state(result,'scheduled_public_download')
    async with database() as session:
        state=(await session.get(ProviderState,advanced.AUTOMATION_KEY)).info
        assert state['consecutive_success_days']==3 and state['verification_target_days']==3
    await advanced.record_import_state({'status':'succeeded','date':str(today+timedelta(days=2)),
                                       'completed_at':now().isoformat()},'scheduled_public_download')
    async with database() as session:
        assert (await session.get(ProviderState,advanced.AUTOMATION_KEY)).info['consecutive_success_days']==1


async def test_manual_recovery_never_clears_scheduled_failure_or_counts_as_automatic_success(database):
    failed={**advanced.import_failure(ValueError('NHL file request failed; no retry'),'team_download'),
            'date':str(now().date())}
    await advanced.record_import_state(failed,'scheduled_public_download')
    async with database() as session:
        before=(await session.get(ProviderState,advanced.AUTOMATION_KEY)).info
    for mode in ('operator_public_download','manual_render_download'):
        await advanced.record_import_state({'status':'succeeded','date':str(now().date()),
                                           'completed_at':now().isoformat()},mode)
    async with database() as session:
        assert (await session.get(ProviderState,advanced.AUTOMATION_KEY)).info==before
        assert (await session.get(ProviderState,advanced.STATUS_KEY)).info['status']=='succeeded'
