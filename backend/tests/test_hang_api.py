"""路由级干湿隔离：使用 sqlite 内存库直接调用 hang()。"""

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.router import hang
from app.database import Base
from app.models.models import HangRail, RailPlacement, Store, WorkOrder
from app.schemas.schemas import HangRequest

NOW = datetime(2026, 9, 23, 12, 0, 0)


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    store = Store(name="测试店")
    session.add(store)
    session.flush()
    rail_a = HangRail(store_id=store.id, label="A 杆", length_cm=200)
    rail_b = HangRail(store_id=store.id, label="B 杆", length_cm=160)
    session.add_all([rail_a, rail_b])
    session.flush()

    dry = WorkOrder(store_id=store.id, ticket_code="D1", garment_name="羊毛大衣",
                    length_cm=45, dry_state="dry", status="hung", due_at=NOW + timedelta(days=1))
    session.add(dry)
    session.flush()
    session.add(RailPlacement(rail_id=rail_a.id, order_id=dry.id, start_cm=0, end_cm=45))

    wet = WorkOrder(store_id=store.id, ticket_code="W1", garment_name="羽绒服",
                    length_cm=50, dry_state="wet", status="ready", due_at=NOW + timedelta(days=1))
    dry2 = WorkOrder(store_id=store.id, ticket_code="D2", garment_name="西裤",
                     length_cm=30, dry_state="dry", status="ready", due_at=NOW + timedelta(days=1))
    legacy = WorkOrder(store_id=store.id, ticket_code="L1", garment_name="旧衬衫",
                       length_cm=30, dry_state=None, status="ready", due_at=NOW + timedelta(days=1))
    session.add_all([wet, dry2, legacy])
    session.commit()
    yield session, store, rail_a, rail_b, wet, dry2, legacy
    session.close()


def _order(db_session, ticket):
    from sqlalchemy import select
    return db_session.scalar(select(WorkOrder).where(WorkOrder.ticket_code == ticket))


def test_wet_cannot_hang_on_dry_rail_explicit(db):
    session, _store, rail_a, _rail_b, wet, *_ = db
    with pytest.raises(HTTPException) as ei:
        hang(HangRequest(order_id=wet.id, rail_id=rail_a.id), db=session)
    assert ei.value.status_code == 409
    assert ei.value.detail["code"] == "isolation_conflict"


def test_wet_skips_dry_rail_and_hangs_other_rail(db):
    """自动扫杆：A（干衣）隔离 → 改扫空杆 B 成功。"""
    session, _store, rail_a, rail_b, wet, *_ = db
    out = hang(HangRequest(order_id=wet.id), db=session)
    assert out.status == "hung"
    placed = session.query(RailPlacement).filter_by(order_id=wet.id, active=1).one()
    assert placed.rail_id == rail_b.id
    assert placed.start_cm == 0  # 空杆 First-Fit 从头开始


def test_same_state_first_fit_continues(db):
    session, _store, rail_a, _rail_b, _wet, dry2, *_ = db
    out = hang(HangRequest(order_id=dry2.id), db=session)
    assert out.status == "hung"
    placed = session.query(RailPlacement).filter_by(order_id=dry2.id, active=1).one()
    assert placed.rail_id == rail_a.id
    assert placed.start_cm == 45  # 接在干衣之后，最左空隙 First-Fit


def test_legacy_unlabeled_treated_as_dry(db):
    session, _store, rail_a, rail_b, _wet, _dry2, legacy = db
    out = hang(HangRequest(order_id=legacy.id), db=session)
    assert out.status == "hung"
    placed = session.query(RailPlacement).filter_by(order_id=legacy.id, active=1).one()
    # 未标注按干衣 → 可继续上 A 杆，接在 45 之后
    assert placed.rail_id == rail_a.id
    assert placed.start_cm == 45
