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
    async def reserve(self,*args):self.calls+=1
    async def blocked(self,*args):return self.tripped
    async def trip(self,*args):self.tripped=True
    async def llm_attempt(self,*args):self.attempts+=1

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
    with pytest.raises(ProviderError):await client.request('odds','GET','https://example.test',cost=3)
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
