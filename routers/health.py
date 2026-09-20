"""Non-mutating health endpoints; no provider calls or private diagnostics."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from alembic.config import Config
from alembic.script import ScriptDirectory
from config import BASE_DIR
from models import Base
import database

router = APIRouter(tags=['health'])
EXPECTED = set(ScriptDirectory.from_config(Config(str(BASE_DIR/'alembic.ini'))).get_heads())

@router.get('/health/live', include_in_schema=False)
def live():
    return {'status': 'alive'}

@router.get('/health/ready', include_in_schema=False)
def ready():
    try:
        with database.SessionLocal() as db:
            if set(db.execute(text('SELECT version_num FROM alembic_version')).scalars()) != EXPECTED:
                raise RuntimeError()
            inspector = inspect(db.connection())
            for table in Base.metadata.sorted_tables:
                actual = {column['name'] for column in inspector.get_columns(table.name)}
                if not set(table.columns.keys()) <= actual:
                    raise RuntimeError()
        return {'status': 'ready'}
    except Exception:
        return JSONResponse({'status': 'not_ready'}, status_code=503)
