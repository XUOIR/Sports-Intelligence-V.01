"""Sports Intelligence V0.1: FastAPI API and scheduler entry point.

Implemented app/ modules provide ingestion, durable request budgets, the
15-feature frozen vector, calibration, eight verification gates, Decimal
accounting, quarter-Kelly staking, and bounded adversarial LLM review.
Run from backend: uvicorn main:app --host 0.0.0.0 --port 10000 --workers 1.
"""

import secrets
import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID
from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import select, func, text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from app import db
from app.config import settings
from app.clock import now, aware
from app.models import Fixture, MarketOdds, PersonalBet, Account, AuditLog, Outcome, State, Snapshot, Evidence
from app.maths import parse_odds, money, profit, roi, decimal
from app.model_config import UNIT_VALUE_CAD, GATE_NAMES, INITIAL_BANKROLL_CAD
from app.ingestion import dirty
from app.providers import complete_roster
from app.performance import performance

@asynccontextmanager
async def lifespan(application):
    running_scheduler = None
    try:
        if settings.db_url:
            db.configure_database()
        if settings.scheduler:
            required = (settings.db_url, settings.odds_key, settings.esports_key, settings.router_key)
            if not all(required) or len(settings.admin_token) < 32:
                raise RuntimeError('Scheduler requires all integration credentials and a valid ADMIN_API_TOKEN')
            from app.scheduler import start, scheduler
            start()
            running_scheduler = scheduler
        yield
    finally:
        if running_scheduler is not None and running_scheduler.running:
            running_scheduler.shutdown(wait=False)
        if db.engine is not None:
            await db.engine.dispose()

app = FastAPI(title="Sports Intelligence", version="0.1.0", lifespan=lifespan,
    docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware, allow_origins=[settings.allowed_origin], allow_methods=["GET","POST","PATCH"],
    allow_headers=["Authorization","Content-Type"], allow_credentials=False)

class BodyLimit:
    def __init__(self, app):
        self.app = app
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        consumed = 0
        async def bounded_receive():
            nonlocal consumed
            message = await receive()
            consumed += len(message.get("body", b""))
            if consumed > 16_384:
                raise HTTPException(413, "Request size limit exceeded")
            return message
        await self.app(scope, bounded_receive, send)

app.add_middleware(BodyLimit)

@app.exception_handler(SQLAlchemyError)
async def database_failure(request, exc):
    logging.getLogger("api").error("Database request failed (%s)", type(exc).__name__)
    return JSONResponse({"detail":"Database temporarily unavailable"}, status_code=503)

async def authorize(authorization: str = Header(default="")):
    expected = settings.admin_token
    if len(expected) < 32:
        raise HTTPException(503, "Server authentication is not configured")
    token = authorization.removeprefix("Bearer ")
    if not secrets.compare_digest(token, expected):
        raise HTTPException(401, "Authentication required")

async def database():
    if db.Session is None:
        raise HTTPException(503, "Database is not configured")
    async with db.Session() as session:
        yield session

def serialize(row):
    return {column.name: (value.value if isinstance(value,(Outcome,State)) else str(value) if isinstance(value,Decimal) else aware(value) if isinstance(value,datetime) else value)
        for column in row.__table__.columns for value in [getattr(row,column.name)]}

def safe_fixture(fixture):
    data = serialize(fixture)
    if fixture.state == State.RECOMMEND and (fixture.dirty or aware(fixture.commence_time) <= now() or now()-aware(fixture.updated_at) > timedelta(minutes=5)):
        data.update(state="HOLD", suggested_stake=0, reason="Fresh re-verification required")
    return data

@app.get("/health/live")
async def live():
    return {"status":"alive", "timezone":"America/Vancouver"}

@app.get("/health/ready")
async def ready(session=Depends(database)):
    await session.execute(text("SELECT 1 FROM fixtures LIMIT 1"))
    if len(settings.admin_token) < 32:
        raise HTTPException(503, "Authentication not configured")
    return {"status":"ready"}

