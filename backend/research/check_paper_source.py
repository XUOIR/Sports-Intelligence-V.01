"""Check the free official source with a persistent, isolated request ledger.

Uses exactly the production admission/cache rules. Never loads a production DB
or calls paid providers; requires an explicit local SQLite path.
"""
import argparse
import asyncio
import json
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app import db
from app.models import Base, ProviderState, RuntimeLimit
from app.nhl_paper_model import load_bundle
from app.nhl_paper_history import refresh, KEY


async def check(path):
    path=Path(path).resolve()
    path.parent.mkdir(parents=True,exist_ok=True)
    engine=create_async_engine('sqlite+aiosqlite:///'+path.as_posix())
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    db.Session=async_sessionmaker(engine,expire_on_commit=False)
    try:
        bundle,_=load_bundle()
        await refresh(bundle)
        async with db.Session() as session:
            cached=await session.get(ProviderState,KEY)
            if not cached:raise RuntimeError('No successful admitted source observation')
            return {key:cached.info[key] for key in ('as_of_date','season','total_scheduled',
                'completed_prior_date','source_sha256','archive_sha256','observed_at')}
    finally:
        await engine.dispose()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--ledger',required=True)
    args=parser.parse_args()
    print(json.dumps(asyncio.run(check(args.ledger)),indent=2))
