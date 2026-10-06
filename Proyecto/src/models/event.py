from datetime import datetime, timezone
from typing import Set, Optional


class Event:
    """Represents a seismic event with all its data."""

    def __init__(
        self,
        event_id: int,
        magnitude: float,
        depth: float,
        x: float,
        y: float,
        datetime: datetime,
        revision: int = 1,
        state: str = "pending",
        populated_zone: bool = False,
    ):
        self.event_id = int(event_id)
        self.magnitude = float(magnitude)
        self.depth = float(depth)
        self.x = float(x)
        self.y = float(y)
        self.datetime = datetime

        self.revision = int(revision)
        self.state = state
        self.stations: Set[str] = set()
        self.in_populated_zone = populated_zone

        self.priority = self._calculate_priority()
        self.expensive_access = False

        self.location = "active"

        self.reference: Optional[int] = None
        self.referenced_by: Set[int] = set()

    # === Priority ===

    def _calculate_priority(self) -> int:
        if self.magnitude >= 6.0:
            return 3
        if (
            self.magnitude >= 4.5
            and self.depth <= 30.0
            and self.in_populated_zone
        ):
            return 3
        if self.magnitude >= 4.5:
            return 2
        return 1

    def recalculate_priority(self):
        self.priority = self._calculate_priority()

    # === Key ===

    def calculate_key(self) -> tuple:
        return (self.priority, self.magnitude, self.event_id)

    # === Comparison ===

    def __lt__(self, other):
        return self.calculate_key() < other.calculate_key()

    def __eq__(self, other):
        return self.calculate_key() == other.calculate_key()

    def __hash__(self):
        return hash(self.event_id)

    # === Persistence and copy ===

    def to_dict(self):
        return {
            "event_id": self.event_id,
            "magnitude": self.magnitude,
            "depth": self.depth,
            "x": self.x,
            "y": self.y,
            "datetime": self.datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "revision": self.revision,
            "state": self.state,
            "stations": sorted(self.stations),
            "in_populated_zone": self.in_populated_zone,
            "priority": self.priority,
            "expensive_access": self.expensive_access,
            "location": self.location,
            "reference": self.reference,
            "referenced_by": sorted(self.referenced_by),
        }

    @classmethod
    def from_dict(cls, data):
        dt = datetime.strptime(
            data["datetime"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        event = cls(
            event_id=data["event_id"],
            magnitude=data["magnitude"],
            depth=data["depth"],
            x=data["x"],
            y=data["y"],
            datetime=dt,
            revision=data["revision"],
            state=data["state"],
            populated_zone=data["in_populated_zone"],
        )
        event.stations = set(data.get("stations", []))
        event.expensive_access = bool(data.get("expensive_access", False))
        event.location = data.get("location", "active")
        event.reference = data.get("reference")
        event.referenced_by = set(data.get("referenced_by", []))
        # Recalculate priority to ensure consistency
        event.recalculate_priority()
        return event

    def copy(self):
        new = Event(
            event_id=self.event_id,
            magnitude=self.magnitude,
            depth=self.depth,
            x=self.x,
            y=self.y,
            datetime=self.datetime,
            revision=self.revision,
            state=self.state,
            populated_zone=self.in_populated_zone,
        )
        new.stations = set(self.stations)
        new.expensive_access = self.expensive_access
        new.location = self.location
        new.reference = self.reference
        new.referenced_by = set(self.referenced_by)
        new.recalculate_priority()
        return new

    def __repr__(self):
        return (
            f"Event(id={self.event_id}, M={self.magnitude}, "
            f"H={self.depth}, P={self.priority}, "
            f"key={self.calculate_key()})"
        )