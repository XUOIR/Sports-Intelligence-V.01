import httpx
import asyncio
import time
import pytest
from decimal import Decimal
from app.http import SafeHTTP,ProviderError
from app.models import State
from app.engine import recommendation_state
from app.model_config import GATE_NAMES
from app.providers import complete_roster,BOOKMAKER_ALIASES

class Guard:
    def __init__(self):self.calls=0;self.tripped=False;self.attempts=0
    async def reserve(self,*args,**kwargs):
        self.calls+=1
        if kwargs.get('cycle_id'):self.attempts+=1
    async def blocked(self,*args):return self.tripped
    async def trip(self,*args,**kwargs):self.tripped=True
    async def llm_attempt(self,*args):self.attempts+=1

@pytest.mark.parametrize('location', [
    'https://api-web.nhle.com/v1/standings/2026-10-13',
    '/v1/standings/2026-10-13',
])
async def test_nhl_public_redirect_is_followed_and_both_requests_are_budgeted(location):
    seen = []
    def respond(request):
        seen.append(str(request.url))
        if request.url.path.endswith('/now'):
            return httpx.Response(307, headers={'Location': location})
        return httpx.Response(200, json={'standings': []})
    guard = Guard()
    client = SafeHTTP(guard, httpx.MockTransport(respond))
    assert await client.request('nhl', 'GET', 'https://api-web.nhle.com/v1/standings/now') == {'standings': []}
    assert seen == ['https://api-web.nhle.com/v1/standings/now', 'https://api-web.nhle.com/v1/standings/2026-10-13']
    assert guard.calls == 2

@pytest.mark.parametrize('location', [
    'https://example.test/v1/standings/2026-10-13',
    'https://api-web.nhle.com.attacker.example/v1/standings/2026-10-13',
    'http://api-web.nhle.com/v1/standings/2026-10-13',
    'https://api-web.nhle.com:444/v1/standings/2026-10-13',
    'https://user@api-web.nhle.com/v1/standings/2026-10-13',
    'https://api-web.nhle.com/private',
    '',
])
async def test_nhl_redirect_cannot_leave_the_public_official_api(location):
    guard = Guard()
    client = SafeHTTP(guard, httpx.MockTransport(lambda request: httpx.Response(307, headers={'Location': location})))
    with pytest.raises(ProviderError):
        await client.request('nhl', 'GET', 'https://api-web.nhle.com/v1/standings/now')
    assert guard.calls == 1

async def test_nhl_redirect_loop_is_bounded_by_existing_request_cap():
    guard = Guard()
    client = SafeHTTP(guard, httpx.MockTransport(lambda request: httpx.Response(307, headers={'Location': '/v1/standings/now'})))
    with pytest.raises(ProviderError):
        await client.request('nhl', 'GET', 'https://api-web.nhle.com/v1/standings/now')
    assert guard.calls == 3

@pytest.mark.parametrize('provider,method', [('odds','GET'), ('pandascore','GET'), ('openrouter','POST'), ('nhl','POST')])
async def test_paid_api_and_non_get_redirects_remain_rejected(provider, method):
    guard = Guard()
    client = SafeHTTP(guard, httpx.MockTransport(lambda request: httpx.Response(307, headers={'Location': 'https://api-web.nhle.com/v1/standings/2026-10-13'})))
    with pytest.raises(ProviderError):
        await client.request(provider, method, 'https://example.test')
    assert guard.calls == 1

async def test_openrouter_503_never_retries_and_circuit_opens():
    guard=Guard();client=SafeHTTP(guard,httpx.MockTransport(lambda r:httpx.Response(503)))
    with pytest.raises(ProviderError):await client.request('openrouter','POST','https://example.test',cycle_id='x')
    assert guard.calls==guard.attempts==1
    with pytest.raises(ProviderError):await client.request('openrouter','POST','https://example.test',cycle_id='x')
    assert guard.calls==1

async def test_429_retries_are_bounded(monkeypatch):
    async def no_sleep(*args):pass
    monkeypatch.setattr('app.http.asyncio.sleep',no_sleep)
    guard=Guard();client=SafeHTTP(guard,httpx.MockTransport(lambda r:httpx.Response(429,headers={'Retry-After':'0'})))
    with pytest.raises(ProviderError):await client.request('nhl','GET','https://example.test')
    assert guard.calls==3 and guard.tripped

async def test_payload_cap_and_bad_json():
    for body in (b'x'*1_000_001,b'not json'):
        guard=Guard();client=SafeHTTP(guard,httpx.MockTransport(lambda r:httpx.Response(200,content=body)))
        with pytest.raises(ProviderError):await client.request('nhl','GET','https://example.test')
        assert guard.calls==1

async def test_network_timeout_cannot_repeat_paid_post():
    def fail(request):raise httpx.ReadTimeout('timeout')
    guard=Guard();client=SafeHTTP(guard,httpx.MockTransport(fail))
    with pytest.raises(ProviderError):await client.request('openrouter','POST','https://example.test')
    assert guard.calls==1 and guard.tripped

async def test_openrouter_total_wall_clock_deadline():
    async def slow(request):
        await asyncio.sleep(20)
        return httpx.Response(200,json={})
    guard=Guard();client=SafeHTTP(guard,httpx.MockTransport(slow));started=time.monotonic()
    with pytest.raises(ProviderError):await client.request('openrouter','POST','https://example.test')
    assert time.monotonic()-started<17 and guard.calls==1 and guard.tripped

@pytest.mark.parametrize('missing',GATE_NAMES)
def test_every_gate_required(missing):
    gates={g:True for g in GATE_NAMES};gates[missing]=False
    assert recommendation_state(gates,has_execution=True,personnel=True,edge=Decimal('.05'),frozen=True)!=State.RECOMMEND

def test_execution_source_and_personnel_hard_locks():
    gates={g:True for g in GATE_NAMES}
    assert recommendation_state(gates,has_execution=False,personnel=True,edge=Decimal('.05'),frozen=True)==State.WATCH
    assert recommendation_state(gates,has_execution=True,personnel=False,edge=Decimal('.05'),frozen=True)==State.HOLD
    assert recommendation_state(gates,has_execution=True,personnel=True,edge=Decimal('.05'),frozen=True)==State.RECOMMEND
    assert BOOKMAKER_ALIASES['playnow_ca']=='playnow'
    assert not complete_roster(None)
    assert not complete_roster([{'id':1}]*5)
    assert complete_roster([{'id':i+1} for i in range(5)])
