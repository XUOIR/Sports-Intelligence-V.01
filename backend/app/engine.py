import hashlib
import json
from datetime import timedelta
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from . import db
from .clock import aware, now
from .models import Fixture, Evidence, Snapshot, State, MarketOdds, PersonalBet, Outcome, Account, EvaluationCycle, ModelValidation
from .features import frozen_vector, validate_source
from .maths import baseline, decimal, calibrated, stake
from .model_config import MODEL_VERSION, MIN_EDGE, GATE_NAMES, MAX_OPEN_EXPOSURE
from .providers import doublecheck
from .http import ProviderError
from .limits import limits, BudgetExceeded

async def freeze(fixture_id: str):
    async with db.Session.begin() as session:
        fixture = await session.get(Fixture, fixture_id, with_for_update=True)
        if fixture is None or await session.get(Snapshot, fixture_id):
            return
        anchor = aware(fixture.commence_time)-timedelta(minutes=30)
        if not anchor <= now() <= anchor+timedelta(seconds=5):
            fixture.state, fixture.reason = State.HOLD, "Exact pre-game anchor missed; no retrospective snapshot"
            return
        selected = {}
        for kind in ("schedule","standings","history"):
            row = await session.scalar(select(Evidence).where(Evidence.fixture_id == fixture_id, Evidence.kind == kind,
                Evidence.observed_at <= anchor).order_by(Evidence.observed_at.desc()).limit(1))
            if row is None:
                fixture.state, fixture.reason = State.HOLD, f"Missing {kind} evidence at frozen anchor"
                return
            try:
                validate_source(kind, row.source_at, row.observed_at, anchor)
            except ValueError as exc:
                fixture.state, fixture.reason = State.HOLD, str(exc)
                return
            selected[kind] = row
        factor_source=None
        try:
            if aware(selected["schedule"].payload["start"]) != aware(fixture.commence_time):
                raise ValueError("Schedule evidence disagrees with official start")
            vector = frozen_vector(selected["standings"].payload["home"], selected["standings"].payload["away"],
                selected["history"].payload, fixture.commence_time)
            factor_source = await session.scalar(select(Evidence).where(Evidence.fixture_id == fixture_id,
                Evidence.kind == "model_factors", Evidence.observed_at <= anchor, Evidence.source_at <= anchor,
                Evidence.source_at >= anchor-timedelta(minutes=30)).order_by(Evidence.observed_at.desc()).limit(1))
            p = baseline(fixture.sport, factor_source.payload if factor_source else {})
        except (ValueError,KeyError,TypeError) as exc:
            # A valid 15-feature snapshot still has value even if advanced factors are missing.
            try:
                vector = frozen_vector(selected["standings"].payload["home"], selected["standings"].payload["away"],
                    selected["history"].payload, fixture.commence_time)
            except (ValueError,KeyError,TypeError):
                fixture.state, fixture.reason = State.HOLD, "Incomplete frozen vector; no imputation"
                return
            p = None
            fixture.state, fixture.reason = State.HOLD, f"Advanced factors missing: {str(exc)[:200]}"
        if now()>anchor+timedelta(seconds=5):
            fixture.state,fixture.reason=State.HOLD,"Anchor processing deadline exceeded; no late snapshot"
            return
        session.add(Snapshot(fixture_id=fixture_id, anchor_at=anchor, game_date=aware(fixture.commence_time).date(), vector=vector,
            evidence_ids=[r.id for r in selected.values()], baseline_home_probability=p, model_version=MODEL_VERSION,
            context={"sources": {k:{"source_at":aware(r.source_at).isoformat(),"observed_at":aware(r.observed_at).isoformat(),"payload":r.payload} for k,r in selected.items()},
                "factors":factor_source.payload if factor_source else {}}))
        fixture.dirty = True

def recommendation_state(gates: dict, *, has_execution: bool, personnel: bool, edge: Decimal | None, frozen: bool):
    if not personnel:
        return State.HOLD
    if not has_execution:
        return State.WATCH
    if not frozen or not gates.get("probability"):
        return State.HOLD
    if edge is not None and edge < MIN_EDGE:
        return State.PASS
    return State.RECOMMEND if all(gates.get(k) is True for k in GATE_NAMES) else State.HOLD

