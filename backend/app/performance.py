"""All-history performance from recorded tickets, separate from model accuracy."""
from decimal import Decimal
from collections import defaultdict
from sqlalchemy import select, func, case
from .models import PersonalBet, Outcome, Snapshot
from .maths import money, roi
from .clock import aware


async def performance(session):
    grouped = (await session.execute(select(
        PersonalBet.outcome, func.count(), func.sum(PersonalBet.stake_cad),
        func.sum(PersonalBet.profit_cad)).group_by(PersonalBet.outcome))).all()
    counts = {outcome.value: int(count) for outcome, count, _, _ in grouped}
    settled_outcomes = {Outcome.WIN, Outcome.LOSS, Outcome.PUSH}
    stake = sum((amount for outcome, _, amount, _ in grouped if outcome in settled_outcomes), Decimal(0))
    net = sum((profit for outcome, _, _, profit in grouped if outcome in settled_outcomes), Decimal(0))
    wins, losses, pushes = (counts.get(name, 0) for name in ('WIN', 'LOSS', 'PUSH'))
    # Group in Vancouver time regardless of the PostgreSQL session timezone.
    # SQLite is used only by isolated tests and the disposable local QA server.
    if session.bind.dialect.name == 'postgresql':
        day = func.date(func.timezone('America/Vancouver', PersonalBet.updated_at))
        days = (await session.execute(select(day, func.sum(PersonalBet.profit_cad))
            .where(PersonalBet.outcome.in_(settled_outcomes)).group_by(day).order_by(day))).all()
    else:
        totals = defaultdict(lambda: Decimal(0))
        rows = (await session.execute(select(PersonalBet.updated_at, PersonalBet.profit_cad)
            .where(PersonalBet.outcome.in_(settled_outcomes)))).all()
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
    evaluated, correct, brier = (await session.execute(select(func.count(),
        func.sum(case(((p > Decimal('.5')) == Snapshot.final_home_win, 1), else_=0)),
        func.avg((p-actual)*(p-actual))).where(p.is_not(None),
        p != Decimal('.5'), Snapshot.final_home_win.is_not(None)))).one()
    return {'wins': wins, 'losses': losses, 'pushes': pushes, 'voids': counts.get('VOID', 0),
        'pending': counts.get('PENDING', 0), 'settled': wins+losses+pushes,
        'win_rate': str(round(Decimal(wins)*100/(wins+losses), 2)) if wins+losses else None,
        'roi': str(roi(net, stake)) if stake else None, 'settled_stake': str(money(stake)),
        'profit': str(money(net)), 'curve': curve,
        'model': {'evaluated': evaluated, 'accuracy': str(round(Decimal(correct or 0)*100/evaluated, 2)) if evaluated else None,
            'brier': str(round(Decimal(str(brier)), 4)) if evaluated else None}}
