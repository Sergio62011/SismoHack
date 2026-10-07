# Módulo json saver: contiene la lógica relacionada con json saver.
"""JSON serialization for the complete SismoLab operational state."""

import json
import os
from pathlib import Path


# Representa JsonSaver y agrupa sus datos y operaciones.
class JsonSaver:
    """Exports a system without flattening the active AVL topology."""

    FORMAT = "SismoLab-AVL"
    SCHEMA_VERSION = 1

    @classmethod
    # Gestiona save.
    def save(cls, system, path):
        """Writes a complete structural snapshot to a user-selected path."""
        destination = Path(path)
        if not destination.name:
            raise ValueError("You must select a JSON file")
        if destination.suffix.lower() != ".json":
            destination = destination.with_suffix(".json")

        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = destination.with_name(destination.name + ".tmp")
        data = cls.to_dict(system)

        try:
            with temp.open("w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
                file.write("\n")
            os.replace(temp, destination)
        except OSError as error:
            if temp.exists():
                temp.unlink()
            raise ValueError(
                f"Could not save the file: {error}"
            ) from error

        return destination

    @classmethod
    # Gestiona to dict.
    def to_dict(cls, system):
        """Builds the JSON-compatible representation of a system."""
        tree = cls._serialize_tree(system.avl.root)
        return {
            "format": cls.FORMAT,
            "schema_version": cls.SCHEMA_VERSION,
            "meta": {
                "load_mode": "topology",
            },
            "scenario": system.scenario.to_dict(),
            "execution": {
                "stress_mode": system.avl.stress_mode,
                "rotations_total": system.avl.rotations_performed,
                "last_rotations": list(system.last_rotations),
                "last_recovery_cost": system.last_recovery_cost,
                "metrics": dict(system.metrics),
            },
            "active_tree": tree,
            "historical_events": [
                event.to_dict()
                for _, event in sorted(system._historical_events.items())
            ],
            "removed_ids": sorted(system.removed_ids),
            "report_queue": [
                report.to_dict() for report in system.report_queue
            ],
            "last_processed_report": (
                system.last_processed_report.to_dict()
                if system.last_processed_report is not None
                else None
            ),
            "insertion_events": cls._preorder_events(system.avl.root),
        }

    @classmethod
    # Gestiona serialize tree.
    def _serialize_tree(cls, root):
        nodes = []

        # Gestiona visit.
        def visit(node):
            if node is None:
                return
            nodes.append({
                "event": node.event.to_dict(),
                "left": node.left.event.event_id if node.left else None,
                "right": node.right.event.event_id if node.right else None,
                "height": node.height,
                "balance_factor": node.balance_factor,
            })
            visit(node.left)
            visit(node.right)

        visit(root)
        return {
            "root": root.event.event_id if root else None,
            "nodes": nodes,
        }

    @classmethod
    # Gestiona preorder events.
    def _preorder_events(cls, root):
        events = []

        # Gestiona visit.
        def visit(node):
            if node is None:
                return
            events.append(node.event.to_dict())
            visit(node.left)
            visit(node.right)

        visit(root)
        return events