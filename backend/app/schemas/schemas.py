from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

GarmentState = Literal["dry", "wet"]


def _as_state(v: str | None) -> str:
    # Unlabeled historical orders are dry-clean compatible.
    return "wet" if v == "wet" else "dry"


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
    # Always emitted normalized; legacy NULL rows surface as "dry".
    garment_state: GarmentState = "dry"
    status: str
    due_at: datetime
    hung_at: datetime | None = None

    @field_validator("garment_state", mode="before")
    @classmethod
    def _normalize_state(cls, v):
        return _as_state(v)

    model_config = {"from_attributes": True}


class OrderUpdate(BaseModel):
    garment_state: GarmentState


class HangRequest(BaseModel):
    order_id: int
    rail_id: int | None = None


class PickupRequest(BaseModel):
    ticket_code: str


class OccupancySeg(BaseModel):
    order_id: int
    ticket_code: str
    garment_name: str
    garment_state: GarmentState = "dry"
    start_cm: float
    end_cm: float

    @field_validator("garment_state", mode="before")
    @classmethod
    def _normalize_state(cls, v):
        return _as_state(v)


class OccupancyOut(BaseModel):
    rail_id: int
    label: str
    length_cm: float
    # Deduped wet/dry set currently hanging on the rail; empty on a free rail.
    states: list[GarmentState] = []
    segments: list[OccupancySeg]
