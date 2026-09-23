from app.services.rail_engine import (
    DRY,
    WET,
    IsolationConflict,
    Segment,
    effective_state,
    first_fit,
    free_gaps,
    rail_state,
    try_fit,
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


# —— 干湿隔离 ——

def test_wet_rejected_on_dry_rail_even_with_room():
    """异属性同杆被拒：A 杆已挂干衣且空隙充足，湿衣仍不得上杆。"""
    occ = [Segment(0, 45)]  # 200cm 杆，剩余 155cm，远超 50cm 衣长
    result = try_fit(200, occ, 50, WET, [DRY])
    assert isinstance(result, IsolationConflict)
    assert result.rail_state == DRY


def test_dry_rejected_on_wet_rail_even_with_room():
    occ = [Segment(0, 40)]
    result = try_fit(160, occ, 30, DRY, [WET])
    assert isinstance(result, IsolationConflict)
    assert result.rail_state == WET


def test_same_state_continues_first_fit():
    """同属性可继续 First-Fit：湿衣上湿衣杆，取最左空隙。"""
    occ = [Segment(0, 40)]
    result = try_fit(160, occ, 50, WET, [WET])
    assert result is not None
    assert not isinstance(result, IsolationConflict)
    assert result.start_cm == 40
    assert result.end_cm == 90


def test_dry_garment_continues_first_fit_on_dry_rail():
    occ = [Segment(0, 45), Segment(45, 80)]
    result = try_fit(200, occ, 30, DRY, [DRY, DRY])
    assert result is not None
    assert not isinstance(result, IsolationConflict)
    assert result.start_cm == 80


def test_empty_rail_accepts_either_state():
    assert try_fit(200, [], 50, WET, []) is not None
    assert try_fit(200, [], 50, DRY, []) is not None


def test_unlabeled_history_counts_as_dry():
    """未标注属性的历史工单按干衣兼容。"""
    assert effective_state(None) == DRY
    # 杆上只有历史工单（None）：干衣可挂，湿衣被隔离
    occ = [Segment(0, 45)]
    dry_result = try_fit(200, occ, 30, None, [None])
    assert dry_result is not None
    assert not isinstance(dry_result, IsolationConflict)
    wet_result = try_fit(200, occ, 30, WET, [None])
    assert isinstance(wet_result, IsolationConflict)
    assert wet_result.rail_state == DRY
    assert rail_state([None]) == DRY


def test_isolation_conflict_takes_precedence_over_space():
    """异属性时即使空间也不足，仍报隔离冲突而非空间不足。"""
    occ = [Segment(0, 190)]
    result = try_fit(200, occ, 50, WET, [DRY])
    assert isinstance(result, IsolationConflict)


def test_same_state_but_no_space_returns_none():
    """同属性但空隙不够：普通空间不足，不是隔离。"""
    occ = [Segment(0, 180)]
    assert try_fit(200, occ, 50, WET, [WET]) is None
