"""1D First-Fit placement by garment length on a hang rail.

Wet/dry isolation: a rail already holding garments of one state (wet or dry)
must not accept a new garment with the opposite state, even when its free
gaps are long enough. Garments of the same state keep plain First-Fit.
"""

from __future__ import annotations

from dataclasses import dataclass

# Canonical garment states. ``None`` / "" on legacy orders means "dry".
DRY = "dry"
WET = "wet"
STATES = (DRY, WET)


def normalize_state(state: str | None) -> str:
    """Unlabeled historical orders are treated as dry-clean compatible."""
    return WET if state == WET else DRY


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


def states_compatible(a: str | None, b: str | None) -> bool:
    """Wet and dry garments may never share a rail; unlabeled counts as dry."""
    return normalize_state(a) == normalize_state(b)


def first_fit_isolated(
    rail_length: float,
    occupied: list[Segment],
    garment_cm: float,
    garment_state: str | None,
    occupant_states: list[str | None],
) -> Placement | None:
    """First-Fit with wet/dry isolation.

    Returns ``None`` both when the rail holds the opposite state and when no
    gap fits; callers compare ``states_compatible`` to tell the two apart.
    """
    for s in occupant_states:
        if not states_compatible(garment_state, s):
            return None
    return first_fit(rail_length, occupied, garment_cm)


def overlaps(a: Segment, b: Segment) -> bool:
    return not (a.end_cm <= b.start_cm or b.end_cm <= a.start_cm)
