# models/report.py
from datetime import datetime, timezone


class Reporte:
    """Incoming station report before the system decides what to do with it."""

    def __init__(
        self,
        id_evento: int,
        magnitud: float,
        profundidad: float,
        x: float,
        y: float,
        fecha_hora: datetime,
        revision: int,
        estacion: str,
    ):
        self.id_evento = id_evento
        self.magnitud = magnitud
        self.profundidad = profundidad
        self.x = x
        self.y = y
        self.fecha_hora = fecha_hora
        self.revision = revision
        self.estacion = estacion

    # === Persistencia y copia ===

    def to_dict(self):
        return {
            "id_evento": self.id_evento,
            "magnitud": self.magnitud,
            "profundidad": self.profundidad,
            "x": self.x,
            "y": self.y,
            "fecha_hora": self.fecha_hora.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "revision": self.revision,
            "estacion": self.estacion,
        }

    @classmethod
    def from_dict(cls, data):
        fecha = datetime.strptime(
            data["fecha_hora"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        return cls(
            id_evento=data["id_evento"],
            magnitud=data["magnitud"],
            profundidad=data["profundidad"],
            x=data["x"],
            y=data["y"],
            fecha_hora=fecha,
            revision=data["revision"],
            estacion=data["estacion"],
        )

    def copia(self):
        return Reporte(
            self.id_evento, self.magnitud, self.profundidad,
            self.x, self.y, self.fecha_hora, self.revision, self.estacion,
        )

    def __repr__(self):
        return (
            f"Reporte(id={self.id_evento}, M={self.magnitud}, "
            f"revision={self.revision}, estacion={self.estacion})"
        )