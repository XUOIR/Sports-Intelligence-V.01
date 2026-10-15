"""Private forward paper research; preserve the existing Alembic workflow."""
from alembic import op
from sqlalchemy import text
from app.models import PaperForecast, PaperPriceObservation, PaperInputArchive

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    for table in (PaperForecast.__table__, PaperPriceObservation.__table__, PaperInputArchive.__table__):
        table.create(bind, checkfirst=True)
        if bind.dialect.name == 'postgresql':
            op.execute(f'ALTER TABLE "{table.name}" ENABLE ROW LEVEL SECURITY')
            for role in ('anon', 'authenticated'):
                if bind.execute(text('SELECT 1 FROM pg_roles WHERE rolname=:role'), {'role': role}).scalar():
                    op.execute(f'REVOKE ALL ON TABLE "{table.name}" FROM {role}')


def downgrade():
    raise RuntimeError('Forward paper evidence is preserved; destructive downgrade disabled')
