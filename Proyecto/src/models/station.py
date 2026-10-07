# Módulo station: contiene la lógica relacionada con station.
# Representa Station y agrupa sus datos y operaciones.
class Station:
    """Represents a seismic station of the scenario."""

    # Define init.
    def __init__(self, station_id: str, name: str):
        if not isinstance(station_id, str) or not station_id.strip():
            raise ValueError("The station ID cannot be empty.")

        if not isinstance(name, str) or not name.strip():
            raise ValueError("The station name cannot be empty.")

        self.station_id = station_id.strip()
        self.name = name.strip()

    # Gestiona to dict.
    def to_dict(self):
        return {
            "station_id": self.station_id,
            "name": self.name,
        }

    @classmethod
    # Gestiona from dict.
    def from_dict(cls, data):
        return cls(
            station_id=data["station_id"],
            name=data["name"],
        )

    # Gestiona copy.
    def copy(self):
        return Station(
            self.station_id,
            self.name,
        )

    # Define repr.
    def __repr__(self):
        return (
            f"Station(id={self.station_id}, "
            f"name={self.name})"
        )