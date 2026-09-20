"""Add Workspace / Project core without touching legacy data."""
from alembic import op
import sqlalchemy as sa
revision = "0002_workspace_project"
down_revision = "0001_legacy"
branch_labels = depends_on = None

def upgrade():
    op.create_table("workspaces",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_email", sa.String(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("length(trim(name)) BETWEEN 1 AND 120", name="ck_workspace_name"))
    op.create_index("ix_workspaces_user_email", "workspaces", ["user_email"])
    op.create_table("projects",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("kind IN ('project', 'course')", name="ck_project_kind"),
        sa.CheckConstraint("length(trim(name)) BETWEEN 1 AND 120", name="ck_project_name"))
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])

def downgrade():
    raise RuntimeError("Restore a verified backup; automatic downgrade could destroy workspace data")
