"""Exercise the additive migration without production database credentials."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from sqlalchemy import create_engine, inspect
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from app.models import Fixture, PaperForecast, PaperPriceObservation, PaperInputArchive


def test_paper_migration_creates_private_research_structure_and_is_repeatable(monkeypatch):
    path=Path(__file__).resolve().parents[1]/'migrations/versions/0003_paper_research.py'
    spec=importlib.util.spec_from_file_location('paper_migration_under_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    engine=create_engine('sqlite:///:memory:')
    try:
        with engine.begin() as connection:
            Fixture.__table__.create(connection)
            monkeypatch.setattr(module,'op',SimpleNamespace(get_bind=lambda:connection))
            module.upgrade();module.upgrade()
            names=set(inspect(connection).get_table_names())
            assert names=={'fixtures','paper_forecasts','paper_price_observations','paper_input_archives'}
            unique=inspect(connection).get_unique_constraints('paper_forecasts')
            assert any(u['column_names']==['fixture_id','model_version'] for u in unique)
            assert 'personal_bets' not in names
        for model in (PaperForecast,PaperPriceObservation,PaperInputArchive):
            ddl=str(CreateTable(model.__table__).compile(dialect=postgresql.dialect()))
            assert 'CREATE TABLE' in ddl
    finally:
        engine.dispose()
