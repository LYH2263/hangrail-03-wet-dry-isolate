from app.services.rail_engine import (
    Segment,
    first_fit,
    first_fit_isolated,
    free_gaps,
    normalize_state,
    states_compatible,
)


def test_first_fit_leftmost():
    occ = [Segment(20, 40)]
    p = first_fit(100, occ, 15)
    assert p is not None
    assert p.start_cm == 0
    assert p.end_cm == 15


def test_first_fit_skips_too_small_gap():
    occ = [Segment(0, 10), Segment(18, 50)]
    p = first_fit(100, occ, 10)
    assert p is not None
    assert p.start_cm == 50


def test_no_space():
    occ = [Segment(0, 80)]
    assert first_fit(100, occ, 25) is None


def test_free_gaps_edges():
    gaps = free_gaps(50, [Segment(10, 20), Segment(30, 35)])
    assert gaps == [Segment(0, 10), Segment(20, 30), Segment(35, 50)]


def test_legacy_unlabeled_state_normalizes_to_dry():
    assert normalize_state(None) == "dry"
    assert normalize_state("") == "dry"
    assert normalize_state("dry") == "dry"
    assert normalize_state("wet") == "wet"


def test_states_compatible():
    assert states_compatible("dry", "dry")
    assert states_compatible("wet", "wet")
    assert states_compatible(None, "dry")  # historical order = dry-compatible
    assert not states_compatible("dry", "wet")
    assert not states_compatible(None, "wet")


def test_isolated_blocks_opposite_state_even_with_room():
    # 40cm occupied, 60cm free — geometrically it fits, isolation says no.
    occ = [Segment(0, 40)]
    assert first_fit_isolated(100, occ, 30, "wet", ["dry"]) is None
    assert first_fit_isolated(100, occ, 30, "dry", ["wet"]) is None
    assert first_fit_isolated(100, occ, 30, None, ["wet"]) is None


def test_isolated_same_state_keeps_first_fit():
    occ = [Segment(0, 40)]
    p = first_fit_isolated(100, occ, 30, "dry", ["dry"])
    assert p is not None
    assert (p.start_cm, p.end_cm) == (40, 70)
    p = first_fit_isolated(100, occ, 30, "wet", ["wet"])
    assert p is not None
    assert (p.start_cm, p.end_cm) == (40, 70)
    # Unlabeled legacy garment behaves as dry on a dry rail.
    p = first_fit_isolated(100, occ, 30, None, [None])
    assert p is not None
    assert (p.start_cm, p.end_cm) == (40, 70)


def test_isolated_empty_rail_accepts_either_state():
    assert first_fit_isolated(100, [], 30, "wet", []) is not None
    assert first_fit_isolated(100, [], 30, "dry", []) is not None
