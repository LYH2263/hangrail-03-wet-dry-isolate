from datetime import datetime, timedelta

from app.models.models import HangRail, RailPlacement, Store, WorkOrder


def _store(db, name="测试门店"):
    s = Store(name=name)
    db.add(s)
    db.flush()
    return s


def _rail(db, store, label, length=200):
    r = HangRail(store_id=store.id, label=label, length_cm=length)
    db.add(r)
    db.flush()
    return r


def _order(db, store, code, length, state, status="ready", hung=False):
    now = datetime.utcnow()
    o = WorkOrder(
        store_id=store.id,
        ticket_code=code,
        garment_name=code,
        length_cm=length,
        garment_state=state,
        status=status,
        due_at=now + timedelta(days=1),
        hung_at=now - timedelta(hours=1) if hung else None,
    )
    db.add(o)
    db.flush()
    return o


def _place(db, rail, order, start, end):
    db.add(
        RailPlacement(
            rail_id=rail.id, order_id=order.id, start_cm=start, end_cm=end, active=1
        )
    )
    db.flush()


def test_wet_rejected_from_dry_rail_and_scans_to_empty_rail(client, db):
    """异属性同杆被拒 → 自动改扫其它杆。"""
    store = _store(db)
    a = _rail(db, store, "A 杆")
    b = _rail(db, store, "B 杆")
    # A 杆 holds one dry garment with 160cm of room — plenty for the wet one.
    dry_coat = _order(db, store, "D-1", 40, "dry", status="hung", hung=True)
    _place(db, a, dry_coat, 0, 40)
    wet = _order(db, store, "W-1", 50, "wet")
    db.commit()

    r = client.post("/api/hang", json={"order_id": wet.id})
    assert r.status_code == 200, r.text
    # It must NOT share A 杆 with the dry coat; it lands on empty B 杆.
    assert r.json()["status"] == "hung"
    occ = client.get(f"/api/occupancy/{a.id}").json()
    assert {s["ticket_code"] for s in occ["segments"]} == {"D-1"}
    assert occ["states"] == ["dry"]
    occ_b = client.get(f"/api/occupancy/{b.id}").json()
    assert {s["ticket_code"] for s in occ_b["segments"]} == {"W-1"}
    assert occ_b["states"] == ["wet"]


def test_explicit_rail_conflict_reports_isolation_not_space(client, db):
    """指定杆冲突时，错误必须能看出是隔离冲突而非空间不足。"""
    store = _store(db)
    a = _rail(db, store, "A 杆")
    _rail(db, store, "B 杆")
    dry_coat = _order(db, store, "D-1", 40, "dry", status="hung", hung=True)
    _place(db, a, dry_coat, 0, 40)
    wet = _order(db, store, "W-1", 50, "wet")
    db.commit()

    r = client.post("/api/hang", json={"order_id": wet.id, "rail_id": a.id})
    assert r.status_code == 409
    body = r.json()["detail"]
    assert body["code"] == "isolation_conflict"
    assert "干湿隔离" in body["message"]
    assert "A 杆" in body["message"]
    # No placement was written anywhere.
    assert client.get(f"/api/occupancy/{a.id}").json()["states"] == ["dry"]


def test_dry_rejected_from_wet_rail_even_when_gap_fits(client, db):
    store = _store(db)
    a = _rail(db, store, "A 杆")
    wet_coat = _order(db, store, "W-9", 40, "wet", status="hung", hung=True)
    _place(db, a, wet_coat, 0, 40)
    dry = _order(db, store, "D-9", 30, "dry")
    db.commit()

    r = client.post("/api/hang", json={"order_id": dry.id, "rail_id": a.id})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "isolation_conflict"
    assert client.get(f"/api/occupancy/{a.id}").json()["states"] == ["wet"]


def test_same_state_continues_first_fit(client, db):
    """同属性衣物仍按 First-Fit 填补 A 杆空隙，不跳杆。"""
    store = _store(db)
    a = _rail(db, store, "A 杆")
    b = _rail(db, store, "B 杆")
    d1 = _order(db, store, "D-1", 40, "dry", status="hung", hung=True)
    d2 = _order(db, store, "D-2", 30, "dry", status="hung", hung=True)
    _place(db, a, d1, 0, 40)
    _place(db, a, d2, 60, 90)  # 20cm gap before it, 110cm after
    d3 = _order(db, store, "D-3", 30, "dry")
    db.commit()

    r = client.post("/api/hang", json={"order_id": d3.id})
    assert r.status_code == 200, r.text
    occ = client.get(f"/api/occupancy/{a.id}").json()
    seg = next(s for s in occ["segments"] if s["ticket_code"] == "D-3")
    # First-Fit: first fitting gap starts at 90 (the 20cm gap is too small).
    assert seg["start_cm"] == 90
    assert seg["end_cm"] == 120
    assert occ["states"] == ["dry"]
    # B 杆 stays untouched.
    assert client.get(f"/api/occupancy/{b.id}").json()["segments"] == []


