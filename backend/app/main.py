from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


def ensure_columns() -> None:
    """轻量迁移：为历史库补齐新增列（项目未引入 Alembic）。"""
    inspector = inspect(engine)
    if "work_orders" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("work_orders")}
    if "dry_state" not in existing:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE work_orders ADD COLUMN dry_state VARCHAR(10)"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_columns()
    if settings.seed_on_empty:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


app = FastAPI(title="HangRail", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
