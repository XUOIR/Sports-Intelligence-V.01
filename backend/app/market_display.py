"""Read the latest saved prices; displaying a market never calls a provider."""
from sqlalchemy import select,func
from .models import MarketOdds

async def latest_quotes(session,fixture_ids):
    if not fixture_ids:return {}
    ranked=select(MarketOdds.id,func.row_number().over(
        partition_by=(MarketOdds.fixture_id,MarketOdds.identity),
        order_by=(MarketOdds.source_at.desc(),MarketOdds.id.desc())).label('position'))\
        .where(MarketOdds.fixture_id.in_(fixture_ids)).subquery()
    rows=(await session.scalars(select(MarketOdds).join(ranked,ranked.c.id==MarketOdds.id)
        .where(ranked.c.position==1).order_by(MarketOdds.source_at.desc()).limit(4000))).all()
    result={}
    for row in rows:
        result.setdefault(row.fixture_id,[]).append(row)
    return result
