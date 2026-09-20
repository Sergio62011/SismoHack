from datetime import datetime


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

    """convertir objeto en texto para que puedas verlo, depurarlo e imprimirlo de forma útil."""
    def __repr__(self):
        return (
            f"Reporte(id={self.id_evento}, M={self.magnitud}, "
            f"revision={self.revision}, estacion={self.estacion})"
        )

