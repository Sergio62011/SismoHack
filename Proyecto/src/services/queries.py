def first_k_pending(system, k):
    if isinstance(k, bool) or not isinstance(k, int) or k <= 0:
        raise ValueError("k must be a positive integer")

    events = []
    nodes_examined = 0

    def traverse(node):
        nonlocal nodes_examined

        if node is None or len(events) >= k:
            return

        traverse(node.right)

        if len(events) >= k:
            return

        nodes_examined += 1

        if node.event.state == "pending":
            events.append(node.event)

        traverse(node.left)

    traverse(system.avl.root)

    return {
        "events": events,
        "nodes_examined": nodes_examined,
    }


def events_by_magnitude(system, magnitude_min, magnitude_max):
    if magnitude_min > magnitude_max:
        raise ValueError(
            "The minimum magnitude cannot be greater than the maximum"
        )

    events = []
    nodes_examined = 0

    def traverse(node):
        nonlocal nodes_examined

        if node is None:
            return

        traverse(node.left)

        nodes_examined += 1

        event = node.event

        if magnitude_min <= event.magnitude <= magnitude_max:
            events.append(event)

        traverse(node.right)

    traverse(system.avl.root)

    return {
        "events": events,
        "nodes_examined": nodes_examined,
    }


def events_by_depth_and_date(
    system,
    max_depth,
    start_date,
    end_date
):
    if start_date > end_date:
        raise ValueError(
            "The start date cannot be later than the end date"
        )

    events = []
    nodes_examined = 0

    def traverse(node):
        nonlocal nodes_examined

        if node is None:
            return

        traverse(node.left)

        nodes_examined += 1

        event = node.event

        if (
            event.depth <= max_depth
            and start_date <= event.datetime <= end_date
        ):
            events.append(event)

        traverse(node.right)

    traverse(system.avl.root)

    return {
        "events": events,
        "nodes_examined": nodes_examined,
    }


def event_associations(system, event_id):
    eid = system._validate_id(event_id)

    if eid in system._active_events:
        event = system._active_events[eid]
        state = "active"

    elif eid in system._historical_events:
        event = system._historical_events[eid]
        state = "archived"

    else:
        if eid in system.removed_ids:
            raise ValueError(
                f"Event {eid} was removed"
            )

        raise ValueError(
            f"Event {eid} does not exist"
        )

    from services.associations import get_candidates

    candidates = []

    for candidate in get_candidates(system, event):
        if candidate.event_id in system._active_events:
            candidate_state = "active"
        else:
            candidate_state = "archived"

        candidates.append({
            "event": candidate,
            "state": candidate_state,
        })

    reference = None

    if event.reference is not None:
        reference = (
            system._active_events.get(event.reference)
            or system._historical_events.get(event.reference)
        )

    referenced_by = []

    for referenced_id in sorted(event.referenced_by):
        other = (
            system._active_events.get(referenced_id)
            or system._historical_events.get(referenced_id)
        )

        if other is None:
            continue

        if referenced_id in system._active_events:
            other_state = "active"
        else:
            other_state = "archived"

        referenced_by.append({
            "event": other,
            "state": other_state,
        })

    return {
        "event": event,
        "state": state,
        "candidates": candidates,
        "reference": reference,
        "referenced_by": referenced_by,
        "nodes_examined": 0,
    }


def avl_metrics(system):
    return {
        "count": system.avl.size(),
        "height": system.avl.height(),
        "leaves": system.avl.number_of_leaves(),
        "nodes_per_level": system.avl.nodes_per_level(),
    }