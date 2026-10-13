"""Generate a reviewable PostgreSQL schema without connecting to a database."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from sqlalchemy import create_mock_engine
from app.models import Base

sql=[]
def emit(statement,*args,**kwargs):
    sql.append(str(statement.compile(dialect=engine.dialect))+";")
engine=create_mock_engine("postgresql://",emit)
Base.metadata.create_all(engine)
sql.append("INSERT INTO account (id, initial_bankroll) VALUES (1, 1100.00) ON CONFLICT DO NOTHING;")
for table in Base.metadata.sorted_tables:
    sql.append(f'ALTER TABLE "{table.name}" ENABLE ROW LEVEL SECURITY;')
    sql.append(f'REVOKE ALL ON TABLE "{table.name}" FROM anon, authenticated;')
Path(__file__).resolve().parents[1].joinpath('backend/schema.sql').write_text("-- Review reference. Deploy using Alembic.\n"+"\n\n".join(sql)+"\n",encoding="utf-8")
print(f"PostgreSQL schema generated: {len(Base.metadata.tables)} tables")
