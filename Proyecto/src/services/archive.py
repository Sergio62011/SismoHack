# Módulo archive: contiene la lógica relacionada con archive.
from services.history import Action


# Gestiona is eligible.
def _is_eligible(event, system):
    if event.priority != 1:
        return False

    age = system.clock.age_in_hours(event.datetime)

    return age > system.parameters.t


# Gestiona find eligible branches.
def _find_eligible_branches(node, system, depth=0):
    if node is None:
        return [], True, 0

    left_branches, left_valid, left_count = (
        _find_eligible_branches(node.left, system, depth + 1)
    )

    right_branches, right_valid, right_count = (
        _find_eligible_branches(node.right, system, depth + 1)
    )

    node_valid = _is_eligible(node.event, system)

    count = 1 + left_count + right_count

    subtree_valid = (
        node_valid
        and left_valid
        and right_valid
    )

    branches = []
    branches.extend(left_branches)
    branches.extend(right_branches)

    if subtree_valid:
        branches.append({
            "root": node.event,
            "depth": depth,
            "count": count,
        })

    return branches, subtree_valid, count


# Gestiona select branch.
def _select_branch(branches):
    if not branches:
        return None

    return max(
        branches,
        key=lambda branch: (
            branch["count"],
            branch["depth"],
            branch["root"].event_id,
        )
    )


# Gestiona preview archive.
def preview_archive(system):
    branches, _, _ = _find_eligible_branches(
        system.avl.root,
        system
    )

    branch = _select_branch(branches)

    if branch is None:
        return {
            "eligible": False,
            "root": None,
            "depth": None,
            "count": 0,
            "ids": [],
            "events": [],
            "message": "No eligible branch to archive.",
        }

    ids = []
    events = []

    # Gestiona collect.
    def collect(node):
        if node is None:
            return

        if node.event.event_id in ids:
            return

        ids.append(node.event.event_id)
        events.append(node.event)

        collect(node.left)
        collect(node.right)

    # We need to locate the selected root.
    # Gestiona find.
    def find(node):
        if node is None:
            return None

        if node.event.event_id == branch["root"].event_id:
            return node

        result = find(node.left)

        if result is not None:
            return result

        return find(node.right)

    root = find(system.avl.root)
    collect(root)

    return {
        "eligible": True,
        "root": branch["root"],
        "depth": branch["depth"],
        "count": branch["count"],
        "ids": ids,
        "events": events,
        "message": (
            "Eligible branch selected by node count, "
            "root depth and root ID."
        ),
    }


# Gestiona archive branch.
def archive_branch(system):
    previous_state = system._snapshot()

    try:
        branches, _, _ = _find_eligible_branches(
            system.avl.root,
            system
        )

        branch = _select_branch(branches)

        if branch is None:
            return {
                "archived": False,
                "root": None,
                "ids": [],
                "count": 0,
                "message": "No eligible branch to archive.",
            }

        # Locate the selected root.
        root = None

        # Gestiona find.
        def find(node):
            if node is None:
                return None

            if node.event.event_id == branch["root"].event_id:
                return node

            result = find(node.left)

            if result is not None:
                return result

            return find(node.right)

        root = find(system.avl.root)

        # Fix the set before modifying the AVL.
        events = []

        # Gestiona collect.
        def collect(node):
            if node is None:
                return

            events.append(node.event)
            collect(node.left)
            collect(node.right)

        collect(root)

        ids = [event.event_id for event in events]

        # Now modify the scenario.
        for event in events:
            system.avl.delete(event.calculate_key())

            system._active_events.pop(
                event.event_id,
                None
            )

            event.location = "archived"

            system._historical_events[event.event_id] = event

        system.metrics["massive_archives"] += 1
        system.metrics["archived_events"] += len(events)
        system.update_expensive_access_flags()

        system.history.record_action(
            Action(
                f"archive_branch {branch['root'].event_id}",
                previous_state
            )
        )

        return {
            "archived": True,
            "root": branch["root"],
            "ids": ids,
            "count": len(events),
            "message": (
                f"Branch with root "
                f"{branch['root'].event_id} was archived."
            ),
        }

    except Exception:
        system._restore(previous_state)
        raise