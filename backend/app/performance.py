"""All-history performance from recorded tickets, separate from model accuracy."""
from decimal import Decimal
from collections import defaultdict
from sqlalchemy import select, func, case
from .models import PersonalBet, Outcome, Snapshot, Fixture
from .maths import money, roi
from .clock import aware


async def performance(session,sport=None):
    def scope(statement,model):
        return statement.join(Fixture,model.fixture_id==Fixture.id).where(Fixture.sport==sport) if sport else statement
    grouped = (await session.execute(scope(select(
        PersonalBet.outcome, func.count(), func.sum(PersonalBet.stake_cad),
        func.sum(PersonalBet.profit_cad)).group_by(PersonalBet.outcome),PersonalBet))).all()
    counts = {outcome.value: int(count) for outcome, count, _, _ in grouped}
    settled_outcomes = {Outcome.WIN, Outcome.LOSS, Outcome.PUSH}
    stake = sum((amount for outcome, _, amount, _ in grouped if outcome in settled_outcomes), Decimal(0))
    net = sum((profit for outcome, _, _, profit in grouped if outcome in settled_outcomes), Decimal(0))
    wins, losses, pushes = (counts.get(name, 0) for name in ('WIN', 'LOSS', 'PUSH'))
    # Group in Vancouver time regardless of the PostgreSQL session timezone.
    # SQLite is used only by isolated tests and the disposable local QA server.
    if session.bind.dialect.name == 'postgresql':
        day = func.date(func.timezone('America/Vancouver', PersonalBet.updated_at))
        days = (await session.execute(scope(select(day, func.sum(PersonalBet.profit_cad))
            .where(PersonalBet.outcome.in_(settled_outcomes)).group_by(day).order_by(day),PersonalBet))).all()
    else:
        totals = defaultdict(lambda: Decimal(0))
        rows = (await session.execute(scope(select(PersonalBet.updated_at, PersonalBet.profit_cad)
            .where(PersonalBet.outcome.in_(settled_outcomes)),PersonalBet))).all()
        for timestamp, profit in rows:
            totals[aware(timestamp).date()] += profit
        days = sorted(totals.items())
    cumulative = Decimal(0)
    curve = []
    for date, profit in days:
        cumulative += profit
        curve.append({'date': str(date), 'profit': str(money(cumulative))})
    # Bound payload size without discarding earlier profit or the last balance.
    if len(curve) > 180:
        curve = [curve[round(i * (len(curve)-1) / 179)] for i in range(180)]
    p = Snapshot.prediction_home_probability
    actual = case((Snapshot.final_home_win.is_(True), 1), else_=0)
    evaluated, directional, correct, brier = (await session.execute(scope(select(func.count(),
        func.sum(case((p != Decimal('.5'), 1), else_=0)),
        func.sum(case(((p != Decimal('.5')) & ((p > Decimal('.5')) == Snapshot.final_home_win), 1), else_=0)),
        func.avg((p-actual)*(p-actual))).where(p.is_not(None),
        Snapshot.final_home_win.is_not(None)),Snapshot))).one()
    return {'wins': wins, 'losses': losses, 'pushes': pushes, 'voids': counts.get('VOID', 0),
        'pending': counts.get('PENDING', 0), 'settled': wins+losses+pushes,
        'win_rate': str(round(Decimal(wins)*100/(wins+losses), 2)) if wins+losses else None,
        'roi': str(roi(net, stake)) if stake else None, 'settled_stake': str(money(stake)),
        'profit': str(money(net)), 'curve': curve,
        'model': {'evaluated': evaluated, 'accuracy': str(round(Decimal(correct or 0)*100/directional, 2)) if directional else None,
            'brier': str(round(Decimal(str(brier)), 4)) if evaluated else None}}

async def model_stats(session,sport):
    recorded=await performance(session,sport=sport)
    p=Snapshot.prediction_home_probability
    total=await session.scalar(select(func.count()).select_from(Snapshot).join(Fixture)
        .where(Fixture.sport==sport,p.is_not(None)))
    rows=(await session.execute(select(Snapshot,Fixture).join(Fixture)
        .where(Fixture.sport==sport,p.is_not(None))
        .order_by(Snapshot.anchor_at.desc()).limit(200))).all()
    predictions=[]
    for snapshot,fixture in rows:
        probability=snapshot.prediction_home_probability
        picked_home=probability>Decimal('.5')
        predictions.append({'fixture_id':fixture.id,'home':fixture.home,'away':fixture.away,
            'selection':'Even match' if probability==Decimal('.5') else fixture.home if picked_home else fixture.away,
            'probability':str(probability if picked_home else 1-probability),
            'anchor_at':aware(snapshot.anchor_at),'model_version':snapshot.model_version,
            'result':None if snapshot.final_home_win is None else 'NO DIRECTION' if probability==Decimal('.5') else 'CORRECT' if picked_home==snapshot.final_home_win else 'INCORRECT'})
    return {'sport':sport,'model':{**recorded['model'],'predicted':int(total or 0),
        'pending':int(total or 0)-recorded['model']['evaluated']},'predictions':predictions,
        'note':'Only saved model forecasts are graded. Recorded wager returns belong to Bankroll; no model ROI is inferred from them.'}
