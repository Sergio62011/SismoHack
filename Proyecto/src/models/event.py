from datetime import datetime, timezone
from typing import Set, Optional


class Evento:
    """Representa un evento sísmico con todos sus datos."""
    
    def __init__(
        self,
        id_evento: int,
        magnitud: float,
        profundidad: float,
        x: float,
        y: float,
        fecha_hora: datetime,
        revision: int = 1,
        estado: str = "pendiente",
        zona_poblada: bool = False,
    ):
        self.id_evento = int(id_evento)
        self.magnitud = float(magnitud)
        self.profundidad = float(profundidad)
        self.x = float(x)
        self.y = float(y)
        self.fecha_hora = fecha_hora
        
        self.revision = int(revision)
        self.estado = estado
        self.estaciones: Set[str] = set()
        self.en_zona_poblada = zona_poblada

        self.prioridad = self._calcular_prioridad()
        self.acceso_costoso = False

        self.ubicacion = "activo"

        self.referencia: Optional[int] = None
        self.referenciado_por: Set[int] = set()

    # === Prioridad ===

    def _calcular_prioridad(self) -> int:
        if self.magnitud >= 6.0:
            return 3
        if (
            self.magnitud >= 4.5
            and self.profundidad <= 30.0
            and self.en_zona_poblada
        ):
            return 3
        if self.magnitud >= 4.5:
            return 2
        return 1

    def recalcular_prioridad(self):
        self.prioridad = self._calcular_prioridad()

    # === Clave ===

    def calcular_clave(self) -> tuple:
        return (self.prioridad, self.magnitud, self.id_evento)

    # === Comparación ===

    def __lt__(self, otro):
        return self.calcular_clave() < otro.calcular_clave()

    def __eq__(self, otro):
        return self.calcular_clave() == otro.calcular_clave()

    def __hash__(self):
        return hash(self.id_evento)

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
            "estado": self.estado,
            "estaciones": sorted(self.estaciones),
            "en_zona_poblada": self.en_zona_poblada,
            "prioridad": self.prioridad,
            "acceso_costoso": self.acceso_costoso,
            "ubicacion": self.ubicacion,
            "referencia": self.referencia,
            "referenciado_por": sorted(self.referenciado_por),
        }

    @classmethod
    def from_dict(cls, data):
        fecha = datetime.strptime(
            data["fecha_hora"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        evento = cls(
            id_evento=data["id_evento"],
            magnitud=data["magnitud"],
            profundidad=data["profundidad"],
            x=data["x"],
            y=data["y"],
            fecha_hora=fecha,
            revision=data["revision"],
            estado=data["estado"],
            zona_poblada=data["en_zona_poblada"],
        )
        evento.estaciones = set(data.get("estaciones", []))
        evento.acceso_costoso = bool(data.get("acceso_costoso", False))
        evento.ubicacion = data.get("ubicacion", "activo")
        evento.referencia = data.get("referencia")
        evento.referenciado_por = set(data.get("referenciado_por", []))
        # Recalcular prioridad para asegurar consistencia
        evento.recalcular_prioridad()
        return evento

    def copia(self):
        nuevo = Evento(
            id_evento=self.id_evento,
            magnitud=self.magnitud,
            profundidad=self.profundidad,
            x=self.x,
            y=self.y,
            fecha_hora=self.fecha_hora,
            revision=self.revision,
            estado=self.estado,
            zona_poblada=self.en_zona_poblada,
        )
        nuevo.estaciones = set(self.estaciones)
        nuevo.acceso_costoso = self.acceso_costoso
        nuevo.ubicacion = self.ubicacion
        nuevo.referencia = self.referencia
        nuevo.referenciado_por = set(self.referenciado_por)
        nuevo.recalcular_prioridad()
        return nuevo

    def __repr__(self):
        return (
            f"Evento(id={self.id_evento}, M={self.magnitud}, "
            f"H={self.profundidad}, P={self.prioridad}, "
            f"clave={self.calcular_clave()})"
        )