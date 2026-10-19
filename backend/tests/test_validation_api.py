import httpx
import pytest
from sqlalchemy import select,func
from app.api import app
from app.http import http
from app.models import ProviderCall,PaperForecast


@pytest.mark.asyncio
async def test_private_performance_reads_saved_cohorts_without_refreshes(database,monkeypatch):
    async def forbidden(*args,**kwargs):raise AssertionError('Performance reads cannot call an upstream provider')
    monkeypatch.setattr(http,'request',forbidden)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        assert (await client.get('/performance')).status_code==401
        response=await client.get('/performance',headers={'Authorization':'Bearer test-session-token-32-characters-long'})
        assert response.status_code==200
        body=response.json()['forward_validation']
        assert body['baseline']['scores']['brier'] is None
        assert body['candidate']['forecasts']==0 and body['candidate']['approved_for_wagers'] is False
        assert body['starters']['completed_games_checked']==0
    async with database() as session:
        assert await session.scalar(select(func.count()).select_from(ProviderCall))==0
        assert await session.scalar(select(func.count()).select_from(PaperForecast))==0
