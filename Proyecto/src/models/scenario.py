# Módulo scenario: contiene la lógica relacionada con scenario.
from datetime import datetime, timedelta, timezone


# Representa Clock y agrupa sus datos y operaciones.
class Clock:
    """Explicit simulation clock, in UTC, that only moves forward."""

    # Define init.
    def __init__(self, initial_instant=None):
        if initial_instant is None:
            initial_instant = datetime(
                2026, 9, 7, 0, 0, 0, tzinfo=timezone.utc
            )
        if initial_instant.tzinfo is None:
            raise ValueError("The clock must have a UTC timezone")
        self.instant = initial_instant.astimezone(timezone.utc)

    # === Operations ===

    # Gestiona advance.
    def advance(self, seconds):
        if seconds <= 0:
            raise ValueError("Clock advance must be positive")
        self.instant += timedelta(seconds=seconds)

    # Gestiona advance hours.
    def advance_hours(self, hours):
        self.advance(hours * 3600)

    # Gestiona is not future.
    def is_not_future(self, datetime_value):
        if datetime_value.tzinfo is None:
            raise ValueError("The datetime must have a UTC timezone")
        return datetime_value <= self.instant

    # Gestiona age in hours.
    def age_in_hours(self, datetime_value):
        if datetime_value.tzinfo is None:
            raise ValueError("The datetime must have a UTC timezone")
        delta = self.instant - datetime_value
        return delta.total_seconds() / 3600.0

    # Gestiona jump to.
    def jump_to(self, datetime_value):
        if datetime_value.tzinfo is None:
            raise ValueError("The datetime must have a UTC timezone")
        self.instant = datetime_value.astimezone(timezone.utc)

    # Gestiona copy.
    def copy(self):
        return Clock(self.instant)

    # === Persistence ===

    # Gestiona to dict.
    def to_dict(self):
        return {
            "instant": self.instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    @classmethod
    # Gestiona from dict.
    def from_dict(cls, data):
        if "instant" not in data:
            raise ValueError("The clock must have an 'instant' field")
        instant = datetime.strptime(
            data["instant"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        return cls(instant)

    # Define repr.
    def __repr__(self):
        return f"Clock({self.instant.isoformat()})"


# Representa Parameters y agrupa sus datos y operaciones.
class Parameters:
    """Configurable scenario parameters: W, R, L, T."""

    # Define init.
    def __init__(self, w=48.0, r=40.0, l=3, t=72.0):
        self.w = self._validate_positive("W", w)
        self.r = self._validate_positive("R", r)
        self.l = self._validate_non_negative_int("L", l)
        self.t = self._validate_positive("T", t)

    # Gestiona set w.
    def set_w(self, value):
        self.w = self._validate_positive("W", value)

    # Gestiona set r.
    def set_r(self, value):
        self.r = self._validate_positive("R", value)

    # Gestiona set l.
    def set_l(self, value):
        self.l = self._validate_non_negative_int("L", value)

    # Gestiona set t.
    def set_t(self, value):
        self.t = self._validate_positive("T", value)

    @staticmethod
    # Gestiona validate positive.
    def _validate_positive(name, value):
        if isinstance(value, bool):
            raise ValueError(f"{name} must be a positive number")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(
                f"{name} must be a positive number"
            ) from None
        if number <= 0:
            raise ValueError(f"{name} must be positive")
        return number

    @staticmethod
    # Gestiona validate non negative int.
    def _validate_non_negative_int(name, value):
        if isinstance(value, bool):
            raise ValueError(f"{name} must be a non-negative integer")
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise ValueError(
                f"{name} must be a non-negative integer"
            ) from None
        if number != value or number < 0:
            raise ValueError(f"{name} must be a non-negative integer")
        return number

    # === Persistence and copy ===

    # Gestiona to dict.
    def to_dict(self):
        return {"w": self.w, "r": self.r, "l": self.l, "t": self.t}

    @classmethod
    # Gestiona from dict.
    def from_dict(cls, data):
        for field in ("w", "r", "l", "t"):
            if field not in data:
                raise ValueError(f"Missing parameter '{field}'")
        return cls(w=data["w"], r=data["r"], l=data["l"], t=data["t"])

    # Gestiona copy.
    def copy(self):
        return Parameters(self.w, self.r, self.l, self.t)

    # Define repr.
    def __repr__(self):
        return f"Parameters(W={self.w}, R={self.r}, L={self.l}, T={self.t})"


# Representa Scenario y agrupa sus datos y operaciones.
class Scenario:
    """Scenario state: clock, parameters, map and stations."""

    # Define init.
    def __init__(
        self,
        map_obj,
        clock=None,
        parameters=None,
        stations=None
    ):
        self.map = map_obj
        self.clock = clock if clock is not None else Clock()
        self.parameters = (
            parameters if parameters is not None else Parameters()
        )
        self.stations = (
            stations if stations is not None else {}
        )

    # === Persistence and copy ===

    # Gestiona to dict.
    def to_dict(self):
        return {
            "clock": self.clock.to_dict(),
            "parameters": self.parameters.to_dict(),
            "map": self.map.to_dict(),
            "stations": {
                station_id: station.to_dict()
                for station_id, station in self.stations.items()
            },
        }

    @classmethod
    # Gestiona from dict.
    def from_dict(cls, data):
        from models.map import SeismicMap
        from models.station import Station

        if "clock" not in data:
            raise ValueError("The scenario must have 'clock'")
        if "parameters" not in data:
            raise ValueError("The scenario must have 'parameters'")
        if "map" not in data:
            raise ValueError("The scenario must have 'map'")

        stations = {
            station_id: Station.from_dict(station_data)
            for station_id, station_data in data.get("stations", {}).items()
        }

        return cls(
            map_obj=SeismicMap.from_dict(data["map"]),
            clock=Clock.from_dict(data["clock"]),
            parameters=Parameters.from_dict(data["parameters"]),
            stations=stations,
        )

    # Gestiona copy.
    def copy(self):
        stations = {
            station_id: station.copy()
            for station_id, station in self.stations.items()
        }

        return Scenario(
            map_obj=self.map.copy(),
            clock=self.clock.copy(),
            parameters=self.parameters.copy(),
            stations=stations,
        )

    # Define repr.
    def __repr__(self):
        return f"Scenario({self.clock}, {self.parameters})"