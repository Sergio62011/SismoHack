# Módulo main: contiene la lógica relacionada con main.
"""
SismoLab AVL - Demo and integration tests.

Covers the sections of the specification that are already implemented:
- Map and zones (section 3)
- Priority calculation (section 4)
- Key and comparison (section 5)
- Create, query, correct, remove (section 6)
- FIFO report queue (section 8)
- Rotations and recovery (section 8)
- BST vs AVL comparison (section 12, partial)
"""

from datetime import datetime, timezone

from structure.avl import AVL
from structure.bst import BST
from models.event import Event
from models.map import SeismicMap, Zone
from models.report import Report
from services.seismic_system import SeismicSystem


# =========================================================
# UTILITIES
# =========================================================

# Gestiona title.
def title(text):
    print("\n" + "=" * 65)
    print(text)
    print("=" * 65)


# Gestiona subtitle.
def subtitle(text):
    print("\n--- " + text + " ---")


# Gestiona utc.
def utc(y, mo, d, h=0, mi=0, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)


# Gestiona ev.
def ev(event_id, magnitude=5.0, depth=50.0,
       x=100.0, y=100.0, populated=False, hour=10):
    return Event(
        event_id=event_id,
        magnitude=magnitude,
        depth=depth,
        x=x,
        y=y,
        datetime=utc(2026, 9, 7, hour, 0, 0),
        populated_zone=populated,
    )


# Gestiona show event.
def show_event(event):
    if event is None:
        print("  (no event)")
        return
    print(
        f"  ID={event.event_id} "
        f"M={event.magnitude} H={event.depth} "
        f"P={event.priority} "
        f"key={event.calculate_key()} "
        f"state={event.state} "
        f"location={event.location} "
        f"rev={event.revision}"
    )


# =========================================================
# 1. MAP AND ZONES
# =========================================================

# Gestiona demo map and zones.
def demo_map_and_zones():
    title("1. MAP AND ZONES (section 3)")

    smap = SeismicMap(rows=10, columns=10)
    smap.add_zone(Zone("North City", 100, 600, 450, 900, True))
    smap.add_zone(Zone("South Reserve", 550, 100, 900, 350, False))
    smap.add_zone(Zone("Central City", 250, 250, 550, 550, True))

    cases = [
        (300.0, 700.0, "inside North City"),
        (700.0, 200.0, "inside South Reserve"),
        (500.0, 500.0, "border of Central City"),
        (100.0, 600.0, "border of North City"),
        (250.0, 250.0, "corner border of Central City"),
        (0.0, 0.0, "outside every zone"),
        (450.0, 900.0, "top border of North City"),
        (450.0, 600.0, "border between North City and Central City"),
    ]

    for x, y, desc in cases:
        pop = smap.is_in_populated_zone(x, y)
        print(f"  ({x}, {y}) -> populated_zone={pop}  [{desc}]")

    subtitle("Map matrix with events")
    events = [
        ev(101, 4.7, 20.0, 300.0, 700.0),
        ev(102, 5.1, 40.0, 700.0, 200.0),
        ev(103, 6.2, 15.0, 500.0, 500.0),
    ]
    for e in events:
        smap.assign_zone_to_event(e)
        print(
            f"  Event {e.event_id}: populated={e.in_populated_zone} "
            f"P={e.priority} key={e.calculate_key()}"
        )

    matrix = smap.matrix_with_events(events)
    smap.print_matrix(matrix)


# =========================================================
# 2. PRIORITY AND KEY
# =========================================================

