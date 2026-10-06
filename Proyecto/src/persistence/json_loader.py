"""Strict JSON loaders for SismoLab structural and insertion modes."""

import json
from collections import deque
from pathlib import Path

from models.scenario import Scenario
from models.event import Event
from models.report import Report
from services.seismic_system import SeismicSystem
from structure.avl import AVL
from structure.bst import BST
from structure.node import Node


class JsonPersistenceError(ValueError):
    """Raised when a JSON file cannot safely become a system state."""


class JsonLoader:
    """Loads JSON only after every required invariant has been verified."""

    FORMAT = "SismoLab-AVL"
    SCHEMA_VERSION = 1
    REQUIRED_METRICS = {
        "accepted_corrections",
        "discarded_reports",
        "conflicts",
        "confirmations",
        "created_by_report",
        "reactivated",
        "massive_archives",
        "archived_events",
    }

    REQUIRED_RECOVERY_COST = {
        "height_before",
        "height_after",
        "rotations",
        "turns",
        "passes",
        "nodes_visited",
    }

    @classmethod
    def load_topology(cls, path, current_system=None):
        """Restores the stored AVL links exactly as they appear in JSON.

        If a current_system is given, a snapshot is taken and restored
        if any validation or build step fails. This guarantees the load
        is all-or-nothing.
        """
        data = cls._read_file(path)
        cls._validate_header(data)

        snapshot = None
        if current_system is not None:
            snapshot = current_system._snapshot()

        try:
            scenario = cls._load_scenario(data)
            execution = cls._load_execution(data.get("execution"))
            tree, active = cls._build_topological_tree(
                data.get("active_tree"), scenario, execution["stress_mode"]
            )
            historical = cls._load_historical(
                data.get("historical_events"), scenario, set(active)
            )
            removed = cls._load_removed(
                data.get("removed_ids"), set(active), set(historical)
            )
            cls._validate_associations(
                {**active, **historical}, removed
            )
            queue = cls._load_queue(data.get("report_queue"), scenario)
            last_report = cls._load_last_report(
                data.get("last_processed_report"), scenario
            )
            cls._validate_expensive_access(
                tree.root, scenario.parameters.l
            )
            cls._validate_last_report_out_of_queue(last_report, queue)

            system = SeismicSystem(scenario)
            system.avl = tree
            system.avl.rotations_performed = execution["rotations_total"]
            system._active_events = active
            system._historical_events = historical
            system.removed_ids = removed
            system.report_queue = queue
            system.last_processed_report = last_report
            system.metrics = execution["metrics"]
            system.last_rotations = execution["last_rotations"]
            system.last_recovery_cost = execution["last_recovery_cost"]
            system.update_expensive_access_flags()

            return system

        except Exception:
            if current_system is not None and snapshot is not None:
                current_system._restore(snapshot)
            raise

    @classmethod
    def load_by_insertions(cls, path):
        """Creates an AVL and a plain BST with the same event sequence.

        Forces normal mode during the whole load, as required by the
        specification ('this load is done with balancing active').
        """
        data = cls._read_file(path)
        cls._validate_header(data)
        scenario = cls._load_scenario(data)
        sequence = data.get("insertion_events")
        if not isinstance(sequence, list):
            raise JsonPersistenceError(
                "Insertion load requires the 'insertion_events' list"
            )

        system = SeismicSystem(scenario)
        system.avl.stress_mode = False
        bst = BST()
        ids = set()
        events = []
        for position, event_data in enumerate(sequence, start=1):
            event = cls._create_event(
                event_data, scenario, "active",
                f"insertion_events[{position}]"
            )
            if event.event_id in ids:
                raise JsonPersistenceError(
                    f"Duplicate identifier in sequence: {event.event_id}"
                )
            ids.add(event.event_id)
            events.append(event)

        for event in events:
            system.avl.insert(event)
            system._active_events[event.event_id] = event
            bst.insert(event.copy())

        system.update_expensive_access_flags()

        return system, bst

    @classmethod
    def _read_file(cls, path):
        file = Path(path)
        if not file.is_file():
            raise JsonPersistenceError(
                "The selected JSON file does not exist"
            )
        try:
            with file.open("r", encoding="utf-8") as stream:
                data = json.load(stream)
        except json.JSONDecodeError as error:
            raise JsonPersistenceError(
                f"Invalid JSON on line {error.lineno}: {error.msg}"
            ) from error
        except OSError as error:
            raise JsonPersistenceError(
                f"Could not read the file: {error}"
            ) from error
        if not isinstance(data, dict):
            raise JsonPersistenceError(
                "The JSON root must be an object"
            )
        return data

    @classmethod
    def _validate_header(cls, data):
        if data.get("format") != cls.FORMAT:
            raise JsonPersistenceError(
                "The file does not belong to SismoLab-AVL"
            )
        if data.get("schema_version") != cls.SCHEMA_VERSION:
            raise JsonPersistenceError(
                "The JSON schema version is not compatible"
            )

    @classmethod
    def _load_scenario(cls, data):
        scenario_data = data.get("scenario")
        if not isinstance(scenario_data, dict):
            raise JsonPersistenceError("Missing 'scenario' object")
        try:
            return Scenario.from_dict(scenario_data)
        except (KeyError, TypeError, ValueError) as error:
            raise JsonPersistenceError(
                f"Invalid scenario: {error}"
            ) from error

    @classmethod
    def _load_execution(cls, execution_data):
        if not isinstance(execution_data, dict):
            raise JsonPersistenceError("Missing 'execution' object")
        cls._require_fields(
            execution_data,
            {"stress_mode", "rotations_total", "last_rotations",
             "last_recovery_cost", "metrics"},
            "execution",
        )
        if not isinstance(execution_data["stress_mode"], bool):
            raise JsonPersistenceError(
                "'execution.stress_mode' must be boolean"
            )
        rotations_total = execution_data["rotations_total"]
        if (isinstance(rotations_total, bool)
                or not isinstance(rotations_total, int)
                or rotations_total < 0):
            raise JsonPersistenceError(
                "'execution.rotations_total' is invalid"
            )
        rotations = execution_data["last_rotations"]
        if (not isinstance(rotations, list)
                or any(r not in {"LL", "RR", "LR", "RL"} for r in rotations)):
            raise JsonPersistenceError(
                "'execution.last_rotations' is invalid"
            )
        metrics = execution_data["metrics"]
        if (not isinstance(metrics, dict)
                or set(metrics) != cls.REQUIRED_METRICS):
            raise JsonPersistenceError(
                "Stored metrics are not valid"
            )
        for name, value in metrics.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise JsonPersistenceError(f"Invalid metric: {name}")

        cost = execution_data["last_recovery_cost"]
        if cost is not None:
            if not isinstance(cost, dict):
                raise JsonPersistenceError(
                    "'execution.last_recovery_cost' must be an object or null"
                )
            missing = cls.REQUIRED_RECOVERY_COST - set(cost)
            if missing:
                raise JsonPersistenceError(
                    f"'last_recovery_cost' incomplete: {sorted(missing)}"
                )
            if not isinstance(cost["rotations"], list):
                raise JsonPersistenceError(
                    "'last_recovery_cost.rotations' must be a list"
                )
            for field in ("height_before", "height_after", "turns",
                          "passes", "nodes_visited"):
                value = cost[field]
                if isinstance(value, bool) or not isinstance(value, int):
                    raise JsonPersistenceError(
                        f"'last_recovery_cost.{field}' must be an integer"
                    )

        return {
            "stress_mode": execution_data["stress_mode"],
            "rotations_total": rotations_total,
            "last_rotations": list(rotations),
            "last_recovery_cost": cost,
            "metrics": dict(metrics),
        }

    # === Topology ===

    @classmethod
    def _build_topological_tree(cls, tree_data, scenario, stress_mode):
        if not isinstance(tree_data, dict):
            raise JsonPersistenceError("Missing 'active_tree' object")
        root_id = tree_data.get("root")
        nodes_data = tree_data.get("nodes")
        if not isinstance(nodes_data, list):
            raise JsonPersistenceError(
                "'active_tree.nodes' must be a list"
            )
        if root_id is None and nodes_data:
            raise JsonPersistenceError(
                "A tree with nodes must have a root"
            )
        if root_id is not None and not nodes_data:
            raise JsonPersistenceError(
                "A root requires at least one node"
            )

        nodes = {}
        links = {}
        active = {}
        for position, node_data in enumerate(nodes_data, start=1):
            if not isinstance(node_data, dict):
                raise JsonPersistenceError(
                    f"active_tree.nodes[{position}] must be an object"
                )
            cls._require_fields(
                node_data,
                {"event", "left", "right", "height", "balance_factor"},
                f"active_tree.nodes[{position}]",
            )
            event = cls._create_event(
                node_data["event"], scenario, "active",
                f"active_tree.nodes[{position}].event",
            )
            eid = event.event_id
            if eid in nodes:
                raise JsonPersistenceError(
                    f"Active event {eid} appears more than once"
                )
            height = node_data["height"]
            if isinstance(height, bool) or not isinstance(height, int) or height < 0:
                raise JsonPersistenceError(
                    f"Stored height of {eid} is invalid"
                )
            factor = node_data["balance_factor"]
            if isinstance(factor, bool) or not isinstance(factor, int):
                raise JsonPersistenceError(
                    f"Stored factor of {eid} is invalid"
                )
            node = Node(event)
            node.height = height
            nodes[eid] = node
            links[eid] = (
                node_data["left"],
                node_data["right"],
                factor,
            )
            active[eid] = event

        if root_id is None:
            empty_tree = AVL()
            empty_tree.stress_mode = stress_mode
            return empty_tree, active

        cls._validate_id_reference(root_id, nodes, "The root")

        parents = set()
        for eid, (left, right, _) in links.items():
            for side, child_id in (("left", left), ("right", right)):
                if child_id is None:
                    continue
                cls._validate_id_reference(
                    child_id, nodes, f"{side} child of {eid}"
                )
                if child_id in parents:
                    raise JsonPersistenceError(
                        f"Node {child_id} has more than one parent"
                    )
                parents.add(child_id)
            nodes[eid].left = nodes.get(left)
            nodes[eid].right = nodes.get(right)
            if left is not None:
                nodes[left].parent = nodes[eid]
            if right is not None:
                nodes[right].parent = nodes[eid]

        if root_id in parents:
            raise JsonPersistenceError("The root cannot have a parent")

        visited = set()

        def traverse(node):
            eid = node.event.event_id
            if eid in visited:
                raise JsonPersistenceError(
                    "The topology contains a cycle"
                )
            visited.add(eid)
            if node.left:
                traverse(node.left)
            if node.right:
                traverse(node.right)

        traverse(nodes[root_id])
        if visited != set(nodes):
            missing = sorted(set(nodes) - visited)
            raise JsonPersistenceError(
                f"Active nodes outside the topology: {missing}"
            )

        cls._validate_bst_and_metadata(nodes[root_id], links, stress_mode)
        tree = AVL()
        tree.root = nodes[root_id]
        tree.stress_mode = stress_mode
        return tree, active

    @classmethod
    def _validate_bst_and_metadata(cls, root, links, stress_mode):
        def traverse(node, lower, upper):
            key = node.event.calculate_key()
            if lower is not None and key <= lower:
                raise JsonPersistenceError(
                    f"BST order is invalid in event {node.event.event_id}"
                )
            if upper is not None and key >= upper:
                raise JsonPersistenceError(
                    f"BST order is invalid in event {node.event.event_id}"
                )
            left_height = (
                traverse(node.left, lower, key) if node.left else -1
            )
            right_height = (
                traverse(node.right, key, upper) if node.right else -1
            )
            height = 1 + max(left_height, right_height)
            factor = left_height - right_height
            stored = links[node.event.event_id]
            if node.height != height:
                raise JsonPersistenceError(
                    f"Inconsistent height in event {node.event.event_id}"
                )
            if stored[2] != factor:
                raise JsonPersistenceError(
                    f"Inconsistent balance factor in event "
                    f"{node.event.event_id}"
                )
            if not stress_mode and abs(factor) > 1:
                raise JsonPersistenceError(
                    "An unbalanced topology requires stress mode"
                )
            return height

        traverse(root, None, None)

    @classmethod
    def _load_historical(cls, historical_data, scenario, active_ids):
        if not isinstance(historical_data, list):
            raise JsonPersistenceError(
                "'historical_events' must be a list"
            )
        historical = {}
        for position, event_data in enumerate(historical_data, start=1):
            event = cls._create_event(
                event_data, scenario, "archived",
                f"historical_events[{position}]",
            )
            if event.event_id in active_ids or event.event_id in historical:
                raise JsonPersistenceError(
                    f"Identifier {event.event_id} is duplicated"
                )
            historical[event.event_id] = event
        return historical

    @classmethod
    def _load_removed(cls, removed_data, active_ids, historical_ids):
        if not isinstance(removed_data, list):
            raise JsonPersistenceError("'removed_ids' must be a list")
        removed = set()
        for identifier in removed_data:
            eid = cls._validate_integer_id(
                identifier, "Removed identifier"
            )
            if eid in removed:
                raise JsonPersistenceError(
                    f"Duplicate removed identifier: {eid}"
                )
            if eid in active_ids or eid in historical_ids:
                raise JsonPersistenceError(
                    f"Identifier {eid} is active, historical and removed"
                )
            removed.add(eid)
        return removed

    @classmethod
    def _create_event(cls, data, scenario, location, context):
        if not isinstance(data, dict):
            raise JsonPersistenceError(f"{context} must be an object")
        required = {
            "event_id", "magnitude", "depth", "x", "y", "datetime",
            "revision", "state", "stations", "in_populated_zone",
            "priority", "expensive_access", "location",
            "reference", "referenced_by",
        }
        cls._require_fields(data, required, context)

        stored_priority = data["priority"]

        try:
            event = Event.from_dict(data)
            SeismicSystem._validate_id(event.event_id)
            SeismicSystem._validate_revision(event.revision)
            SeismicSystem._validate_data(
                event.magnitude, event.depth,
                event.x, event.y, event.datetime,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise JsonPersistenceError(
                f"Invalid event in {context}: {error}"
            ) from error

        if event.datetime > scenario.clock.instant:
            raise JsonPersistenceError(
                f"Event {event.event_id} is later than the scenario clock"
            )
        if event.state not in {"pending", "reviewed"}:
            raise JsonPersistenceError(
                f"Invalid state in event {event.event_id}"
            )
        if event.location != location:
            raise JsonPersistenceError(
                f"Invalid location in event {event.event_id}"
            )

        stations = data["stations"]
        if (not isinstance(stations, list)
                or len(set(stations)) != len(stations)):
            raise JsonPersistenceError(
                f"Invalid stations in event {event.event_id}"
            )
        if any(
            station not in scenario.stations
            for station in stations
        ):
            raise JsonPersistenceError(
                f"Event {event.event_id} references a non-existent station"
            )

        in_zone = scenario.map.is_in_populated_zone(event.x, event.y)
        if event.in_populated_zone != in_zone:
            raise JsonPersistenceError(
                f"Inconsistent populated zone in event {event.event_id}"
            )

        if stored_priority != event.priority:
            raise JsonPersistenceError(
                f"Stored priority inconsistent in event "
                f"{event.event_id}: JSON={stored_priority}, "
                f"calculated={event.priority}"
            )
        if not isinstance(data["in_populated_zone"], bool):
            raise JsonPersistenceError(
                f"Invalid populated zone in event {event.event_id}"
            )
        if not isinstance(data["expensive_access"], bool):
            raise JsonPersistenceError(
                f"Invalid access flag in event {event.event_id}"
            )
        return event

    # =========================================================
    # Reports
    # =========================================================

    @classmethod
    def _load_queue(cls, queue_data, scenario):
        if not isinstance(queue_data, list):
            raise JsonPersistenceError("'report_queue' must be a list")
        queue = deque()
        for position, report_data in enumerate(queue_data, start=1):
            queue.append(cls._create_report(
                report_data, scenario, f"report_queue[{position}]"
            ))
        return queue

    @classmethod
    def _load_last_report(cls, report_data, scenario):
        if report_data is None:
            return None
        return cls._create_report(
            report_data, scenario, "last_processed_report"
        )

    @classmethod
    def _create_report(cls, data, scenario, context):
        if not isinstance(data, dict):
            raise JsonPersistenceError(f"{context} must be an object")
        required = {
            "event_id", "magnitude", "depth", "x", "y", "datetime",
            "revision", "station",
        }
        cls._require_fields(data, required, context)
        try:
            report = Report.from_dict(data)
            SeismicSystem._validate_id(report.event_id)
            SeismicSystem._validate_revision(report.revision)
            SeismicSystem._validate_data(
                report.magnitude, report.depth,
                report.x, report.y, report.datetime,
            )
            SeismicSystem._validate_station(report.station)
        except (KeyError, TypeError, ValueError) as error:
            raise JsonPersistenceError(
                f"Invalid report in {context}: {error}"
            ) from error
        if report.station not in scenario.stations:
            raise JsonPersistenceError(
                f"The report in {context} references a non-existent station"
            )
        return report

    # =========================================================
    # Associations
    # =========================================================

    @classmethod
    def _validate_associations(cls, events, removed_ids=None):
        removed_ids = removed_ids or set()

        for event in events.values():
            reference = event.reference
            if reference is not None:
                if reference in removed_ids:
                    raise JsonPersistenceError(
                        f"Event {event.event_id} references the removed "
                        f"{reference}"
                    )
                if reference not in events or reference == event.event_id:
                    raise JsonPersistenceError(
                        f"Invalid reference in event {event.event_id}"
                    )
                if event.event_id not in events[reference].referenced_by:
                    raise JsonPersistenceError(
                        f"Non-reciprocal reference in event "
                        f"{event.event_id}"
                    )
            for referenced in event.referenced_by:
                if referenced in removed_ids:
                    raise JsonPersistenceError(
                        f"Event {event.event_id} is referenced by the "
                        f"removed {referenced}"
                    )
                if referenced not in events:
                    raise JsonPersistenceError(
                        f"Invalid association in event {event.event_id}"
                    )
                if events[referenced].reference != event.event_id:
                    raise JsonPersistenceError(
                        f"Non-reciprocal association in event "
                        f"{event.event_id}"
                    )

        for event in events.values():
            visited = set()
            current = event
            while current.reference is not None:
                if current.event_id in visited:
                    raise JsonPersistenceError(
                        "Associations contain a cycle"
                    )
                visited.add(current.event_id)
                current = events[current.reference]

    @classmethod
    def _validate_last_report_out_of_queue(cls, last_report, queue):
        if last_report is None:
            return
        for report in queue:
            if (
                report.event_id == last_report.event_id
                and report.revision == last_report.revision
                and report.station == last_report.station
            ):
                raise JsonPersistenceError(
                    f"The last processed report ({last_report.event_id} "
                    f"rev {last_report.revision}) is still in the queue"
                )

    @classmethod
    def _validate_expensive_access(cls, root, limit_l):
        def traverse(node, depth):
            if node is None:
                return
            expected = (
                node.event.priority == 3 and depth > limit_l
            )
            if node.event.expensive_access != expected:
                raise JsonPersistenceError(
                    f"Inconsistent expensive access flag in event "
                    f"{node.event.event_id}: stored="
                    f"{node.event.expensive_access}, expected={expected} "
                    f"(depth={depth}, L={limit_l})"
                )
            traverse(node.left, depth + 1)
            traverse(node.right, depth + 1)

        traverse(root, 0)

    # =========================================================
    # Helpers
    # =========================================================

    @classmethod
    def _validate_id_reference(cls, value, nodes, context):
        if (isinstance(value, bool)
                or not isinstance(value, int)
                or value not in nodes):
            raise JsonPersistenceError(
                f"{context} references a non-existent node"
            )

    @classmethod
    def _validate_integer_id(cls, value, context):
        try:
            return SeismicSystem._validate_id(value)
        except ValueError as error:
            raise JsonPersistenceError(
                f"{context} invalid: {error}"
            ) from error

    @staticmethod
    def _require_fields(data, required, context):
        missing = sorted(required - set(data))
        if missing:
            raise JsonPersistenceError(
                f"Missing fields in {context}: {', '.join(missing)}"
            )