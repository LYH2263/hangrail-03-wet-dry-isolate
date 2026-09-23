from datetime import datetime
from pydantic import BaseModel, field_validator


class StoreOut(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}


class RailOut(BaseModel):
    id: int
    store_id: int
    label: str
    length_cm: float
    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: int
    store_id: int
    ticket_code: str
    garment_name: str
    length_cm: float
    dry_state: str | None  # dry / wet / None（历史工单，按干衣兼容）
    status: str
    due_at: datetime
    hung_at: datetime | None
    model_config = {"from_attributes": True}


class OrderStateRequest(BaseModel):
    dry_state: str | None = None  # 传 dry / wet；传 null 回退为历史兼容

    @field_validator("dry_state")
    @classmethod
    def _check(cls, v):
        if v not in (None, "dry", "wet"):
            raise ValueError("dry_state 仅支持 dry / wet / null")
        return v


class HangRequest(BaseModel):
    order_id: int
    rail_id: int | None = None


class PickupRequest(BaseModel):
    ticket_code: str


class OccupancySeg(BaseModel):
    order_id: int
    ticket_code: str
    garment_name: str
    dry_state: str | None
    start_cm: float
    end_cm: float


class OccupancyOut(BaseModel):
    rail_id: int
    label: str
    length_cm: float
    # 该杆当前干湿集合：dry / wet / None（空杆或未标注）
    rail_dry_state: str | None
    segments: list[OccupancySeg]