# Gestiona demo priority and key.
def demo_priority_and_key():
    title("2. PRIORITY AND KEY (sections 4 and 5)")

    subtitle("Exact boundaries")
    cases = [
        (6.0, 100.0, False, 3, "M=6.0 exact"),
        (5.9, 100.0, False, 2, "M=5.9, not high"),
        (4.5, 30.0, True, 3, "M=4.5, H=30, populated -> 3"),
        (4.5, 30.0, False, 2, "M=4.5, H=30, not populated -> 2"),
        (4.5, 30.1, True, 2, "M=4.5, H=30.1, populated -> 2"),
        (4.5, 70.0, True, 2, "M=4.5, H=70, populated -> 2"),
        (4.4, 10.0, True, 1, "M=4.4 -> 1"),
        (-2.0, 0.0, False, 1, "M=-2.0 -> 1"),
        (10.0, 700.0, False, 3, "M=10.0 -> 3"),
    ]

    for m, h, pop, expected, desc in cases:
        e = ev(1, m, h, populated=pop)
        ok = "OK" if e.priority == expected else "FAIL"
        print(
            f"  [{ok}] {desc}: P={e.priority} (expected {expected})"
        )

    subtitle("Lexicographic comparison (example from the PDF)")
    root = ev(10, 5.2, 40.0)
    root.priority = 3
    root.magnitude = 5.2

    incoming = [
        (ev(20, 5.8, 40.0), "left", "(2, 5.8, 20) < (3, 5.2, 10)"),
        (ev(30, 6.1, 40.0), "right", "(3, 6.1, 30) > (3, 5.2, 10)"),
        (ev(5, 5.2, 40.0), "left", "(3, 5.2, 5) < (3, 5.2, 10)"),
        (ev(25, 5.2, 40.0), "right", "(3, 5.2, 25) > (3, 5.2, 10)"),
    ]

    for e, expected, reason in incoming:
        e.priority = 2 if "2," in reason else 3
        e.magnitude = float(reason.split(",")[1].strip())
        actual = "left" if e < root else "right"
        ok = "OK" if actual == expected else "FAIL"
        print(f"  [{ok}] {reason}: {actual}")


# =========================================================
# 3. AVL: ROTATIONS
# =========================================================

# Gestiona demo rotations.
def demo_rotations():
    title("3. AVL ROTATIONS (section 5)")

    cases = [
        ("LL", [30, 20, 10]),
        ("RR", [10, 20, 30]),
        ("LR", [30, 10, 20]),
        ("RL", [10, 30, 20]),
    ]

    for name, ids in cases:
        subtitle(f"Case {name}: insert {ids}")
        avl = AVL()
        for i in ids:
            avl.insert(ev(i))
        avl.draw(show_info=True)
        print(f"  Height: {avl.height()}")
        print(f"  Rotations registered: {avl.rotations_last_operation}")
        print(f"  In-order: {[e.event_id for e in avl.in_order()]}")
        print(f"  Is AVL valid? {avl._is_avl(avl.root)}")


# =========================================================
# 4. AVL: DELETION
# =========================================================

# Gestiona demo deletion.
def demo_deletion():
    title("4. AVL DELETION (sections 6 and 10)")

    subtitle("Delete root with two children")
    avl = AVL()
    for i in [20, 10, 30, 5, 15, 25, 35]:
        avl.insert(ev(i))

    print("  Before:")
    avl.draw(show_info=True)

    avl.delete((2, 5.0, 20))
    print("  After deleting the root (20):")
    avl.draw(show_info=True)
    print(f"  In-order: {[e.event_id for e in avl.in_order()]}")
    print(f"  Is AVL valid? {avl._is_avl(avl.root)}")

    subtitle("Delete leaf")
    avl.delete((2, 5.0, 5))
    print(f"  In-order: {[e.event_id for e in avl.in_order()]}")
    print(f"  Is AVL valid? {avl._is_avl(avl.root)}")

    subtitle("Delete node with one child")
    avl2 = AVL()
    for i in [20, 10, 30, 25]:
        avl2.insert(ev(i))
    avl2.delete((2, 5.0, 30))
    print(f"  In-order: {[e.event_id for e in avl2.in_order()]}")
    print(f"  Is AVL valid? {avl2._is_avl(avl2.root)}")


# =========================================================
# 5. STRESS MODE AND RECOVERY
# =========================================================

# Gestiona demo stress mode.
def demo_stress_mode():
    title("5. STRESS MODE AND GLOBAL RECOVERY (section 8)")

    avl = AVL()
    avl.enable_stress_mode()
    print(f"  Stress mode active: {avl.stress_mode}")

    for i in [10, 20, 30, 40, 50, 60, 70, 80]:
        avl.insert(ev(i))

    subtitle("Tree in stress mode (no rotations)")
    avl.draw(show_info=True)
    print(f"  Height: {avl.height()}")
    print(f"  Is AVL valid? {avl._is_avl(avl.root)}")

    subtitle("Global recovery")
    avl.recover_balance()
    avl.draw(show_info=True)
    print(f"  Height: {avl.height()}")
    print(f"  Is AVL valid? {avl._is_avl(avl.root)}")
    print(f"  In-order: {[e.event_id for e in avl.in_order()]}")

    subtitle("Imbalance greater than 2")
    avl2 = AVL()
    avl2.enable_stress_mode()
    for i in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
        avl2.insert(ev(i))
    print(f"  Height in stress: {avl2.height()}")
    root = avl2.root
    print(f"  Root balance factor: {root.balance_factor}")
    avl2.recover_balance()
    print(f"  Height after recovery: {avl2.height()}")
    print(f"  Is AVL valid? {avl2._is_avl(avl2.root)}")


