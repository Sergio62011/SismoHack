"""Business rules for the active seismic-event catalog."""

from datetime import datetime, timezone
from math import isfinite

from models.event import Evento
from models.map import MapaSismico
from structure.avl import AVL


class SistemaSismico:
    """Coordinates event operations without depending on a user interface.

    The AVL remains the storage structure for active events. The ID index only
    provides direct identity lookup because an ID alone cannot navigate an AVL
    ordered by (priority, magnitude, id).
    """

    def __init__(self, mapa=None):
        self.avl = AVL()
        self.mapa = mapa if mapa is not None else MapaSismico()
        self._eventos_activos = {}
        self.ids_eliminados = set()

    def crear_evento(
        self,
        id_evento,
        magnitud,
        profundidad,
        x,
        y,
        fecha_hora,
        estacion,
    ):
        """Creates and inserts one valid active event as a single operation."""
        event_id = self._validar_id(id_evento)
        if event_id in self._eventos_activos:
            raise ValueError(f"El evento {event_id} ya está activo")
        if event_id in self.ids_eliminados:
            raise ValueError(
                f"El identificador {event_id} fue eliminado y no se puede reutilizar"
            )

        datos = self._validar_datos(magnitud, profundidad, x, y, fecha_hora)
        estacion = self._validar_estacion(estacion)

        evento = Evento(
            id_evento=event_id,
            magnitud=datos["magnitud"],
            profundidad=datos["profundidad"],
            x=datos["x"],
            y=datos["y"],
            fecha_hora=datos["fecha_hora"],
            revision=1,
            estado="pendiente",
        )
        evento.estaciones.add(estacion)
        self.mapa.asignar_zona_a_evento(evento)

        self.avl.insert(evento)
        self._eventos_activos[event_id] = evento
        return evento

    def buscar_por_id(self, id_evento):
        """Returns the active event with this ID, or None if it is absent."""
        return self._eventos_activos.get(self._validar_id(id_evento))

    def corregir_evento(
        self,
        id_evento,
        *,
        magnitud=None,
        profundidad=None,
        x=None,
        y=None,
        fecha_hora=None,
    ):
        """Applies a validated correction and preserves the event identity.

        If priority or magnitude changes, the event is removed using its former
        key before its data changes and is then inserted with its new key.
        """
        evento = self._obtener_activo(id_evento)
        datos = self._validar_datos(
            evento.magnitud if magnitud is None else magnitud,
            evento.profundidad if profundidad is None else profundidad,
            evento.x if x is None else x,
            evento.y if y is None else y,
            evento.fecha_hora if fecha_hora is None else fecha_hora,
        )

        clave_anterior = evento.calcular_clave()
        self.avl.delete(clave_anterior)

        evento.magnitud = datos["magnitud"]
        evento.profundidad = datos["profundidad"]
        evento.x = datos["x"]
        evento.y = datos["y"]
        evento.fecha_hora = datos["fecha_hora"]
        evento.revision += 1
        evento.estado = "pendiente"
        self.mapa.asignar_zona_a_evento(evento)

        self.avl.insert(evento)
        return evento

    def marcar_revisado(self, id_evento):
        """Marks an active event as reviewed without changing its AVL key."""
        evento = self._obtener_activo(id_evento)
        evento.estado = "revisado"
        return evento

    def eliminar_evento(self, id_evento):
        """Removes only the selected active event and retires its identifier."""
        event_id = self._validar_id(id_evento)
        evento = self._obtener_activo(event_id)
        self.avl.delete(evento.calcular_clave())
        del self._eventos_activos[event_id]
        self.ids_eliminados.add(event_id)
        evento.ubicacion = "eliminado"
        return evento

    def _obtener_activo(self, id_evento):
        event_id = self._validar_id(id_evento)
        evento = self._eventos_activos.get(event_id)
        if evento is None:
            raise ValueError(f"No existe un evento activo con ID {event_id}")
        return evento

    @staticmethod
    def _validar_id(id_evento):
        if isinstance(id_evento, bool):
            raise ValueError("El identificador debe ser un entero")

        if isinstance(id_evento, str):
            texto = id_evento.strip()
            if not texto.isdigit():
                raise ValueError("El identificador debe ser un entero")
            event_id = int(texto)
        else:
            try:
                event_id = int(id_evento)
            except (TypeError, ValueError) as error:
                raise ValueError("El identificador debe ser un entero") from error

            if event_id != id_evento:
                raise ValueError("El identificador debe ser un entero")

        if not 1 <= event_id <= 999999:
            raise ValueError("El identificador debe estar entre 1 y 999999")
        return event_id

    @staticmethod
    def _validar_estacion(estacion):
        if not isinstance(estacion, str) or not estacion.strip():
            raise ValueError("La estación es obligatoria")
        return estacion.strip()

    @classmethod
    def _validar_datos(cls, magnitud, profundidad, x, y, fecha_hora):
        datos = {
            "magnitud": cls._validar_decimal("La magnitud", magnitud, -2.0, 10.0),
            "profundidad": cls._validar_decimal(
                "La profundidad", profundidad, 0.0, 700.0
            ),
            "x": cls._validar_decimal("La coordenada x", x, 0.0, 1000.0),
            "y": cls._validar_decimal("La coordenada y", y, 0.0, 1000.0),
        }

        if not isinstance(fecha_hora, datetime):
            raise ValueError("La fecha y hora debe ser un datetime")
        if fecha_hora.tzinfo is None or fecha_hora.utcoffset() is None:
            raise ValueError("La fecha y hora debe incluir zona horaria UTC")

        datos["fecha_hora"] = fecha_hora.astimezone(timezone.utc)
        return datos

    @staticmethod
    def _validar_decimal(nombre, valor, minimo, maximo):
        if isinstance(valor, bool):
            raise ValueError(f"{nombre} debe ser un número")
        try:
            numero = float(valor)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{nombre} debe ser un número") from error

        if not isfinite(numero) or not minimo <= numero <= maximo:
            raise ValueError(f"{nombre} debe estar entre {minimo} y {maximo}")
        if round(numero, 1) != numero:
            raise ValueError(f"{nombre} admite como máximo un decimal")
        return numero