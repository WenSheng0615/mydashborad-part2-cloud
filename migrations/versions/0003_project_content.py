"""Local project tasks and optional Note association; no legacy data backfill."""
from alembic import op
import sqlalchemy as sa
revision = "0003_project_content"
down_revision = "0002_workspace_project"
branch_labels = depends_on = None

def upgrade():
    op.create_table("tasks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('todo', 'doing', 'done')", name="ck_task_status"),
        sa.CheckConstraint("length(trim(title)) BETWEEN 1 AND 200", name="ck_task_title"))
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"])
    # SQLite supports adding a nullable REFERENCES column without rebuilding notes.
    op.execute("ALTER TABLE notes ADD COLUMN project_id VARCHAR REFERENCES projects(id)")
    op.create_index("ix_notes_project_id", "notes", ["project_id"])

def downgrade():
    raise RuntimeError("Restore a verified backup; do not discard user tasks")
