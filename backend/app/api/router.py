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
    OrderUpdate,
    PickupRequest,
    RailOut,
    StoreOut,
)
from app.services.rail_engine import (
    Segment,
    first_fit,
    normalize_state,
    states_compatible,
)

api_router = APIRouter()


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
def update_order(order_id: int, body: OrderUpdate, db: Session = Depends(get_db)):
    order = db.get(WorkOrder, order_id)
    if not order:
        raise HTTPException(404, "工单不存在")
    # A hanging garment already defines its rail's wet/dry set; flipping it
    # mid-hang would silently mix states on the rail.
    if order.status == "hung":
        raise HTTPException(400, "已上杆工单不可修改干湿属性，请先取件释放")
    order.garment_state = body.garment_state
    db.commit()
    db.refresh(order)
    return order


@api_router.get("/occupancy/{rail_id}", response_model=OccupancyOut)
def occupancy(rail_id: int, db: Session = Depends(get_db)):
    rail = db.get(HangRail, rail_id)
    if not rail:
        raise HTTPException(404, "挂杆不存在")
    placements = db.scalars(
        select(RailPlacement).where(RailPlacement.rail_id == rail_id, RailPlacement.active == 1)
    ).all()
    segs = []
    states: set[str] = set()
    for p in placements:
        order = db.get(WorkOrder, p.order_id)
        if not order:
            continue
        state = normalize_state(order.garment_state)
        states.add(state)
        segs.append(
            OccupancySeg(
                order_id=order.id,
                ticket_code=order.ticket_code,
                garment_name=order.garment_name,
                garment_state=state,
                start_cm=p.start_cm,
                end_cm=p.end_cm,
            )
        )
    segs.sort(key=lambda s: s.start_cm)
    return OccupancyOut(
        rail_id=rail.id,
        label=rail.label,
        length_cm=rail.length_cm,
        states=sorted(states),
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

    want_state = normalize_state(order.garment_state)
    state_cn = {"dry": "干衣", "wet": "湿衣"}
    # Rails rejected specifically by wet/dry isolation vs. plain lack of space.
    isolation_blocks: list[str] = []
    space_blocks: list[str] = []

    for rail in rails:
        active = db.scalars(
            select(RailPlacement).where(RailPlacement.rail_id == rail.id, RailPlacement.active == 1)
        ).all()
        occupied: list[Segment] = []
        occupant_states: list[str] = []
        for p in active:
            occupied.append(Segment(p.start_cm, p.end_cm))
            occ_order = db.get(WorkOrder, p.order_id)
            if occ_order:
                occupant_states.append(normalize_state(occ_order.garment_state))
        if any(not states_compatible(want_state, s) for s in occupant_states):
            other = next(s for s in occupant_states if s != want_state)
            isolation_blocks.append(f"{rail.label}（已挂{state_cn[other]}）")
            continue
        place = first_fit(rail.length_cm, occupied, order.length_cm)
        if place is None:
            space_blocks.append(rail.label)
            continue
        db.add(
            RailPlacement(
                rail_id=rail.id,
                order_id=order.id,
                start_cm=place.start_cm,
                end_cm=place.end_cm,
            )
        )
        order.status = "hung"
        order.hung_at = datetime.utcnow()
        db.commit()
        db.refresh(order)
        return order

    detail_parts = []
    if isolation_blocks:
        detail_parts.append(
            f"干湿隔离冲突：{state_cn[want_state]}不得与{'湿衣' if want_state == 'dry' else '干衣'}同杆 → "
            f"{'、'.join(isolation_blocks)}"
        )
    if space_blocks:
        detail_parts.append(f"空间不足：{'、'.join(space_blocks)}")
    raise HTTPException(
        409,
        {
            "code": "isolation_conflict" if isolation_blocks else "no_space",
            "message": "；".join(detail_parts) or "挂杆空间不足",
            "isolation_rails": isolation_blocks,
            "space_rails": space_blocks,
        },
    )


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
