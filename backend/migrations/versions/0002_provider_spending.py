"""Durable paid-call identities and non-secret provider quota observations."""
from alembic import op
from sqlalchemy import text
from app.models import ProviderCall, ProviderState

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    for table in (ProviderCall.__table__, ProviderState.__table__):
        table.create(bind, checkfirst=True)
        op.execute(f'ALTER TABLE "{table.name}" ENABLE ROW LEVEL SECURITY')
        for role in ('anon','authenticated'):
            if bind.execute(text('SELECT 1 FROM pg_roles WHERE rolname=:role'),{'role':role}).scalar():
                op.execute(f'REVOKE ALL ON TABLE "{table.name}" FROM {role}')

def downgrade():
    raise RuntimeError('Spending history is preserved; destructive downgrade disabled')
