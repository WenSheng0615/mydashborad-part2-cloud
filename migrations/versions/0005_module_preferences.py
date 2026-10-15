"""Owner-scoped built-in App preferences; preserve all existing app data."""
from alembic import op
import sqlalchemy as sa
revision = "0005_module_preferences"
down_revision = "0004_daily_workspace"
branch_labels = depends_on = None


def upgrade():
    op.create_table("module_preferences",
        sa.Column("user_email", sa.String(), primary_key=True),
        sa.Column("module_id", sa.String(40), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False))


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM module_preferences")).scalar():
        raise RuntimeError("Module preferences exist; restore a verified backup instead")
    op.drop_table("module_preferences")