# =========================================================
# 6. BST VS AVL COMPARISON
# =========================================================

# Gestiona demo bst vs avl.
def demo_bst_vs_avl():
    title("6. BST vs AVL COMPARISON (section 12)")

    ids = list(range(1, 16))

    bst = BST()
    avl = AVL()

    for i in ids:
        e1 = ev(i)
        e2 = ev(i)
        bst.insert(e1)
        avl.insert(e2)

    subtitle("BST")
    bst.draw()
    print(f"  BST height: {bst.height()}")
    print(f"  BST leaves: {bst.number_of_leaves()}")
    print(f"  BST nodes: {bst.size()}")

    subtitle("AVL")
    avl.draw(show_info=True)
    print(f"  AVL height: {avl.height()}")
    print(f"  AVL leaves: {avl.number_of_leaves()}")
    print(f"  AVL nodes: {avl.size()}")
    print(f"  Total rotations: {avl.rotations_performed}")

    subtitle("Comparison")
    print(f"  BST height = {bst.height()}, AVL height = {avl.height()}")
    print(
        f"  BST in-order == AVL in-order: "
        f"{[e.event_id for e in bst.in_order()] == [e.event_id for e in avl.in_order()]}"
    )


# =========================================================
# 7. SYSTEM: CREATE, QUERY, CORRECT, REMOVE
# =========================================================

# Gestiona demo system crud.
def demo_system_crud():
    title("7. CRUD IN THE SYSTEM (section 6)")

    system = SeismicSystem()
    date = utc(2026, 9, 7, 10, 0, 0)

    subtitle("Create events")
    system.create_event(10, 5.2, 40.0, 200.0, 300.0, date, "ST-01")
    system.create_event(20, 6.5, 15.0, 500.0, 500.0, date, "ST-01")
    system.create_event(30, 4.0, 60.0, 700.0, 200.0, date, "ST-02")

    for eid in [10, 20, 30]:
        show_event(system.find_by_id(eid))

    subtitle("Query active event")
    query = system.query_event(20)
    print(f"  State: {query['state']}")
    show_event(query["event"])

    subtitle("Correct event 10 (M 5.2 -> 6.2, H 40 -> 15)")
    system.correct_event(10, magnitude=6.2, depth=15.0)
    show_event(system.find_by_id(10))

    subtitle("Mark event 20 as reviewed")
    system.mark_reviewed(20)
    show_event(system.find_by_id(20))

    subtitle("Remove event 30")
    system.remove_event(30)
    print(f"  Query 30: {system.query_event(30)['state']}")

    subtitle("Try to reuse a removed ID")
    try:
        system.create_event(30, 5.0, 10.0, 100.0, 100.0, date, "ST-03")
        print("  ERROR: it should not allow reusing the ID")
    except ValueError as e:
        print(f"  OK: {e}")

    subtitle("Try to duplicate an active ID")
    try:
        system.create_event(10, 5.0, 10.0, 100.0, 100.0, date, "ST-04")
        print("  ERROR: it should not allow duplicating")
    except ValueError as e:
        print(f"  OK: {e}")


# =========================================================
# 8. FIFO REPORT QUEUE
# =========================================================

# Gestiona print report result.
def print_report_result(number, result):
    event = result["event"]
    eid = event.event_id if event is not None else "None"
    print(f"\n  Step {number}")
    print(f"    Decision: {result['decision']}")
    print(f"    Message:  {result['message']}")
    print(f"    Event:    {eid}")
    print(f"    Rotations: {result['rotations']}")
    if "report" in result:
        print(f"    Report: {result['report']}")
        print(f"    Remaining pending: {result['remaining_pending']}")


# Gestiona demo reports.
def demo_reports():
    title("8. FIFO REPORT QUEUE (sections 6 and 8)")

    system = SeismicSystem()
    date = utc(2026, 9, 7, 10, 0, 0)

    reports = [
        Report(10, 5.0, 40.0, 100.0, 100.0, date, 1, "ST-01"),
        Report(10, 5.0, 40.0, 100.0, 100.0, date, 1, "ST-02"),  # confirmation
        Report(10, 6.2, 15.0, 100.0, 100.0, date, 2, "ST-03"),  # correction
        Report(10, 6.5, 15.0, 100.0, 100.0, date, 2, "ST-04"),  # conflict
        Report(10, 5.0, 40.0, 100.0, 100.0, date, 1, "ST-05"),  # outdated
        Report(20, 6.0, 10.0, 200.0, 200.0, date, 1, "ST-06"),  # new
    ]

    for r in reports:
        system.enqueue_report(r)

    print(f"  Reports in queue: {system.pending_report_count()}")

    results = system.process_all()
    for i, res in enumerate(results, start=1):
        print_report_result(i, res)

    subtitle("Final state of event 10")
    e = system.find_by_id(10)
    show_event(e)
    print(f"    Stations: {sorted(e.stations)}")

    subtitle("Metrics")
    for k, v in system.metrics.items():
        print(f"    {k}: {v}")