def test_wet_then_wet_share_rail_first_fit(client, db):
    store = _store(db)
    a = _rail(db, store, "A 杆")
    w1 = _order(db, store, "W-1", 40, "wet", status="hung", hung=True)
    _place(db, a, w1, 0, 40)
    w2 = _order(db, store, "W-2", 30, "wet")
    db.commit()

    r = client.post("/api/hang", json={"order_id": w2.id})
    assert r.status_code == 200
    occ = client.get(f"/api/occupancy/{a.id}").json()
    assert occ["states"] == ["wet"]
    seg = next(s for s in occ["segments"] if s["ticket_code"] == "W-2")
    assert (seg["start_cm"], seg["end_cm"]) == (40, 70)


def test_legacy_unlabeled_order_treated_as_dry(client, db):
    """未标注属性的历史工单按干衣兼容。"""
    store = _store(db)
    a = _rail(db, store, "A 杆")
    d1 = _order(db, store, "D-1", 40, "dry", status="hung", hung=True)
    _place(db, a, d1, 0, 40)
    # Legacy row: garment_state explicitly NULL in the database.
    legacy = _order(db, store, "OLD-1", 30, None)
    db.commit()

    r = client.post("/api/hang", json={"order_id": legacy.id})
    assert r.status_code == 200
    # Serialized as dry, shares A 杆 via First-Fit.
    assert r.json()["garment_state"] == "dry"
    occ = client.get(f"/api/occupancy/{a.id}").json()
    assert occ["states"] == ["dry"]
    seg = next(s for s in occ["segments"] if s["ticket_code"] == "OLD-1")
    assert (seg["start_cm"], seg["end_cm"]) == (40, 70)


def test_pure_space_failure_still_reports_no_space(client, db):
    store = _store(db)
    a = _rail(db, store, "A 杆", length=50)
    d1 = _order(db, store, "D-1", 40, "dry", status="hung", hung=True)
    _place(db, a, d1, 0, 40)
    d2 = _order(db, store, "D-2", 30, "dry")  # same state, only 10cm free
    db.commit()

    r = client.post("/api/hang", json={"order_id": d2.id, "rail_id": a.id})
    assert r.status_code == 409
    body = r.json()["detail"]
    assert body["code"] == "no_space"
    assert "干湿隔离" not in body["message"]


def test_seed_dry_a_rail_rejects_wet_down_jacket(client, db):
    """种子场景：A 杆已挂干衣，湿衣羽绒服不得再上 A 杆。"""
    from app.services.seed import seed_if_empty

    seed_if_empty(db)
    orders = {o.ticket_code: o for o in db.query(WorkOrder).all()}
    rails = {r.label: r for r in db.query(HangRail).all()}

    r = client.post("/api/hang", json={"order_id": orders["HR-2003"].id, "rail_id": rails["A 杆"].id})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "isolation_conflict"

    # Unspecified rail: auto-scan skips A and the wet jacket lands on B.
    r2 = client.post("/api/hang", json={"order_id": orders["HR-2003"].id})
    assert r2.status_code == 200
    occ_a = client.get(f"/api/occupancy/{rails['A 杆'].id}").json()
    occ_b = client.get(f"/api/occupancy/{rails['B 杆'].id}").json()
    assert occ_a["states"] == ["dry"]
    assert "HR-2003" not in {s["ticket_code"] for s in occ_a["segments"]}
    assert occ_b["states"] == ["wet"]
    assert {s["ticket_code"] for s in occ_b["segments"]} == {"HR-2003"}


def test_patch_order_state_and_hang(client, db):
    store = _store(db)
    a = _rail(db, store, "A 杆")
    d1 = _order(db, store, "D-1", 40, "dry", status="hung", hung=True)
    _place(db, a, d1, 0, 40)
    w = _order(db, store, "W-1", 50, "wet")
    db.commit()

    # Flip wet → dry before hanging: now it shares A 杆.
    r = client.patch(f"/api/orders/{w.id}", json={"garment_state": "dry"})
    assert r.status_code == 200
    assert r.json()["garment_state"] == "dry"

    r = client.post("/api/hang", json={"order_id": w.id})
    assert r.status_code == 200
    assert client.get(f"/api/occupancy/{a.id}").json()["states"] == ["dry"]

    # Hanging orders are locked against state edits.
    assert client.patch(f"/api/orders/{d1.id}", json={"garment_state": "wet"}).status_code == 400
