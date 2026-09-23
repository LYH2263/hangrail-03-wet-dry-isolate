from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import HangRail, RailPlacement, Store, WorkOrder
from app.schemas.schemas import (
    HangRequest,
    OccupancyOut,
    OccupancySeg,
    OrderOut,
    OrderStateRequest,
    PickupRequest,
    RailOut,
    StoreOut,
)
from app.services.rail_engine import (
    IsolationConflict,
    Segment,
    rail_state,
    try_fit,
)

api_router = APIRouter()


def _active_placements(db: Session, rail_id: int) -> list[RailPlacement]:
    return db.scalars(
        select(RailPlacement).where(RailPlacement.rail_id == rail_id, RailPlacement.active == 1)
    ).all()


@api_router.get("/health")
def health():
    return {"status": "ok"}


@api_router.get("/stores", response_model=list[StoreOut])
def stores(db: Session = Depends(get_db)):
    return db.scalars(select(Store).order_by(Store.id)).all()


@api_router.get("/rails", response_model=list[RailOut])
def rails(db: Session = Depends(get_db)):
    return db.scalars(select(HangRail).order_by(HangRail.id)).all()


@api_router.get("/orders", response_model=list[OrderOut])
def orders(db: Session = Depends(get_db)):
    return db.scalars(select(WorkOrder).order_by(WorkOrder.id.desc())).all()


@api_router.patch("/orders/{order_id}", response_model=OrderOut)
def update_order_state(order_id: int, body: OrderStateRequest, db: Session = Depends(get_db)):
    order = db.get(WorkOrder, order_id)
    if not order:
        raise HTTPException(404, "工单不存在")
    if order.status == "hung":
        raise HTTPException(400, "已上杆工单不可修改干湿属性，请先取件")
    order.dry_state = body.dry_state
    db.commit()
    db.refresh(order)
    return order


@api_router.get("/occupancy/{rail_id}", response_model=OccupancyOut)
def occupancy(rail_id: int, db: Session = Depends(get_db)):
    rail = db.get(HangRail, rail_id)
    if not rail:
        raise HTTPException(404, "挂杆不存在")
    placements = _active_placements(db, rail_id)
    segs = []
    states: list[str | None] = []
    for p in placements:
        order = db.get(WorkOrder, p.order_id)
        if not order:
            continue
        states.append(order.dry_state)
        segs.append(
            OccupancySeg(
                order_id=order.id,
                ticket_code=order.ticket_code,
                garment_name=order.garment_name,
                dry_state=order.dry_state,
                start_cm=p.start_cm,
                end_cm=p.end_cm,
            )
        )
    segs.sort(key=lambda s: s.start_cm)
    return OccupancyOut(
        rail_id=rail.id,
        label=rail.label,
        length_cm=rail.length_cm,
        rail_dry_state=rail_state(states),
        segments=segs,
    )


@api_router.post("/hang", response_model=OrderOut)
def hang(body: HangRequest, db: Session = Depends(get_db)):
    order = db.get(WorkOrder, body.order_id)
    if not order:
        raise HTTPException(404, "工单不存在")
    if order.status not in ("ready", "overdue"):
        raise HTTPException(400, "工单状态不可上杆")
    rail_q = select(HangRail).where(HangRail.store_id == order.store_id)
    if body.rail_id:
        rail_q = rail_q.where(HangRail.id == body.rail_id)
    rails = db.scalars(rail_q.order_by(HangRail.id)).all()
    if not rails:
        raise HTTPException(404, "无可用挂杆")

    # 逐杆试挂：隔离冲突与空间不足分别记录
    failures: list[dict] = []
    for rail in rails:
        active = _active_placements(db, rail.id)
        occupied = [Segment(p.start_cm, p.end_cm) for p in active]
        occupied_orders = [db.get(WorkOrder, p.order_id) for p in active]
        occupied_states = [o.dry_state for o in occupied_orders if o]
        result = try_fit(rail.length_cm, occupied, order.length_cm, order.dry_state, occupied_states)
        if isinstance(result, IsolationConflict):
            failures.append(
                {"rail_id": rail.id, "label": rail.label, "reason": "isolation_conflict",
                 "rail_dry_state": result.rail_state}
            )
            continue
        if result is None:
            failures.append(
                {"rail_id": rail.id, "label": rail.label, "reason": "no_space",
                 "rail_dry_state": rail_state(occupied_states)}
            )
            continue
        db.add(
            RailPlacement(
                rail_id=rail.id,
                order_id=order.id,
                start_cm=result.start_cm,
                end_cm=result.end_cm,
            )
        )
        order.status = "hung"
        order.hung_at = datetime.utcnow()
        db.commit()
        db.refresh(order)
        return order

    conflicts = [f for f in failures if f["reason"] == "isolation_conflict"]
    if conflicts and len(conflicts) == len(failures):
        code = "isolation_conflict"
        names = "、".join(f["label"] for f in conflicts)
        wanted = "湿衣" if order.dry_state == "wet" else "干衣"
        message = f"干湿隔离冲突：{names} 已挂相反属性衣物，{wanted}不得同杆（与空隙无关）"
    elif conflicts:
        blocked = "、".join(f"{f['label']}（{'干衣' if f['rail_dry_state'] == 'dry' else '湿衣'}杆隔离）" for f in conflicts)
        message = f"无可上杆位置：{blocked} 干湿隔离，其余挂杆空间不足"
        code = "mixed"
    else:
        code = "no_space"
        message = "挂杆空间不足"
    raise HTTPException(409, detail={"code": code, "message": message, "rails": failures})


@api_router.post("/pickup", response_model=OrderOut)
def pickup(body: PickupRequest, db: Session = Depends(get_db)):
    order = db.scalar(select(WorkOrder).where(WorkOrder.ticket_code == body.ticket_code))
    if not order:
        raise HTTPException(404, "取件码无效")
    if order.status != "hung":
        raise HTTPException(400, "工单未在挂杆上")
    placements = db.scalars(
        select(RailPlacement).where(RailPlacement.order_id == order.id, RailPlacement.active == 1)
    ).all()
    for p in placements:
        p.active = 0
    order.status = "picked"
    db.commit()
    db.refresh(order)
    return order


@api_router.post("/overdue/scan", response_model=list[OrderOut])
def overdue_scan(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    hung = db.scalars(select(WorkOrder).where(WorkOrder.status == "hung")).all()
    marked = []
    for o in hung:
        if o.due_at < now:
            o.status = "overdue"
            marked.append(o)
    ready = db.scalars(select(WorkOrder).where(WorkOrder.status == "ready")).all()
    for o in ready:
        if o.due_at < now:
            o.status = "overdue"
            marked.append(o)
    db.commit()
    return marked


@api_router.get("/overdue", response_model=list[OrderOut])
def overdue_list(db: Session = Depends(get_db)):
    return db.scalars(select(WorkOrder).where(WorkOrder.status == "overdue").order_by(WorkOrder.due_at)).all()
