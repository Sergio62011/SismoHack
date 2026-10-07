# Módulo seismic system: contiene la lógica relacionada con seismic system.
from collections import deque
from datetime import datetime, timezone
from math import isfinite

from models.scenario import Scenario
from models.event import Event
from models.map import SeismicMap
from models.station import Station
from structure.avl import AVL
from services.history import Action, History
from services.associations import update_associations_of


# Representa SeismicSystem y agrupa sus datos y operaciones.
class SeismicSystem:

    # Define init.
    def __init__(self, scenario=None):
        if scenario is None:
            scenario = Scenario(SeismicMap())
        self.scenario = scenario
        self.avl = AVL()
        self._active_events = {}
        self._historical_events = {}
        self.removed_ids = set()
        self.report_queue = deque()
        self.last_rotations = []
        self.last_processed_report = None
        self.metrics = {
            "accepted_corrections": 0,
            "discarded_reports": 0,
            "conflicts": 0,
            "confirmations": 0,
            "created_by_report": 0,
            "reactivated": 0,
            "massive_archives": 0,
            "archived_events": 0,
        }
        self.history = History()
        self.last_recovery_cost = None

    @property
    # Gestiona clock.
    def clock(self):
        return self.scenario.clock

    @property
    # Gestiona parameters.
    def parameters(self):
        return self.scenario.parameters

    @property
    # Gestiona map.
    def map(self):
        return self.scenario.map

    @property
    # Gestiona stations.
    def stations(self):
        return self.scenario.stations

    # Gestiona register station.
    def register_station(self, station_id, name):
        station = Station(station_id, name)
        if station.station_id in self.stations:
            raise ValueError(
                f"A station with ID {station.station_id} already exists"
            )
        self.stations[station.station_id] = station
        return station

    # Gestiona get station.
    def get_station(self, station_id):
        sid = self._validate_station(station_id)
        return self.stations.get(sid)

    # Gestiona id exists.
    def _id_exists(self, event_id):
        return (
            event_id in self._active_events
            or event_id in self._historical_events
            or event_id in self.removed_ids
        )

    # Gestiona snapshot.
    def _snapshot(self):
        return {
            "avl": self.avl.copy(),
            "active": {
                k: event.copy() for k, event in self._active_events.items()
            },
            "historical": {
                k: historical.copy()
                for k, historical in self._historical_events.items()
            },
            "removed": set(self.removed_ids),
            "queue": deque(report.copy() for report in self.report_queue),
            "scenario": self.scenario.copy(),
            "stress_mode": self.avl.stress_mode,
            "metrics": dict(self.metrics),
        }

    # Gestiona restore.
    def _restore(self, snapshot):
        self.avl = snapshot["avl"]
        self._active_events = snapshot["active"]
        self._historical_events = snapshot["historical"]
        self.removed_ids = snapshot["removed"]
        self.report_queue = snapshot["queue"]
        self.scenario = snapshot["scenario"]
        self.avl.stress_mode = snapshot["stress_mode"]
        self.metrics = snapshot["metrics"]
        self.update_expensive_access_flags()

    # Gestiona undo.
    def undo(self):
        action = self.history.undo()
        if action is None:
            return False
        self._restore(action.previous_state)
        return True

    # Gestiona can undo.
    def can_undo(self):
        return not self.history.is_empty()

    # Gestiona last action description.
    def last_action_description(self):
        if self.history.is_empty():
            return None
        return self.history._stack[-1].description

    # === CREATE ===

    # Gestiona create event.
    def create_event(self, event_id, magnitude, depth, x, y,
                     datetime_value, station):
        eid = self._validate_id(event_id)
        if self._id_exists(eid):
            raise ValueError(
                f"Identifier {eid} already exists in the scenario"
            )
        data = self._validate_data(
            magnitude, depth, x, y, datetime_value
        )
        if not self.clock.is_not_future(data["datetime"]):
            raise ValueError(
                "The event date cannot be later than the clock"
            )
        station = self._resolve_station(station)

        previous_state = self._snapshot()
        try:
            event = Event(
                event_id=eid,
                magnitude=data["magnitude"],
                depth=data["depth"],
                x=data["x"],
                y=data["y"],
                datetime=data["datetime"],
                revision=1,
                state="pending",
            )
            event.stations.add(station)
            self.map.assign_zone_to_event(event)

            self.avl.insert(event)
            self._active_events[eid] = event
            update_associations_of(self, eid)
            self.update_expensive_access_flags()

            self.history.record_action(
                Action(f"create_event {eid}", previous_state)
            )
            return event
        except Exception:
            self._restore(previous_state)
            raise

    # === READ ===

    # Gestiona find by id.
    def find_by_id(self, event_id):
        return self._active_events.get(self._validate_id(event_id))

    # Gestiona query event.
    def query_event(self, event_id):
        eid = self._validate_id(event_id)
        if eid in self._active_events:
            return {"state": "active",
                    "event": self._active_events[eid]}
        if eid in self._historical_events:
            return {"state": "archived",
                    "event": self._historical_events[eid]}
        if eid in self.removed_ids:
            return {"state": "removed", "event": None}
        return {"state": "unknown", "event": None}

    # === UPDATE ===

    # Gestiona correct event.
    def correct_event(self, event_id, *, magnitude=None, depth=None,
                      x=None, y=None, datetime_value=None):
        event = self._get_active(event_id)
        data = self._validate_data(
            event.magnitude if magnitude is None else magnitude,
            event.depth if depth is None else depth,
            event.x if x is None else x,
            event.y if y is None else y,
            event.datetime if datetime_value is None else datetime_value,
        )
        if not self.clock.is_not_future(data["datetime"]):
            raise ValueError(
                "The event date cannot be later than the clock"
            )

        previous_state = self._snapshot()
        try:
            previous_key = event.calculate_key()
            self.avl.delete(previous_key)
            rotations = list(self.avl.rotations_last_operation)

            self._apply_data(event, data)
            event.revision += 1
            event.state = "pending"
            self.map.assign_zone_to_event(event)

            self.avl.insert(event)
            rotations.extend(self.avl.rotations_last_operation)
            self.last_rotations = rotations
            update_associations_of(self, event.event_id)
            self.update_expensive_access_flags()

            self.history.record_action(
                Action(f"correct_event {event.event_id}", previous_state)
            )
            return event
        except Exception:
            self._restore(previous_state)
            raise

    # Gestiona mark reviewed.
    def mark_reviewed(self, event_id):
        event = self._get_active(event_id)
        previous_state = self._snapshot()
        try:
            event.state = "reviewed"
            self.history.record_action(
                Action(f"mark_reviewed {event.event_id}", previous_state)
            )
            return event
        except Exception:
            self._restore(previous_state)
            raise

    # Gestiona remove event.
    def remove_event(self, event_id):
        eid = self._validate_id(event_id)
        event = self._get_active(eid)

        previous_state = self._snapshot()
        try:
            self.avl.delete(event.calculate_key())
            del self._active_events[eid]
            self.removed_ids.add(eid)
            event.location = "removed"
            update_associations_of(self, eid)
            self.update_expensive_access_flags()

            self.history.record_action(
                Action(f"remove_event {eid}", previous_state)
            )
            return event
        except Exception:
            self._restore(previous_state)
            raise

    # === CLOCK AND PARAMETERS ===

    # Gestiona jump clock.
    def jump_clock(self, datetime_value):
        if datetime_value.tzinfo is None:
            raise ValueError("The datetime must have a UTC timezone")
        datetime_value = datetime_value.astimezone(timezone.utc)

        if datetime_value < self.clock.instant:
            raise ValueError(
                f"The date is earlier than the current clock. "
                f"Cannot move the clock backwards."
            )

        previous_state = self._snapshot()
        try:
            self.clock.jump_to(datetime_value)
            self.history.record_action(
                Action(
                    f"jump_clock {datetime_value.isoformat()}",
                    previous_state
                )
            )
        except Exception:
            self._restore(previous_state)
            raise

    # Gestiona advance clock.
    def advance_clock(self, seconds):
        previous_state = self._snapshot()
        try:
            self.clock.advance(seconds)
            self.history.record_action(
                Action(f"advance_clock {seconds}s", previous_state)
            )
        except Exception:
            self._restore(previous_state)
            raise

    # Gestiona set w.
    def set_w(self, value):
        previous_state = self._snapshot()
        try:
            self.parameters.set_w(value)
            update_associations_of(self)
            self.history.record_action(
                Action(f"set_w {value}", previous_state)
            )
        except Exception:
            self._restore(previous_state)
            raise

    # Gestiona set r.
    def set_r(self, value):
        previous_state = self._snapshot()
        try:
            self.parameters.set_r(value)
            update_associations_of(self)
            self.history.record_action(
                Action(f"set_r {value}", previous_state)
            )
        except Exception:
            self._restore(previous_state)
            raise

    # Gestiona set l.
    def set_l(self, value):
        previous_state = self._snapshot()
        try:
            self.parameters.set_l(value)
            self.update_expensive_access_flags()

            self.history.record_action(
                Action(f"set_l {value}", previous_state)
            )
        except Exception:
            self._restore(previous_state)
            raise

    # Gestiona set t.
    def set_t(self, value):
        previous_state = self._snapshot()
        try:
            self.parameters.set_t(value)
            self.history.record_action(
                Action(f"set_t {value}", previous_state)
            )
        except Exception:
            self._restore(previous_state)
            raise

    # Gestiona update parameters.
    def update_parameters(self, *, w=None, r=None, l=None, t=None):
        previous_state = self._snapshot()
        try:
            new = self.parameters.copy()
            if w is not None:
                new.set_w(w)
            if r is not None:
                new.set_r(r)
            if l is not None:
                new.set_l(l)
            if t is not None:
                new.set_t(t)

            associations_changed = (
                new.w != self.parameters.w
                or new.r != self.parameters.r
            )
            l_changed = new.l != self.parameters.l

            if (
                new.w == self.parameters.w
                and new.r == self.parameters.r
                and new.l == self.parameters.l
                and new.t == self.parameters.t
            ):
                return False

            self.scenario.parameters = new
            if associations_changed:
                update_associations_of(self)
            if associations_changed or l_changed:
                self.update_expensive_access_flags()

            self.history.record_action(
                Action("update_parameters", previous_state)
            )
            return True
        except Exception:
            self._restore(previous_state)
            raise

    # === QUEUE ===

    # Gestiona enqueue report.
    def enqueue_report(self, report):
        self.report_queue.append(report)

    # Gestiona has pending reports.
    def has_pending_reports(self):
        return len(self.report_queue) > 0

    # Gestiona pending report count.
    def pending_report_count(self):
        return len(self.report_queue)

    # Gestiona process next report.
    def process_next_report(self):
        if not self.has_pending_reports():
            return self._result(
                "empty_queue", "No pending reports", None,
                rotations=[],
            )

        previous_state = self._snapshot()
        try:
            report = self.report_queue.popleft()
            self.last_processed_report = report
            result = self.process_report(report)
            result["report"] = report
            result["remaining_pending"] = (
                self.pending_report_count()
            )

            self.history.record_action(
                Action(
                    f"process_report {report.event_id} "
                    f"rev {report.revision}",
                    previous_state,
                )
            )
            return result
        except Exception:
            self._restore(previous_state)
            raise

    # Gestiona process all.
    def process_all(self):
        results = []
        while self.has_pending_reports():
            results.append(self.process_next_report())
        return results

    # === REPORT PROCESSING ===

    # Gestiona process report.
    def process_report(self, report):
        eid = self._validate_id(report.event_id)
        revision = self._validate_revision(report.revision)
        station = self._resolve_station(report.station)
        data = self._validate_data(
            report.magnitude, report.depth,
            report.x, report.y, report.datetime,
        )

        if eid in self.removed_ids:
            self.metrics["discarded_reports"] += 1
            return self._result(
                "rejected",
                f"Event {eid} was removed and cannot be reactivated",
                None, rotations=[],
            )

        archived = self._historical_events.get(eid)
        if archived is not None:
            if revision > archived.revision:
                self._apply_data(archived, data)
                archived.revision = revision
                archived.state = "pending"
                archived.location = "active"
                archived.stations.add(station)
                self.map.assign_zone_to_event(archived)
                self.avl.insert(archived)
                self._active_events[eid] = archived
                del self._historical_events[eid]
                self.metrics["reactivated"] += 1
                update_associations_of(self, eid)
                self.update_expensive_access_flags()

                return self._result(
                    "reactivated",
                    f"Event {eid} reactivated from history",
                    archived,
                )
            self.metrics["discarded_reports"] += 1
            return self._result(
                "archived_ignored",
                f"Event {eid} archived; the report does not reactivate it",
                archived, rotations=[],
            )

        event = self._active_events.get(eid)

        if event is None:
            new = Event(
                event_id=eid,
                magnitude=data["magnitude"],
                depth=data["depth"],
                x=data["x"],
                y=data["y"],
                datetime=data["datetime"],
                revision=revision,
                state="pending",
            )
            new.stations.add(station)
            self.map.assign_zone_to_event(new)
            self.avl.insert(new)
            self._active_events[eid] = new
            self.metrics["created_by_report"] += 1
            update_associations_of(self, eid)
            self.update_expensive_access_flags()

            return self._result(
                "created", f"Event {eid} created from report", new
            )

        if revision > event.revision:
            previous_key = event.calculate_key()
            self.avl.delete(previous_key)
            rotations = list(self.avl.rotations_last_operation)
            self._apply_data(event, data)
            event.revision = revision
            event.state = "pending"
            event.stations.add(station)
            self.map.assign_zone_to_event(event)
            self.avl.insert(event)
            rotations.extend(self.avl.rotations_last_operation)
            self.metrics["accepted_corrections"] += 1
            update_associations_of(self, eid)
            self.update_expensive_access_flags()

            return self._result(
                "corrected",
                f"Event {eid} corrected with a higher revision",
                event, rotations=rotations,
            )

        if revision == event.revision:
            if self._data_equal(event, data):
                event.stations.add(station)
                self.metrics["confirmations"] += 1
                return self._result(
                    "confirmed",
                    f"Event {eid} confirmed by {station}",
                    event, rotations=[],
                )
            self.metrics["conflicts"] += 1
            return self._result(
                "conflict",
                "Report rejected: same revision with different data",
                event, rotations=[],
            )

        self.metrics["discarded_reports"] += 1
        return self._result(
            "outdated",
            f"Report discarded: revision {revision} is lower than {event.revision}",
            event, rotations=[],
        )

    # === INTERNAL HELPERS ===

    # Gestiona get active.
    def _get_active(self, event_id):
        eid = self._validate_id(event_id)
        event = self._active_events.get(eid)
        if event is None:
            raise ValueError(f"No active event with ID {eid}")
        return event

    @staticmethod
    # Gestiona data equal.
    def _data_equal(event, data):
        return (
            round(event.magnitude, 1) == round(data["magnitude"], 1)
            and round(event.depth, 1) == round(data["depth"], 1)
            and round(event.x, 1) == round(data["x"], 1)
            and round(event.y, 1) == round(data["y"], 1)
            and event.datetime == data["datetime"]
        )

    # Gestiona result.
    def _result(self, decision, message, event, rotations=None):
        if rotations is None:
            rotations = self.avl.rotations_last_operation
        return {
            "decision": decision,
            "message": message,
            "event": event,
            "rotations": list(rotations),
        }

    @staticmethod
    # Gestiona apply data.
    def _apply_data(event, data):
        event.magnitude = data["magnitude"]
        event.depth = data["depth"]
        event.x = data["x"]
        event.y = data["y"]
        event.datetime = data["datetime"]

    # Gestiona resolve station.
    def _resolve_station(self, station):
        sid = self._validate_station(station)
        if sid not in self.stations:
            self.register_station(sid, sid)
        return sid

    # === VALIDATION ===

    @staticmethod
    # Gestiona validate id.
    def _validate_id(event_id):
        if isinstance(event_id, bool):
            raise ValueError("The identifier must be an integer")
        if isinstance(event_id, str):
            text = event_id.strip()
            if not text.isdigit():
                raise ValueError("The identifier must be an integer")
            eid = int(text)
        else:
            try:
                eid = int(event_id)
            except (TypeError, ValueError) as error:
                raise ValueError(
                    "The identifier must be an integer"
                ) from error
            if eid != event_id:
                raise ValueError("The identifier must be an integer")
        if not 1 <= eid <= 999999:
            raise ValueError("The identifier must be between 1 and 999999")
        return eid

    @staticmethod
    # Gestiona validate station.
    def _validate_station(station):
        if not isinstance(station, str) or not station.strip():
            raise ValueError("The station is required")
        return station.strip()

    @staticmethod
    # Gestiona validate revision.
    def _validate_revision(revision):
        if isinstance(revision, bool):
            raise ValueError("The revision must be a positive integer")
        try:
            rev = int(revision)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "The revision must be a positive integer"
            ) from error
        if rev != revision:
            raise ValueError("The revision must be a positive integer")
        if rev <= 0:
            raise ValueError("The revision must be a positive integer")
        return rev

    @classmethod
    # Gestiona validate data.
    def _validate_data(cls, magnitude, depth, x, y, datetime_value):
        data = {
            "magnitude": cls._validate_decimal(
                "Magnitude", magnitude, -2.0, 10.0
            ),
            "depth": cls._validate_decimal(
                "Depth", depth, 0.0, 700.0
            ),
            "x": cls._validate_decimal("Coordinate x", x, 0.0, 1000.0),
            "y": cls._validate_decimal("Coordinate y", y, 0.0, 1000.0),
        }
        if not isinstance(datetime_value, datetime):
            raise ValueError("The datetime must be a datetime object")
        if datetime_value.tzinfo is None or datetime_value.utcoffset() is None:
            raise ValueError("The datetime must include a UTC timezone")
        data["datetime"] = datetime_value.astimezone(timezone.utc)
        return data

    @staticmethod
    # Gestiona validate decimal.
    def _validate_decimal(name, value, minimum, maximum):
        if isinstance(value, bool):
            raise ValueError(f"{name} must be a number")
        try:
            number = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{name} must be a number") from error
        if not isfinite(number) or not minimum <= number <= maximum:
            raise ValueError(
                f"{name} must be between {minimum} and {maximum}"
            )
        if abs(round(number, 1) - number) > 1e-9:
            raise ValueError(f"{name} allows at most one decimal")
        return number

    # Gestiona enable stress mode.
    def enable_stress_mode(self):
        previous_state = self._snapshot()
        try:
            self.avl.enable_stress_mode()
            self.history.record_action(
                Action("enable_stress_mode", previous_state)
            )
        except Exception:
            self._restore(previous_state)
            raise

    # Gestiona disable stress mode.
    def disable_stress_mode(self):
        previous_state = self._snapshot()
        try:
            height_before = self.avl.height()
            self.avl.recover_balance()
            height_after = self.avl.height()

            rotations = list(self.avl.rotations_last_operation)
            cost = {
                "height_before": height_before,
                "height_after": height_after,
                "rotations": rotations,
                "turns": self._count_turns(rotations),
                "passes": self.avl.recovery_passes,
                "nodes_visited": self.avl.recovery_nodes_visited,
            }
            self.last_recovery_cost = cost
            self.update_expensive_access_flags()
            self.history.record_action(
                Action("disable_stress_mode", previous_state)
            )
            return cost
        except Exception:
            self._restore(previous_state)
            raise

    @staticmethod
    # Gestiona count turns.
    def _count_turns(rotations):
        total = 0
        for r in rotations:
            if r in ("LL", "RR"):
                total += 1
            else:
                total += 2
        return total

    # Gestiona is in stress mode.
    def is_in_stress_mode(self):
        return self.avl.stress_mode

    # Gestiona update expensive access flags.
    def update_expensive_access_flags(self):
        for event in self._active_events.values():
            key = event.calculate_key()
            depth = self.avl.node_depth(key)
            if depth < 0:
                event.expensive_access = False
                continue
            event.expensive_access = (
                event.priority == 3
                and depth > self.parameters.l
            )

    # Gestiona nodes visited in search.
    def nodes_visited_in_search(self, event_id):
        event = self._get_active(event_id)
        key = event.calculate_key()
        depth = self.avl.node_depth(key)
        if depth < 0:
            return 0
        return depth + 1

    # Gestiona events with expensive access.
    def events_with_expensive_access(self):
        result = []
        for event in self._active_events.values():
            if not event.expensive_access:
                continue
            key = event.calculate_key()
            depth = self.avl.node_depth(key)
            result.append({
                "event": event,
                "depth": depth,
                "limit": self.parameters.l,
                "nodes_visited": (
                    depth + 1 if depth >= 0 else 0
                ),
            })
        return result

    # Gestiona add zone.
    def add_zone(self, zone):
        previous_state = self._snapshot()
        try:
            self.map.add_zone(zone)

            affected = 0
            for event in list(self._active_events.values()):
                if not zone.contains_point(event.x, event.y):
                    continue
                old_priority = event.priority
                self.map.assign_zone_to_event(event)
                if event.priority != old_priority:
                    old_key = (
                        old_priority, event.magnitude, event.event_id
                    )
                    self.avl.delete(old_key)
                    self.avl.insert(event)
                    affected += 1

            update_associations_of(self)
            self.update_expensive_access_flags()

            self.history.record_action(
                Action(f"add_zone {zone.name}", previous_state)
            )
            return affected
        except Exception:
            self._restore(previous_state)
            raise