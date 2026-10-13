import pytest
from app import db
from app.db import direct_database_url

HOST = "db.lagwnyxitcfrdfnuafea.supabase.co"

@pytest.mark.parametrize("password", ["dummy%21password", "dummy!password"])
def test_password_encoding_does_not_double_encode(password):
    target = direct_database_url(f"postgresql://postgres:{password}@{HOST}:5432/postgres")
    assert target.password == "dummy!password"
    assert target.drivername == "postgresql+asyncpg"
    assert target.port == 5432 and target.host == HOST

@pytest.mark.parametrize("uri", [
    f"postgresql://postgres:dummy@{HOST}:6543/postgres",
    "postgresql://postgres:dummy@aws-0-us.pooler.supabase.com:5432/postgres",
    f"postgresql://wrong:dummy@{HOST}:5432/postgres",
    f"postgresql://postgres:dummy@{HOST}:5432/other",
    "sqlite:///:memory:",
])
def test_wrong_database_target_is_rejected_without_echoing_credentials(uri):
    with pytest.raises(ValueError) as exc:
        direct_database_url(uri)
    assert "dummy" not in str(exc.value)

async def test_pool_configuration_without_connecting():
    previous_engine, previous_session = db.engine, db.Session
    try:
        engine = db.configure_database(f"postgresql://postgres:dummy%21@{HOST}:5432/postgres")
        assert engine.pool.size() == 10
        assert engine.pool._max_overflow == 20
        assert engine.pool._recycle == 1800
        assert engine.pool._pre_ping is True
        await engine.dispose()
    finally:
        db.engine, db.Session = previous_engine, previous_session
