"""1D First-Fit placement by garment length on a hang rail.

干湿隔离：同一根杆上只允许一种干湿属性。已挂衣物中只要存在相反属性，
即使空隙足够也不得上杆（返回 IsolationConflict），由上层改扫其它杆。
历史工单未标注属性（None）按干衣兼容。
"""

from __future__ import annotations

from dataclasses import dataclass

DRY = "dry"
WET = "wet"


@dataclass(frozen=True)
class Segment:
    start_cm: float
    end_cm: float  # exclusive

    @property
    def length(self) -> float:
        return self.end_cm - self.start_cm


@dataclass(frozen=True)
class Placement:
    start_cm: float
    end_cm: float


@dataclass(frozen=True)
class IsolationConflict:
    """杆上已存在相反干湿属性。"""

    rail_state: str  # 杆上当前属性：DRY / WET


# 试挂结果：Placement=成功；IsolationConflict=隔离冲突；None=空间不足
TryFitResult = Placement | IsolationConflict | None


def effective_state(state: str | None) -> str:
    """未标注（None）的历史工单按干衣兼容。"""
    return WET if state == WET else DRY


def rail_state(occupied_states: list[str | None]) -> str | None:
    """杆上当前干湿集合的属性；空杆返回 None。

    有占位即非空：历史工单 None 归一化为干衣，因此全 None 的杆是干衣杆。
    """
    if not occupied_states:
        return None
    states = {effective_state(s) for s in occupied_states}
    return next(iter(states))


def free_gaps(rail_length: float, occupied: list[Segment]) -> list[Segment]:
    occ = sorted(occupied, key=lambda s: s.start_cm)
    gaps: list[Segment] = []
    cursor = 0.0
    for seg in occ:
        if seg.start_cm > cursor:
            gaps.append(Segment(cursor, seg.start_cm))
        cursor = max(cursor, seg.end_cm)
    if cursor < rail_length:
        gaps.append(Segment(cursor, rail_length))
    return gaps


def first_fit(rail_length: float, occupied: list[Segment], garment_cm: float) -> Placement | None:
    if garment_cm <= 0 or garment_cm > rail_length:
        return None
    for gap in free_gaps(rail_length, occupied):
        if gap.length + 1e-9 >= garment_cm:
            return Placement(gap.start_cm, gap.start_cm + garment_cm)
    return None


def try_fit(
    rail_length: float,
    occupied: list[Segment],
    garment_cm: float,
    garment_state: str | None,
    occupied_states: list[str | None] | None = None,
) -> TryFitResult:
    """带干湿隔离的 First-Fit：先过隔离，再走现网 First-Fit。"""
    current = rail_state(occupied_states or [])
    if current is not None and current != effective_state(garment_state):
        return IsolationConflict(current)
    return first_fit(rail_length, occupied, garment_cm)


def overlaps(a: Segment, b: Segment) -> bool:
    return not (a.end_cm <= b.start_cm or b.end_cm <= a.start_cm)