# =========================================================
# 9. ARCHIVING AND REACTIVATION
# =========================================================

# Gestiona demo archive reactivation.
def demo_archive_reactivation():
    title("9. ARCHIVING AND REACTIVATION (section 6)")

    system = SeismicSystem()
    date = utc(2026, 9, 7, 10, 0, 0)

    # Create and archive manually for the demo
    system.create_event(70, 4.8, 40.0, 200.0, 200.0, date, "ST-01")
    event = system.find_by_id(70)

    system.avl.delete(event.calculate_key())
    del system._active_events[70]
    event.location = "archived"
    system._historical_events[70] = event

    print(f"  Event 70 archived: {system.query_event(70)['state']}")

    subtitle("Old report over an archived event")
    r1 = Report(70, 4.8, 40.0, 200.0, 200.0, date, 1, "ST-02")
    res1 = system.process_report(r1)
    print(f"  Decision: {res1['decision']}")
    print(f"  Message:  {res1['message']}")

    subtitle("Report with a higher revision over an archived event")
    r2 = Report(70, 6.1, 20.0, 200.0, 200.0, date, 2, "ST-03")
    res2 = system.process_report(r2)
    print(f"  Decision: {res2['decision']}")
    print(f"  Message:  {res2['message']}")
    show_event(system.find_by_id(70))
    print(f"  Query 70: {system.query_event(70)['state']}")


# =========================================================
# 10. VALIDATIONS
# =========================================================

# Gestiona demo validations.
def demo_validations():
    title("10. VALIDATIONS (sections 3 and 6)")

    system = SeismicSystem()
    date = utc(2026, 9, 7, 10, 0, 0)

    cases = [
        ("ID 0", dict(event_id=0, magnitude=5.0, depth=10.0,
                      x=100.0, y=100.0)),
        ("ID 1000000", dict(event_id=1000000, magnitude=5.0, depth=10.0,
                            x=100.0, y=100.0)),
        ("M = -2.5", dict(event_id=1, magnitude=-2.5, depth=10.0,
                          x=100.0, y=100.0)),
        ("M = 10.5", dict(event_id=1, magnitude=10.5, depth=10.0,
                          x=100.0, y=100.0)),
        ("H = -1", dict(event_id=1, magnitude=5.0, depth=-1.0,
                        x=100.0, y=100.0)),
        ("H = 701", dict(event_id=1, magnitude=5.0, depth=701.0,
                         x=100.0, y=100.0)),
        ("x = 1001", dict(event_id=1, magnitude=5.0, depth=10.0,
                          x=1001.0, y=100.0)),
        ("y = -1", dict(event_id=1, magnitude=5.0, depth=10.0,
                        x=100.0, y=-1.0)),
        ("M with two decimals", dict(event_id=1, magnitude=5.25,
                                     depth=10.0, x=100.0, y=100.0)),
    ]

    for desc, kwargs in cases:
        try:
            system.create_event(
                station="ST-01", datetime_value=date, **kwargs
            )
            print(f"  [FAIL] {desc}: it should have rejected")
        except ValueError as e:
            print(f"  [OK] {desc}: {e}")

    subtitle("Datetimes without timezone")
    from datetime import datetime as dt
    try:
        system.create_event(
            999, 5.0, 10.0, 100.0, 100.0,
            dt(2026, 9, 7, 10, 0, 0),  # without tzinfo
            "ST-01",
        )
        print("  [FAIL] it should reject a datetime without tz")
    except ValueError as e:
        print(f"  [OK] {e}")


# =========================================================
# MAIN ENTRY POINT
# =========================================================

if __name__ == "__main__":
    import sys

    if "--ui" in sys.argv:
        from ui.main_window import run_application
        sys.exit(run_application())

    demo_map_and_zones()
    demo_priority_and_key()
    demo_rotations()
    demo_deletion()
    demo_stress_mode()
    demo_bst_vs_avl()
    demo_system_crud()
    demo_reports()
    demo_archive_reactivation()
    demo_validations()

    title("END OF TESTS")