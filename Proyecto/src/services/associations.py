from datetime import timedelta
from math import hypot


def _valid_events(system):
    events = {}

    for event in system._active_events.values():
        events[event.event_id] = event

    for event in system._historical_events.values():
        if event.event_id not in system.removed_ids:
            events[event.event_id] = event

    return list(events.values())


def _distance(event_a, event_b):
    return hypot(
        event_a.x - event_b.x,
        event_a.y - event_b.y
    )


def is_candidate(event_a, event_b, w_hours, r_km):
    if w_hours < 0 or r_km < 0:
        return False

    if event_a.event_id == event_b.event_id:
        return False

    # A must have a greater magnitude than B
    if event_a.magnitude <= event_b.magnitude:
        return False

    # A must have occurred strictly before B
    if event_a.datetime >= event_b.datetime:
        return False

    difference = event_b.datetime - event_a.datetime

    if difference > timedelta(hours=w_hours):
        return False

    if _distance(event_a, event_b) > r_km:
        return False

    return True


def get_candidates(system, event):
    w_hours = system.parameters.w
    r_km = system.parameters.r

    candidates = []

    for candidate in _valid_events(system):
        if candidate.event_id == event.event_id:
            continue

        if is_candidate(candidate, event, w_hours, r_km):
            candidates.append(candidate)

    return candidates


def choose_reference(event, candidates):
    if not candidates:
        return None

    def criterion(candidate):
        difference = (
            event.datetime - candidate.datetime
        ).total_seconds()

        distance = _distance(candidate, event)

        return (
            difference,
            distance,
            -candidate.magnitude,
            candidate.event_id
        )

    return min(candidates, key=criterion)


def recalculate_all(system):
    events = _valid_events(system)

    # First, clear previous relationships.
    for event in events:
        event.reference = None
        event.referenced_by.clear()

    # Then recalculate them.
    for event in events:
        candidates = get_candidates(system, event)
        reference = choose_reference(event, candidates)

        if reference is not None:
            event.reference = reference.event_id
            reference.referenced_by.add(event.event_id)


def update_associations_of(system, event_id=None):
    recalculate_all(system)