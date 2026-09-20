"""Archive projects, recover notes and store project reference links."""
from alembic import op
import sqlalchemy as sa
revision = "0004_daily_workspace"
down_revision = "0003_project_content"
branch_labels = depends_on = None

def upgrade():
    op.add_column("projects", sa.Column("archived_at", sa.DateTime(), nullable=True))
    op.add_column("notes", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.create_table("project_links",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_project_links_project_id", "project_links", ["project_id"])

def downgrade():
    raise RuntimeError("Restore a verified backup to retain archived content")
