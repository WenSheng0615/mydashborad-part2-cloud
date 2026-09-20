"""Adopt V1 without dropping tables or rewriting existing rows."""
from alembic import op
import sqlalchemy as sa
from migrations.legacy_schema import metadata
revision = "0001_legacy"
down_revision = None
branch_labels = depends_on = None
KNOWN_ADDITIONS = {("notes", "image_url"), ("sessions", "expires_at"), ("quiz_questions", "tag")}

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    # Validate the whole known schema before any DDL; unexpected drift needs review.
    for table in metadata.sorted_tables:
        if table.name not in existing:
            continue
        columns = {c["name"]: c for c in inspector.get_columns(table.name)}
        pk = inspector.get_pk_constraint(table.name)["constrained_columns"]
        if set(pk) != {c.name for c in table.primary_key}:
            raise RuntimeError(f"Unexpected primary key: {table.name}")
        for col in table.columns:
            if col.name not in columns:
                if (table.name, col.name) not in KNOWN_ADDITIONS:
                    raise RuntimeError(f"Unexpected missing column: {table.name}.{col.name}")
            elif columns[col.name]["type"]._type_affinity is not col.type._type_affinity:
                raise RuntimeError(f"Unexpected column type: {table.name}.{col.name}")
    for table in metadata.sorted_tables:
        if table.name not in existing:
            table.create(bind)
            continue
        columns = {c["name"] for c in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name not in columns:
                default = sa.text("''") if col.name == "tag" else None
                op.add_column(table.name, sa.Column(col.name, col.type, nullable=True, server_default=default))
        indexes = {i["name"] for i in inspector.get_indexes(table.name)}
        for index in table.indexes:
            if index.name not in indexes:
                index.create(bind)

def downgrade():
    raise RuntimeError("V1 adoption is irreversible; restore a verified SQLite backup")
