import asyncio
import json
from pathlib import Path
import argparse
from sqlalchemy import select
from . import db
from .models import Snapshot,Fixture
from .clock import aware

async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sport',choices=['NHL','CS2'],required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    db.configure_database()
    async with db.Session() as session:
        rows=(await session.execute(select(Snapshot,Fixture).join(Fixture).where(Fixture.sport==args.sport,
            Snapshot.final_home_win.is_not(None),Snapshot.baseline_home_probability.is_not(None)).limit(100000))).all()
        records=[{'fixture_id':s.fixture_id,'sport':f.sport,'commence_time':aware(f.commence_time).isoformat(),
            'anchor_at':aware(s.anchor_at).isoformat(),'collected_at':aware(s.collected_at).isoformat(),
            'vector':s.vector,'model_version':s.model_version,'probability':str(s.baseline_home_probability),
            'outcome':int(s.final_home_win),'sources':s.context.get('sources',{}),'factors':s.context.get('factors',{})} for s,f in rows]
    args.output.write_text(json.dumps(records,separators=(',',':')),encoding='utf-8')
    await db.engine.dispose()
    print(f'Exported {len(records)} outcome-labeled snapshots')

if __name__=='__main__':
    asyncio.run(main())
