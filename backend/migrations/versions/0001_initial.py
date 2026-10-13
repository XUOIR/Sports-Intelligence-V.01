"""Initial V0.1 schema. Subsequent migrations must be explicit and versioned."""
from alembic import op
from sqlalchemy import text
from app.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind)
    bind.execute(text("INSERT INTO account (id, initial_bankroll) VALUES (1, 1100.00) ON CONFLICT DO NOTHING"))
    # Backend-only tables must not be accessible with Supabase public anon/authenticated roles.
    for table in Base.metadata.sorted_tables:
        op.execute(f'ALTER TABLE "{table.name}" ENABLE ROW LEVEL SECURITY')
        for role in ("anon","authenticated"):
            if bind.execute(text("SELECT 1 FROM pg_roles WHERE rolname=:name"),{"name":role}).scalar():
                op.execute(f'REVOKE ALL ON TABLE "{table.name}" FROM {role}')

def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore a verified backup explicitly")
