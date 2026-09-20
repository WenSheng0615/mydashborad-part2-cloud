from alembic import context
from sqlalchemy import create_engine, pool
from config import DATABASE_URL
from models import Base

if context.is_offline_mode():
    raise RuntimeError("V1 adoption needs online schema inspection; use a database copy")
engine = create_engine(context.config.attributes.get("database_url", DATABASE_URL), poolclass=pool.NullPool)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
