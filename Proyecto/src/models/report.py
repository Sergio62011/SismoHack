from datetime import datetime, timezone


class Report:
    """Incoming station report before the system decides what to do with it."""

    def __init__(
        self,
        event_id: int,
        magnitude: float,
        depth: float,
        x: float,
        y: float,
        datetime: datetime,
        revision: int,
        station: str,
    ):
        self.event_id = event_id
        self.magnitude = magnitude
        self.depth = depth
        self.x = x
        self.y = y
        self.datetime = datetime
        self.revision = revision
        self.station = station

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
            "station": self.station,
        }

    @classmethod
    def from_dict(cls, data):
        dt = datetime.strptime(
            data["datetime"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        return cls(
            event_id=data["event_id"],
            magnitude=data["magnitude"],
            depth=data["depth"],
            x=data["x"],
            y=data["y"],
            datetime=dt,
            revision=data["revision"],
            station=data["station"],
        )

    def copy(self):
        return Report(
            self.event_id, self.magnitude, self.depth,
            self.x, self.y, self.datetime, self.revision, self.station,
        )

    def __repr__(self):
        return (
            f"Report(id={self.event_id}, M={self.magnitude}, "
            f"revision={self.revision}, station={self.station})"
        )