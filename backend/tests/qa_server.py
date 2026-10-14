"""Disposable local browser QA. No live databases, providers, or scheduler."""
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
for key in ("SUPABASE_DB_URL","THE_ODDS_API_KEY","ESPORTS_API_KEY","OPENROUTER_API_KEY"):
    os.environ[key] = ""
os.environ["ENABLE_SCHEDULER"] = "false"
if os.getenv('QA_NHL_STATISTICS')=='true':
    os.environ['ENABLE_NHL_ADVANCED_STATS']='true'

from contextlib import asynccontextmanager
from datetime import timedelta
from uuid import uuid4
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from app.api import app
from app import db
from app.models import Base,Account,Fixture,State,PersonalBet,Outcome,ProviderState
from app.model_config import GATE_NAMES
from app.clock import now

if os.getenv('QA_MANUAL_ODDS')=='true':
    # This test harness always clears real provider credentials above. The
    # transport below never reaches a network, including quota preflights.
    from dataclasses import replace
    import httpx
    from app import providers,manual_odds,operations
    import app.limits as limit_module
    from app.config import settings
    from app.http import SafeHTTP
    config=replace(settings,odds_key='disposable-qa-key',odds_daily_credits=15)
    providers.settings=manual_odds.settings=operations.settings=limit_module.settings=config
    calls=[]
    def mock(request):
        headers={'x-requests-remaining':str(500-len(calls)*3),'x-requests-used':str(len(calls)*3),'x-requests-last':'0'}
        if request.url.path=='/v4/sports/':return httpx.Response(200,json=[{'key':'icehockey_nhl'}],headers=headers)
        if '/icehockey_nhl/odds/' not in request.url.path:raise AssertionError('Unexpected QA provider request')
        calls.append(request);headers.update({'x-requests-last':'3','x-requests-used':str(len(calls)*3),'x-requests-remaining':str(500-len(calls)*3)})
        return httpx.Response(200,json=[{'id':'qa','home_team':'QA Home','away_team':'QA Away','commence_time':qa_start.isoformat(),
            'bookmakers':[{'key':'playnow_ca','last_update':now().isoformat(),'markets':[{'key':'h2h',
                'outcomes':[{'name':'QA Home','price':2},{'name':'QA Away','price':1.9}]}]}]}],headers=headers)
    providers.http=SafeHTTP(limit_module.Limits(),httpx.MockTransport(mock))
    qa_start=now()+timedelta(hours=3)

@asynccontextmanager
async def lifespan(application):
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    db.Session=async_sessionmaker(engine,expire_on_commit=False)
    async with db.Session.begin() as session:
        session.add(Account(id=1,initial_bankroll=1100))
        if os.getenv('QA_NHL_STATISTICS')=='true':
            # Actual tested data, an explicitly illustrative matchup and a local
            # disposable database. No real fixture or live source is fabricated.
            from pathlib import Path
            import json
            from app.nhl_advanced import build_batch,CACHE_KEY
            from app import nhl_advanced
            folder=Path(__file__).resolve().parents[2]/'artifacts/nhl-low-cost-provider-research/moneypuck-offline-test/compressed-2026-10-14'
            reference=json.loads((folder/'nhl/nhl-score-2026-10-13.json').read_text(encoding='utf-8'))
            sources={'team':json.loads((folder/'download.json').read_text(encoding='utf-8')),'goalie':json.loads((folder/'goalies/download.json').read_text(encoding='utf-8'))}
            batch=build_batch(folder/'all_teams.csv',folder/'goalies/goalies.zip',now().date(),reference,sources)
            session.add(ProviderState(provider=CACHE_KEY,info=batch))
            session.add(Fixture(id='qa:nhl-stats',sport='NHL',home='Edmonton Oilers',away='Toronto Maple Leafs',
                commence_time=now()+timedelta(hours=3),state=State.HOLD,
                reason='Local statistics test: illustrative matchup, not an official scheduled game.',
                metrics={'home_abbrev':'EDM','away_abbrev':'TOR'},gates={}))
            async def no_network_sync(**kwargs):
                return {'status':'disabled_in_offline_qa'}
            nhl_advanced.sync=no_network_sync
        if os.getenv('QA_MATCH_FEED')=='true':
            games=[]
            for index,(state,decision,hours) in enumerate([('FUT',State.HOLD,2),('LIVE',State.PASS,-1),('OFF',State.WATCH,-4)]):
                fid=f'nhl:{index+1}';start=now()+timedelta(hours=hours)
                session.add(Fixture(id=fid,sport='NHL',home=f'QA Home {index+1}',away=f'QA Away {index+1}',commence_time=start,
                    state=decision,reason='Disposable local QA match. No real betting evidence.',metrics={},gates={}))
                games.append({'id':fid,'sport':'NHL','home':f'QA Home {index+1}','away':f'QA Away {index+1}',
                    'home_abbrev':'QAH','away_abbrev':'QAA','commence_time':start.isoformat(),'game_state':state,'schedule_state':'OK',
                    'home_score':None if state=='FUT' else 3,'away_score':None if state=='FUT' else 1,
                    'period':2,'period_type':'REG','clock':'14:21','intermission':False})
            for days in [-1,0,1]:
                day=now().date()+timedelta(days=days)
                session.add(ProviderState(provider=f'nhl-score:{day}',observed_at=now(),info={
                    'games':games if days==0 else [],'next_at':(now()+timedelta(minutes=30)).isoformat(),'interval_seconds':30}))
        if os.getenv("QA_FIXTURE") == "true":
            session.add(Fixture(id="qa:fixture",sport="NHL",home="QA Home",away="QA Away",commence_time=qa_start if os.getenv('QA_MANUAL_ODDS')=='true' else now()+timedelta(hours=3),
                state=State.HOLD,reason="Disposable browser test. No real match or price.",metrics={},
                probability='.72',edge='.06',gates={gate:True for gate in GATE_NAMES[:4]}))
            await session.flush()
            if os.getenv("QA_PERFORMANCE") == "true":
                for outcome,stake,profit,days in [(Outcome.WIN,25,25,2),(Outcome.LOSS,10,-10,1),(Outcome.PUSH,10,0,0)]:
                    session.add(PersonalBet(request_id=str(uuid4()),fixture_id="qa:fixture",selection="QA Home",
                        odds_taken=2,stake_cad=stake,unit_size_at_execution=100,outcome=outcome,profit_cad=profit,
                        updated_at=now()-timedelta(days=days)))
    yield
    await engine.dispose()

app.router.lifespan_context=lifespan
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8001)
