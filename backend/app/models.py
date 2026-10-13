import enum
import uuid
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, Date, JSON, Enum, ForeignKey, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator
from datetime import timezone
from .clock import aware
from .clock import now

class PacificTimestamp(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True
    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        value = aware(value)
        return value.astimezone(timezone.utc).replace(tzinfo=None) if dialect.name == "sqlite" else value
    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "sqlite" and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return aware(value)

class Base(DeclarativeBase):
    pass

class State(str, enum.Enum):
    WATCH = "WATCH"
    HOLD = "HOLD"
    PASS = "PASS"
    RECOMMEND = "RECOMMEND"

class Outcome(str, enum.Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    PUSH = "PUSH"
    VOID = "VOID"
    PENDING = "PENDING"

class Fixture(Base):
    __tablename__ = "fixtures"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    sport: Mapped[str] = mapped_column(String(8))
    home: Mapped[str] = mapped_column(String(160))
    away: Mapped[str] = mapped_column(String(160))
    commence_time: Mapped[datetime] = mapped_column(PacificTimestamp(), index=True)
    created_at: Mapped[datetime] = mapped_column(PacificTimestamp(), default=now)
    updated_at: Mapped[datetime] = mapped_column(PacificTimestamp(), default=now)
    state: Mapped[State] = mapped_column(Enum(State), default=State.WATCH)
    dirty: Mapped[bool] = mapped_column(default=True)
    revision: Mapped[int] = mapped_column(default=0)
    probability: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    edge: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    suggested_stake: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    selection: Mapped[str | None] = mapped_column(String(160))
    gates: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_assessment: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(String(500), default="Awaiting source evidence")
    final_home_win: Mapped[bool | None]
    __table_args__ = (CheckConstraint("sport IN ('NHL','MLB','NFL','NBA','CS2','VAL','LOL')"),)

class MarketOdds(Base):
    __tablename__ = "market_odds"
    id: Mapped[int] = mapped_column(primary_key=True)
    fixture_id: Mapped[str] = mapped_column(ForeignKey("fixtures.id"), index=True)
    bookmaker: Mapped[str] = mapped_column(String(40))
    market: Mapped[str] = mapped_column(String(20))
    selection: Mapped[str] = mapped_column(String(160))
    line: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    decimal_odds: Mapped[Decimal] = mapped_column(Numeric(16, 8))
    implied_probability: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    source_at: Mapped[datetime] = mapped_column(PacificTimestamp())
    created_at: Mapped[datetime] = mapped_column(PacificTimestamp(), default=now)
    identity: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("fixture_id", "identity", "source_at"),
        CheckConstraint("decimal_odds > 1.0001"), Index("ix_quote_lookup", "fixture_id", "bookmaker", "market", "selection"))

class PersonalBet(Base):
    __tablename__ = "personal_bets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    fixture_id: Mapped[str] = mapped_column(ForeignKey("fixtures.id"))
    selection: Mapped[str] = mapped_column(String(160))
    market: Mapped[str] = mapped_column(String(20), default="h2h")
    line: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    bookmaker: Mapped[str] = mapped_column(String(40), default="playnow")
    odds_taken: Mapped[Decimal] = mapped_column(Numeric(16, 8))
    stake_cad: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    unit_size_at_execution: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    outcome: Mapped[Outcome] = mapped_column(Enum(Outcome), default=Outcome.PENDING)
    profit_cad: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(PacificTimestamp(), default=now)
    updated_at: Mapped[datetime] = mapped_column(PacificTimestamp(), default=now)
    __table_args__ = (CheckConstraint("stake_cad > 0 AND odds_taken > 1.0001 AND unit_size_at_execution > 0"),)

class Account(Base):
    __tablename__ = "account"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    initial_bankroll: Mapped[Decimal] = mapped_column(Numeric(12, 2))

class Evidence(Base):
    __tablename__ = "source_evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    fixture_id: Mapped[str] = mapped_column(ForeignKey("fixtures.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    observed_at: Mapped[datetime] = mapped_column(PacificTimestamp(), default=now)
    source_at: Mapped[datetime] = mapped_column(PacificTimestamp())
    payload: Mapped[dict] = mapped_column(JSON)

class Snapshot(Base):
    __tablename__ = "frozen_snapshots"
    fixture_id: Mapped[str] = mapped_column(ForeignKey("fixtures.id"), primary_key=True)
    anchor_at: Mapped[datetime] = mapped_column(PacificTimestamp())
    collected_at: Mapped[datetime] = mapped_column(PacificTimestamp(), default=now)
    game_date: Mapped[date] = mapped_column(Date)
    vector: Mapped[list] = mapped_column(JSON)
    evidence_ids: Mapped[list] = mapped_column(JSON)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    baseline_home_probability: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    prediction_home_probability: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    model_version: Mapped[str] = mapped_column(String(40))
    final_home_win: Mapped[bool | None]
    brier: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))

class EvaluationCycle(Base):
    __tablename__ = "evaluation_cycles"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    fixture_id: Mapped[str] = mapped_column(ForeignKey("fixtures.id"))
    llm_attempts: Mapped[int] = mapped_column(default=0)
    report: Mapped[dict | None] = mapped_column(JSON)

class RuntimeLimit(Base):
    __tablename__ = "runtime_limits"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    used: Mapped[int] = mapped_column(default=0)
    blocked_until: Mapped[datetime | None] = mapped_column(PacificTimestamp())

class JobLease(Base):
    __tablename__ = "job_leases"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(PacificTimestamp())

class ModelValidation(Base):
    __tablename__ = "model_validation"
    version: Mapped[str] = mapped_column(String(40), primary_key=True)
    sport: Mapped[str] = mapped_column(String(8))
    parameters: Mapped[dict] = mapped_column(JSON)
    report: Mapped[dict] = mapped_column(JSON)
    approved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(PacificTimestamp(), default=now)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(PacificTimestamp(), default=now)
