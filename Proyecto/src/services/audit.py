from collections import deque

from services.associations import _valid_events


def _ordered_keys(root):
    result = []

    def traverse(node):
        if node is None:
            return
        traverse(node.left)
        result.append((node.event.calculate_key(), node.event.event_id))
        traverse(node.right)

    traverse(root)
    return result


def _recalculated_heights(root):

    def traverse(node):
        if node is None:
            return -1, {}
        left_height, left_metadata = traverse(node.left)
        right_height, right_metadata = traverse(node.right)
        height = 1 + max(left_height, right_height)
        factor = left_height - right_height
        metadata = {}
        metadata.update(left_metadata)
        metadata.update(right_metadata)
        metadata[node.event.event_id] = (height, factor)
        return height, metadata

    _, metadata = traverse(root)
    return metadata


def verify_structure(system):
    errors = []

    # === 1. Global BST order ===
    keys = _ordered_keys(system.avl.root)
    for i in range(1, len(keys)):
        if keys[i][0] <= keys[i - 1][0]:
            errors.append(
                f"Broken BST order: key {keys[i][0]} "
                f"(event {keys[i][1]}) is not greater than "
                f"key {keys[i - 1][0]} (event {keys[i - 1][1]})"
            )

    # === 2. Identifier uniqueness ===
    active_ids = set(system._active_events.keys())
    historical_ids = set(system._historical_events.keys())
    removed_ids = set(system.removed_ids)

    duplicated_active = set()
    if len(active_ids) != len(system._active_events):
        duplicated_active = {"(duplicate keys in dictionary)"}

    duplicates_across = (
        (active_ids & historical_ids)
        | (active_ids & removed_ids)
        | (historical_ids & removed_ids)
    )
    if duplicates_across:
        errors.append(
            f"Identifiers in more than one state: "
            f"{sorted(duplicates_across)}"
        )

    # === 3. AVL ↔ active dictionary correspondence ===
    ids_in_tree = {key[1] for key in keys}
    if ids_in_tree != active_ids:
        missing_in_tree = active_ids - ids_in_tree
        extra_in_tree = ids_in_tree - active_ids
        if missing_in_tree:
            errors.append(
                f"Active events outside the AVL: {sorted(missing_in_tree)}"
            )
        if extra_in_tree:
            errors.append(
                f"Nodes in the AVL without active event: {sorted(extra_in_tree)}"
            )

    # === 4. Event key matches its position ===
    for key, event_id in keys:
        event = system._active_events.get(event_id)
        if event is None:
            continue
        if event.calculate_key() != key:
            errors.append(
                f"Inconsistent key in event {event_id}: "
                f"node={key}, calculated={event.calculate_key()}"
            )

    # === 5. Heights and factors ===
    metadata = _recalculated_heights(system.avl.root)

    def check_metadata(node, depth):
        if node is None:
            return
        eid = node.event.event_id
        expected_height, expected_factor = metadata.get(eid, (-1, 0))
        if node.height != expected_height:
            errors.append(
                f"Incorrect height in event {eid}: "
                f"stored={node.height}, expected={expected_height}"
            )
        if node.balance_factor != expected_factor:
            errors.append(
                f"Incorrect factor in event {eid}: "
                f"stored={node.balance_factor}, "
                f"expected={expected_factor}"
            )
        if not system.avl.stress_mode and abs(expected_factor) > 1:
            errors.append(
                f"Unexpected imbalance in normal mode: "
                f"event {eid}, factor={expected_factor}"
            )
        check_metadata(node.left, depth + 1)
        check_metadata(node.right, depth + 1)

    check_metadata(system.avl.root, 0)

    # === 6. Associations ===
    all_events = {
        **system._active_events,
        **system._historical_events
    }
    for eid, event in all_events.items():
        if event.reference is not None:
            if event.reference == eid:
                errors.append(
                    f"Event {eid} references itself"
                )
            elif event.reference in system.removed_ids:
                errors.append(
                    f"Event {eid} references the removed "
                    f"{event.reference}"
                )
            elif event.reference not in all_events:
                errors.append(
                    f"Event {eid} references a non-existent event "
                    f"{event.reference}"
                )
            else:
                reference = all_events[event.reference]
                if eid not in reference.referenced_by:
                    errors.append(
                        f"Non-reciprocal reference: {eid} -> "
                        f"{event.reference}"
                    )
        for referenced in event.referenced_by:
            if referenced in system.removed_ids:
                errors.append(
                    f"Event {eid} is referenced by the removed "
                    f"{referenced}"
                )
            elif referenced not in all_events:
                errors.append(
                    f"Event {eid} referenced by non-existent "
                    f"{referenced}"
                )
            else:
                other = all_events[referenced]
                if other.reference != eid:
                    errors.append(
                        f"Non-reciprocal association: {referenced} -> "
                        f"{eid}"
                    )

    # === 7. Expensive access flags ===
    def check_access(node, depth):
        if node is None:
            return
        expected = (
            node.event.priority == 3
            and depth > system.parameters.l
        )
        if node.event.expensive_access != expected:
            errors.append(
                f"Inconsistent expensive access flag in event "
                f"{node.event.event_id}: stored="
                f"{node.event.expensive_access}, expected={expected} "
                f"(depth={depth}, L={system.parameters.l})"
            )
        check_access(node.left, depth + 1)
        check_access(node.right, depth + 1)

    check_access(system.avl.root, 0)

    # === Indicators ===
    by_priority = {1: 0, 2: 0, 3: 0}
    pending = 0
    for event in system._active_events.values():
        by_priority[event.priority] = (
            by_priority.get(event.priority, 0) + 1
        )
        if event.state == "pending":
            pending += 1

    with_expensive_access = sum(
        1
        for event in system._active_events.values()
        if event.expensive_access
    )

    indicators = {
        "active": len(system._active_events),
        "historical": len(system._historical_events),
        "removed": len(system.removed_ids),
        "height": system.avl.height(),
        "leaves": system.avl.number_of_leaves(),
        "nodes_per_level": system.avl.nodes_per_level(),
        "in_order": [e.event_id for e in system.avl.in_order()],
        "pre_order": [e.event_id for e in system.avl.pre_order()],
        "post_order": [e.event_id for e in system.avl.post_order()],
        "breadth_first": [e.event_id for e in system.avl.breadth_first()],
        "accepted_corrections": system.metrics["accepted_corrections"],
        "discarded_reports": system.metrics["discarded_reports"],
        "conflicts": system.metrics["conflicts"],
        "confirmations": system.metrics["confirmations"],
        "created_by_report": system.metrics["created_by_report"],
        "reactivated": system.metrics["reactivated"],
        "massive_archives": system.metrics["massive_archives"],
        "archived_events": system.metrics["archived_events"],
        "ll_cases": system.avl.ll_cases,
        "rr_cases": system.avl.rr_cases,
        "lr_cases": system.avl.lr_cases,
        "rl_cases": system.avl.rl_cases,
        "single_left_rotations": system.avl.single_left_rotations,
        "single_right_rotations": system.avl.single_right_rotations,
        "rotations_performed": system.avl.rotations_performed,
        "by_priority": by_priority,
        "pending": pending,
        "with_expensive_access": with_expensive_access,
        "stress_mode": system.avl.stress_mode,
    }

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "indicators": indicators,
    }