@app.get("/dashboard", dependencies=[Depends(authorize)])
async def dashboard(session=Depends(database)):
    account = await session.get(Account,1)
    initial = account.initial_bankroll if account else INITIAL_BANKROLL_CAD
    net = await session.scalar(select(func.coalesce(func.sum(PersonalBet.profit_cad),0)))
    exposure = await session.scalar(select(func.coalesce(func.sum(PersonalBet.stake_cad),0)).where(PersonalBet.outcome == Outcome.PENDING))
    settled = await session.scalar(select(func.coalesce(func.sum(PersonalBet.stake_cad),0)).where(PersonalBet.outcome.in_([Outcome.WIN,Outcome.LOSS,Outcome.PUSH])))
    fixtures = (await session.scalars(select(Fixture).where(Fixture.commence_time >= now()-timedelta(hours=12)).order_by(Fixture.commence_time).limit(200))).all()
    latest = await session.scalar(select(func.max(MarketOdds.source_at)))
    return {"bankroll": str(money(initial+net)), "available":str(money(initial+net-exposure)), "exposure":str(money(exposure)),
        "profit":str(money(net)), "roi":str(roi(net,settled)), "unit_value":str(UNIT_VALUE_CAD),
        "source_updated_at":aware(latest) if latest else None, "server_time":now(), "fixtures":[safe_fixture(f) for f in fixtures],
        "stale":latest is None or now()-aware(latest) > timedelta(minutes=5), "performance":await performance(session)}

@app.get("/fixtures/{fixture_id}", dependencies=[Depends(authorize)])
async def fixture_detail(fixture_id: str, session=Depends(database)):
    fixture = await session.get(Fixture,fixture_id)
    if fixture is None:
        raise HTTPException(404,"Fixture not found")
    quotes = (await session.scalars(select(MarketOdds).where(MarketOdds.fixture_id == fixture_id).order_by(MarketOdds.source_at.desc()).limit(100))).all()
    snapshot = await session.get(Snapshot,fixture_id)
    return {"fixture":safe_fixture(fixture), "odds":[serialize(q) for q in quotes], "snapshot":serialize(snapshot) if snapshot else None}

class WagerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    fixture_id: str = Field(min_length=1,max_length=100)
    selection: str = Field(min_length=1,max_length=160)
    odds: str = Field(min_length=1,max_length=20)
    odds_format: str = "auto"
    stake_cad: Decimal = Field(gt=0,le=1_000_000,max_digits=12,decimal_places=2)
    market: str = "h2h"
    line: Decimal | None = Field(default=None, ge=-10000,le=10000)
    bookmaker: str = Field(default="playnow", max_length=40)
    @field_validator("market")
    @classmethod
    def market_valid(cls,value):
        if value not in {"h2h","spreads","totals"}:
            raise ValueError("Unsupported market")
        return value

@app.post("/bets", dependencies=[Depends(authorize)], status_code=201)
async def log_wager(body: WagerInput, session=Depends(database)):
    try:
        odds_taken = parse_odds(body.odds,body.odds_format)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from None
    async with session.begin():
        # Account row serializes concurrent wagers and settlement changes.
        account = await session.get(Account,1,with_for_update=True)
        if not account:
            raise HTTPException(503,"Initialize the account through the migration")
        previous = await session.scalar(select(PersonalBet).where(PersonalBet.request_id == str(body.request_id)))
        if previous:
            if (previous.fixture_id,previous.selection,previous.market,previous.line,previous.odds_taken,previous.stake_cad,previous.bookmaker) != (
                body.fixture_id,body.selection,body.market,body.line,odds_taken,body.stake_cad,body.bookmaker):
                raise HTTPException(409,"Request ID was already used for a different wager")
            return serialize(previous)
        fixture = await session.get(Fixture,body.fixture_id)
        if not fixture:
            raise HTTPException(404,"Fixture not found")
        if body.market in {"spreads","totals"} and body.line is None or body.market == "h2h" and body.line is not None:
            raise HTTPException(422,"Market and exact line do not match")
        if body.market in {"h2h","spreads"} and body.selection not in {fixture.home,fixture.away}:
            raise HTTPException(422,"Selection is not a fixture participant")
        if body.market == "totals" and body.selection not in {"Over","Under"}:
            raise HTTPException(422,"Totals selection must be Over or Under")
        net = await session.scalar(select(func.coalesce(func.sum(PersonalBet.profit_cad),0)))
        exposure = await session.scalar(select(func.coalesce(func.sum(PersonalBet.stake_cad),0)).where(PersonalBet.outcome == Outcome.PENDING))
        if body.stake_cad > account.initial_bankroll+net-exposure:
            raise HTTPException(409,"Stake exceeds available bankroll")
        bet = PersonalBet(request_id=str(body.request_id), fixture_id=body.fixture_id,selection=body.selection,
            odds_taken=odds_taken,stake_cad=money(body.stake_cad),unit_size_at_execution=UNIT_VALUE_CAD,
            market=body.market,line=body.line,bookmaker=body.bookmaker)
        session.add(bet)
        await session.flush()
        session.add(AuditLog(action="LOG_WAGER",entity_id=bet.id, details={"stake":str(bet.stake_cad),"odds":str(odds_taken)}))
        # Exposure changes revoke outstanding recommendations immediately.
        for f in (await session.scalars(select(Fixture).where(Fixture.commence_time > now()))).all():
            dirty(f,"Exposure changed after manual wager")
        return serialize(bet)

