import asyncio
from alembic import context
from app import db
from app.models import Base
from sqlalchemy import text

def sync_migrations(connection):
    context.configure(connection=connection,target_metadata=Base.metadata)
    with context.begin_transaction():
        connection.execute(text("SELECT pg_advisory_xact_lock(774001)"))
        context.run_migrations()

async def run():
    engine = db.configure_database()
    async with engine.connect() as connection:
        await connection.run_sync(sync_migrations)
    await engine.dispose()

asyncio.run(run())
