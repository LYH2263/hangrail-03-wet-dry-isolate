from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def ensure_columns() -> None:
    """Lightweight additive migration for databases created before ALTERs.

    ``create_all`` never touches existing tables, so older volumes would miss
    newly added columns (e.g. work_orders.garment_state). Add them in place;
    NULL rows are interpreted per current semantics (legacy = dry).
    """
    inspector = inspect(engine)
    tables = {t: {c["name"] for c in inspector.get_columns(t)} for t in inspector.get_table_names()}
    additions = {
        "work_orders": [("garment_state", "VARCHAR(8)")],
    }
    with engine.begin() as conn:
        for table, cols in additions.items():
            if table not in tables:
                continue
            for name, ddl_type in cols:
                if name not in tables[table]:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
