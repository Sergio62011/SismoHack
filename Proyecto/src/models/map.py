class Zone:
    """Represents a rectangular zone inside the simulated map."""

    def __init__(self, name, x_min, y_min, x_max, y_max, populated):
        self.name = name
        self.x_min = float(x_min)
        self.y_min = float(y_min)
        self.x_max = float(x_max)
        self.y_max = float(y_max)
        self.populated = bool(populated)

    def contains_point(self, x, y):
        """Returns True when the point is inside the zone or on its border."""
        return (
            self.x_min <= x <= self.x_max
            and self.y_min <= y <= self.y_max
        )

    def symbol(self):
        return "P" if self.populated else "N"

    # === Persistence and copy ===

    def to_dict(self):
        return {
            "name": self.name,
            "x_min": self.x_min,
            "y_min": self.y_min,
            "x_max": self.x_max,
            "y_max": self.y_max,
            "populated": self.populated,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            data["name"],
            data["x_min"], data["y_min"],
            data["x_max"], data["y_max"],
            data["populated"],
        )

    def copy(self):
        return Zone(
            self.name, self.x_min, self.y_min,
            self.x_max, self.y_max, self.populated,
        )

    def __repr__(self):
        kind = "populated" if self.populated else "not populated"
        return f"Zone({self.name}, {kind})"


class SeismicMap:
    """Simple matrix map for zones and seismic events."""

    def __init__(self, width_km=1000, height_km=1000, rows=10, columns=10):
        self.width_km = width_km
        self.height_km = height_km
        self.rows = rows
        self.columns = columns
        self.zones = []

    def add_zone(self, zone):
        self.zones.append(zone)

    def zones_of_point(self, x, y):
        return [
            zone
            for zone in self.zones
            if zone.contains_point(float(x), float(y))
        ]

    def is_in_populated_zone(self, x, y):
        zones_of_point = self.zones_of_point(x, y)
        return any(zone.populated for zone in zones_of_point)

    def assign_zone_to_event(self, event):
        event.in_populated_zone = self.is_in_populated_zone(event.x, event.y)
        event.recalculate_priority()

    def coordinate_to_cell(self, x, y):
        column = int((float(x) / self.width_km) * self.columns)
        row_from_bottom = int((float(y) / self.height_km) * self.rows)

        column = min(max(column, 0), self.columns - 1)
        row_from_bottom = min(max(row_from_bottom, 0), self.rows - 1)

        row = (self.rows - 1) - row_from_bottom
        return row, column

    def empty_matrix(self):
        return [["." for _ in range(self.columns)] for _ in range(self.rows)]

    def zones_matrix(self):
        matrix = self.empty_matrix()
        for row in range(self.rows):
            for column in range(self.columns):
                x, y = self._cell_center(row, column)
                zones = self.zones_of_point(x, y)
                if any(zone.populated for zone in zones):
                    matrix[row][column] = "P"
                elif len(zones) > 0:
                    matrix[row][column] = "N"
        return matrix

    def matrix_with_events(self, events):
        matrix = self.zones_matrix()
        for event in events:
            row, column = self.coordinate_to_cell(event.x, event.y)
            matrix[row][column] = "E"
        return matrix

    def print_matrix(self, matrix):
        print(
            "Legend: . = empty | P = populated zone | "
            "N = non-populated zone | E = event"
        )
        for row in matrix:
            print(" ".join(row))

    def _cell_center(self, row, column):
        cell_width = self.width_km / self.columns
        cell_height = self.height_km / self.rows
        x = (column + 0.5) * cell_width
        row_from_bottom = (self.rows - 1) - row
        y = (row_from_bottom + 0.5) * cell_height
        return x, y

    # === Persistence and copy ===

    def to_dict(self):
        return {
            "width_km": self.width_km,
            "height_km": self.height_km,
            "rows": self.rows,
            "columns": self.columns,
            "zones": [z.to_dict() for z in self.zones],
        }

    @classmethod
    def from_dict(cls, data):
        smap = cls(
            width_km=data["width_km"],
            height_km=data["height_km"],
            rows=data["rows"],
            columns=data["columns"],
        )
        for z in data["zones"]:
            smap.add_zone(Zone.from_dict(z))
        return smap

    def copy(self):
        new = SeismicMap(
            self.width_km, self.height_km, self.rows, self.columns
        )
        for z in self.zones:
            new.add_zone(z.copy())
        return new