@app.get("/bets", dependencies=[Depends(authorize)])
async def ledger(limit: int = 100, offset: int = 0, session=Depends(database)):
    if not 1 <= limit <= 200 or not 0 <= offset <= 100000:
        raise HTTPException(422,"Invalid pagination")
    bets = (await session.scalars(select(PersonalBet).order_by(PersonalBet.created_at.desc()).limit(limit).offset(offset))).all()
    return [serialize(b) for b in bets]

class Settlement(BaseModel):
    outcome: Outcome

@app.patch("/bets/{bet_id}", dependencies=[Depends(authorize)])
async def settle(bet_id: str, body: Settlement, session=Depends(database)):
    async with session.begin():
        await session.get(Account,1,with_for_update=True)
        bet = await session.get(PersonalBet,bet_id,with_for_update=True)
        if not bet:
            raise HTTPException(404,"Wager not found")
        old = bet.outcome
        bet.outcome = body.outcome
        bet.profit_cad = profit(body.outcome.value,bet.odds_taken,bet.stake_cad)
        bet.updated_at = now()
        session.add(AuditLog(action="SETTLE_WAGER",entity_id=bet_id,details={"before":old.value,"after":body.outcome.value,"profit":str(bet.profit_cad)}))
        for fixture in (await session.scalars(select(Fixture).where(Fixture.commence_time > now()))).all():
            dirty(fixture,"Bankroll changed after settlement")
        return serialize(bet)

class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_at: datetime
    source_reference: str = Field(min_length=10,max_length=300)
    factors: dict[str, Decimal]
    personnel_confirmed: bool
    other_markets_verified: bool
    opposing_case_verified: bool
    maps_veto_verified: bool = False
    home_players: list[dict] | None = None
    away_players: list[dict] | None = None

@app.post("/fixtures/{fixture_id}/evidence", dependencies=[Depends(authorize)])
async def verified_evidence(fixture_id: str, body: EvidenceInput, session=Depends(database)):
    from app.maths import baseline
    try:
        source = aware(body.source_at)
        if not timedelta(0) <= now()-source <= timedelta(minutes=30):
            raise ValueError("Verification source must be <=30 minutes old")
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from None
    async with session.begin():
        fixture = await session.get(Fixture,fixture_id,with_for_update=True)
        if not fixture:
            raise HTTPException(404,"Fixture not found")
        try:
            baseline(fixture.sport,body.factors)
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from None
        roster_ok = complete_roster(body.home_players) and complete_roster(body.away_players)
        if fixture.sport != "NHL" and not roster_ok:
            body.personnel_confirmed = False
        # New factors may be collected before the anchor only. Frozen probability never changes later.
        factors = fixture.metrics.get("factors",{}) if now() >= aware(fixture.commence_time)-timedelta(minutes=30) else {k:float(v) for k,v in body.factors.items()}
        if now() < aware(fixture.commence_time)-timedelta(minutes=30):
            session.add(Evidence(fixture_id=fixture_id,kind="model_factors",source_at=source,observed_at=now(),payload=factors))
        fixture.metrics = {**fixture.metrics, "factors":factors,"personnel_confirmed":body.personnel_confirmed,
            "confirmed_at":source.isoformat(), "roster_complete":roster_ok,
            "other_markets_verified":body.other_markets_verified,"opposing_case_verified":body.opposing_case_verified,
            "maps_veto_verified":body.maps_veto_verified,"source_reference":body.source_reference}
        dirty(fixture,"Verified evidence changed; re-evaluation required")
        if not body.personnel_confirmed:
            fixture.state = State.HOLD
        session.add(AuditLog(action="VERIFY_EVIDENCE",entity_id=fixture_id,details={"source":body.source_reference,"at":source.isoformat()}))
        return safe_fixture(fixture)


if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv('PORT', '10000'))
    if not 1 <= port <= 65535:
        raise ValueError('PORT must be between 1 and 65535')
    uvicorn.run(app, host='0.0.0.0', port=port, workers=1, log_level='info')