async def evaluate(fixture_id: str):
    if not await limits.lease(f"eval:{fixture_id}", 30):
        return
    async with db.Session() as session:
        fixture = await session.get(Fixture, fixture_id)
        if not fixture or aware(fixture.commence_time) <= now():
            return
        snapshot = await session.get(Snapshot, fixture_id)
        if not snapshot or aware(snapshot.anchor_at) != aware(fixture.commence_time)-timedelta(minutes=30) or not timedelta(0)<=aware(snapshot.collected_at)-aware(snapshot.anchor_at)<=timedelta(seconds=5):
            fixture.state, fixture.reason, fixture.suggested_stake = State.HOLD, "Awaiting valid frozen anchor", 0
            await session.commit()
            return
        metrics = fixture.metrics
        confirmed_at = metrics.get("confirmed_at")
        personnel = metrics.get("personnel_confirmed") is True and bool(confirmed_at) and timedelta(0) <= now()-aware(confirmed_at) <= timedelta(minutes=30)
        if fixture.sport in {"CS2","VAL","LOL"}:
            personnel = personnel and metrics.get("roster_complete") is True
        quotes = (await session.scalars(select(MarketOdds).where(MarketOdds.fixture_id == fixture_id,
            MarketOdds.market == "h2h", MarketOdds.bookmaker.in_(["playnow","bclc"]),
            MarketOdds.source_at >= now()-timedelta(minutes=5), MarketOdds.source_at <= now()).order_by(MarketOdds.source_at.desc()).limit(20))).all()
        latest = {}
        for q in quotes:
            latest.setdefault((q.bookmaker,q.selection), q)
        # Require a complete binary market; three-way / single-side quotes cannot masquerade as executable prices.
        complete = [q for q in latest.values() if q.selection in {fixture.home,fixture.away} and
            (q.bookmaker, fixture.away if q.selection == fixture.home else fixture.home) in latest]
        execution_checked=metrics.get("execution_verified_at")
        if metrics.get("execution_source_present") is not True or not execution_checked or not timedelta(0)<=now()-aware(execution_checked)<=timedelta(minutes=5):
            complete=[]
        model = await session.scalar(select(ModelValidation).where(ModelValidation.sport == fixture.sport,
            ModelValidation.approved.is_(True)).order_by(ModelValidation.created_at.desc()).limit(1))
        probability_ok = bool(model and aware(model.created_at) <= aware(snapshot.anchor_at) and snapshot.model_version == MODEL_VERSION and snapshot.baseline_home_probability is not None
            and model.report.get("baseline_version") == MODEL_VERSION and
            timedelta(0) <= now()-aware(model.created_at) <= timedelta(days=90) and
            aware(model.report["test_through"]).date() < snapshot.game_date)
        p_home = calibrated(snapshot.baseline_home_probability, model.parameters) if probability_ok else None
        if p_home is not None:
            snapshot.prediction_home_probability = p_home
        choices = [(q, p_home if q.selection == fixture.home else 1-p_home) for q in complete] if p_home is not None else []
        chosen = max(choices, key=lambda pair: pair[1]-pair[0].implied_probability) if choices else None
        account = await session.get(Account, 1)
        net = await session.scalar(select(func.coalesce(func.sum(PersonalBet.profit_cad),0)))
        exposure = await session.scalar(select(func.coalesce(func.sum(PersonalBet.stake_cad),0)).where(PersonalBet.outcome == Outcome.PENDING))
        duplicate = await session.scalar(select(PersonalBet.id).where(PersonalBet.fixture_id == fixture_id, PersonalBet.outcome == Outcome.PENDING).limit(1))
        bankroll = max(Decimal(0), account.initial_bankroll+net) if account else Decimal(0)
        gates = {key: False for key in GATE_NAMES}
        gates.update(personnel=personnel, form=len(snapshot.vector) == 15,
            maps_veto=fixture.sport == "NHL" or metrics.get("maps_veto_verified") is True,
            other_markets=metrics.get("other_markets_verified") is True,
            opposing_case=metrics.get("opposing_case_verified") is True, probability=probability_ok,
            overlap_exposure=not duplicate and bankroll > 0 and exposure < bankroll*MAX_OPEN_EXPOSURE)
        edge = None
        suggested = Decimal(0)
        if chosen:
            quote, p = chosen
            edge = p-quote.implied_probability
            gates["price"] = edge >= MIN_EDGE
            available = min(bankroll-exposure, bankroll*MAX_OPEN_EXPOSURE-exposure)
            suggested = stake(p, quote.decimal_odds, bankroll, available)
            gates["overlap_exposure"] = gates["overlap_exposure"] and suggested > 0
            fixture.selection, fixture.probability, fixture.edge = quote.selection, p, edge
            fixture.target_price = 1/(p-MIN_EDGE) if p > MIN_EDGE else None
        else:
            fixture.probability, fixture.edge, fixture.target_price = None, None, None
        # AI can veto factual gates, never supply them. No paid call until every deterministic gate passes.
        revision = fixture.revision
        cycle_id = hashlib.sha256(json.dumps([fixture_id, snapshot.anchor_at.isoformat(), revision,
            chosen[0].id if chosen else None, model.version if model else None], separators=(",", ":")).encode()).hexdigest()
        if chosen and all(gates.values()):
            await session.execute(insert(EvaluationCycle).values(id=cycle_id, fixture_id=fixture_id, llm_attempts=0).on_conflict_do_nothing())
            await session.commit()  # Persist budget identity before invoking a paid provider.
            cycle = await session.get(EvaluationCycle, cycle_id)
            try:
                report = cycle.report or await doublecheck(fixture, chosen[1], chosen[0], cycle_id, gates)
                cycle.report = report
                fixture.risk_assessment = report
                gates["opposing_case"] = gates["opposing_case"] and report["opposing_case_verified"]
                gates["other_markets"] = gates["other_markets"] and report["other_markets_verified"]
                gates["maps_veto"] = gates["maps_veto"] and (fixture.sport == "NHL" or report["veto_verified"])
            except (ProviderError, BudgetExceeded) as exc:
                gates["opposing_case"] = False
                fixture.risk_assessment = {"error":str(exc)[:300]}
            await session.refresh(fixture)  # Recheck evidence changes while waiting on network.
            if fixture.revision != revision or aware(fixture.commence_time) <= now():
                fixture.state, fixture.dirty, fixture.suggested_stake = State.HOLD, True, 0
                fixture.reason = "Evidence changed during adversarial review"
                await session.commit()
                return
        if chosen and now()-aware(chosen[0].source_at)>timedelta(minutes=5):
            gates["price"]=False
        if confirmed_at and now()-aware(confirmed_at)>timedelta(minutes=30):
            gates["personnel"]=False
            personnel=False
        fixture.gates = gates
        fixture.state = recommendation_state(gates, has_execution=bool(complete), personnel=personnel, edge=edge, frozen=True)
        fixture.suggested_stake = suggested if fixture.state == State.RECOMMEND else 0
        fixture.dirty = False
        fixture.reason = "Eight verification gates passed" if fixture.state == State.RECOMMEND else "; ".join(k.replace("_"," ") for k,v in gates.items() if not v)[:500]
        await session.commit()
