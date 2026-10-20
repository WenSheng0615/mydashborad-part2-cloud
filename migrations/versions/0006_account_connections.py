"""Separate account profiles and owner-scoped encrypted service credentials."""
from alembic import op
import sqlalchemy as sa
revision = '0006_account_connections'
down_revision = '0005_module_preferences'
branch_labels = depends_on = None

def upgrade():
    op.create_table('account_profiles',
        sa.Column('user_email',sa.String(),primary_key=True),
        sa.Column('google_subject',sa.String(),nullable=False,unique=True),
        sa.Column('name',sa.String(),nullable=False),sa.Column('picture',sa.Text(),nullable=False))
    op.create_table('service_connections',
        sa.Column('user_email',sa.String(),primary_key=True),sa.Column('provider',sa.String(40),primary_key=True),
        sa.Column('enabled',sa.Boolean(),nullable=False),sa.Column('secret',sa.Text()),
        sa.Column('account',sa.String(),nullable=False),sa.Column('generation',sa.Integer(),nullable=False))

def downgrade():
    for table in ('account_profiles','service_connections'):
        if op.get_bind().execute(sa.text('SELECT count(*) FROM '+table)).scalar():
            raise RuntimeError('Account/connection data exists; restore a verified backup instead')
    op.drop_table('service_connections');op.drop_table('account_profiles')
