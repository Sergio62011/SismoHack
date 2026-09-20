"""Business rules for the active seismic-event catalog."""

from collections import deque
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
        self._historicos = {}
        self.ids_eliminados = set()
        self.cola_reportes = deque()
        self.ultimas_rotaciones = []
        self.ultimo_reporte_procesado = None
        self.metricas = {
            "correcciones_aceptadas": 0,
            "reportes_descartados": 0,
            "conflictos": 0,
            "confirmaciones": 0,
            "creados_por_reporte": 0,
            "reactivados": 0,
            "archivos_masivos": 0,
            "eventos_archivados": 0,
        }

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

    def consultar_evento(self, id_evento):
        """Returns an event and its location: activo, archivado or eliminado."""
        event_id = self._validar_id(id_evento)

        if event_id in self._eventos_activos:
            return {"estado": "activo", "evento": self._eventos_activos[event_id]}
        if event_id in self._historicos:
            return {"estado": "archivado", "evento": self._historicos[event_id]}
        if event_id in self.ids_eliminados:
            return {"estado": "eliminado", "evento": None}

        return {"estado": "desconocido", "evento": None}

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
        rotaciones = list(self.avl.rotaciones_ultima_operacion)

        self._aplicar_datos(evento, datos)
        evento.revision += 1
        evento.estado = "pendiente"
        self.mapa.asignar_zona_a_evento(evento)

        self.avl.insert(evento)
        rotaciones.extend(self.avl.rotaciones_ultima_operacion)
        self.ultimas_rotaciones = rotaciones
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

    def encolar_reporte(self, reporte):
        """Adds one report to the pending FIFO queue."""
        self.cola_reportes.append(reporte)

    def hay_reportes_pendientes(self):
        return len(self.cola_reportes) > 0

    def cantidad_reportes_pendientes(self):
        return len(self.cola_reportes)

    def procesar_siguiente_reporte(self):
        """Processes the oldest pending report in FIFO order."""
        if not self.hay_reportes_pendientes():
            return self._resultado(
                "cola_vacia",
                "No hay reportes pendientes",
                None,
                rotaciones=[],
            )

        reporte = self.cola_reportes.popleft()
        self.ultimo_reporte_procesado = reporte
        resultado = self.procesar_reporte(reporte)
        resultado["reporte"] = reporte
        resultado["pendientes_restantes"] = self.cantidad_reportes_pendientes()
        return resultado

    def procesar_continuo(self):
        """Processes all pending reports. A future GUI can add visual pauses."""
        resultados = []

        while self.hay_reportes_pendientes():
            resultados.append(self.procesar_siguiente_reporte())

        return resultados

    def procesar_reporte(self, reporte):
        """Applies the rules for new, correction, confirmation and rejection."""
        event_id = self._validar_id(reporte.id_evento)
        revision = self._validar_revision(reporte.revision)
        estacion = self._validar_estacion(reporte.estacion)
        datos = self._validar_datos(
            reporte.magnitud,
            reporte.profundidad,
            reporte.x,
            reporte.y,
            reporte.fecha_hora,
        )

        if event_id in self.ids_eliminados:
            self.metricas["reportes_descartados"] += 1
            return self._resultado(
                "rechazado",
                f"El evento {event_id} fue eliminado y no puede reactivarse",
                None,
                rotaciones=[],
            )

        archivado = self._historicos.get(event_id)
        if archivado is not None:
            if revision > archivado.revision:
                self._aplicar_datos(archivado, datos)
                archivado.revision = revision
                archivado.estado = "pendiente"
                archivado.ubicacion = "activo"
                archivado.estaciones.add(estacion)
                self.mapa.asignar_zona_a_evento(archivado)

                self.avl.insert(archivado)
                self._eventos_activos[event_id] = archivado
                del self._historicos[event_id]
                self.metricas["reactivados"] += 1
                return self._resultado(
                    "reactivado",
                    f"Evento {event_id} reactivado desde historico",
                    archivado,
                )

            self.metricas["reportes_descartados"] += 1
            return self._resultado(
                "archivado_ignorado",
                f"Evento {event_id} archivado; el reporte no lo reactiva",
                archivado,
                rotaciones=[],
            )

        evento = self._eventos_activos.get(event_id)

        if evento is None:
            nuevo = Evento(
                id_evento=event_id,
                magnitud=datos["magnitud"],
                profundidad=datos["profundidad"],
                x=datos["x"],
                y=datos["y"],
                fecha_hora=datos["fecha_hora"],
                revision=revision,
                estado="pendiente",
            )
            nuevo.estaciones.add(estacion)
            self.mapa.asignar_zona_a_evento(nuevo)

            self.avl.insert(nuevo)
            self._eventos_activos[event_id] = nuevo
            self.metricas["creados_por_reporte"] += 1
            return self._resultado(
                "creado",
                f"Evento {event_id} creado desde reporte",
                nuevo,
            )

        if revision > evento.revision:
            clave_anterior = evento.calcular_clave()
            self.avl.delete(clave_anterior)
            rotaciones = list(self.avl.rotaciones_ultima_operacion)

            self._aplicar_datos(evento, datos)
            evento.revision = revision
            evento.estado = "pendiente"
            evento.estaciones.add(estacion)
            self.mapa.asignar_zona_a_evento(evento)

            self.avl.insert(evento)
            rotaciones.extend(self.avl.rotaciones_ultima_operacion)
            self.metricas["correcciones_aceptadas"] += 1
            return self._resultado(
                "corregido",
                f"Evento {event_id} corregido con una revision mayor",
                evento,
                rotaciones=rotaciones,
            )

        if revision == evento.revision:
            if self._datos_iguales(evento, datos):
                evento.estaciones.add(estacion)
                self.metricas["confirmaciones"] += 1
                return self._resultado(
                    "confirmado",
                    f"Evento {event_id} confirmado por {estacion}",
                    evento,
                    rotaciones=[],
                )

            self.metricas["conflictos"] += 1
            return self._resultado(
                "conflicto",
                "Reporte rechazado: misma revision con datos distintos",
                evento,
                rotaciones=[],
            )

        self.metricas["reportes_descartados"] += 1
        return self._resultado(
            "antiguo",
            f"Reporte descartado: revision {revision} menor que {evento.revision}",
            evento,
            rotaciones=[],
        )

    def _obtener_activo(self, id_evento):
        event_id = self._validar_id(id_evento)
        evento = self._eventos_activos.get(event_id)
        if evento is None:
            raise ValueError(f"No existe un evento activo con ID {event_id}")
        return evento

    @staticmethod
    def _datos_iguales(evento, datos):
        return (
            round(evento.magnitud, 1) == round(datos["magnitud"], 1)
            and round(evento.profundidad, 1) == round(datos["profundidad"], 1)
            and round(evento.x, 1) == round(datos["x"], 1)
            and round(evento.y, 1) == round(datos["y"], 1)
            and evento.fecha_hora == datos["fecha_hora"]
        )

    def _resultado(self, decision, mensaje, evento, rotaciones=None):
        if rotaciones is None:
            rotaciones = self.avl.rotaciones_ultima_operacion

        return {
            "decision": decision,
            "mensaje": mensaje,
            "evento": evento,
            "rotaciones": list(rotaciones),
        }

    @staticmethod
    def _aplicar_datos(evento, datos):
        evento.magnitud = datos["magnitud"]
        evento.profundidad = datos["profundidad"]
        evento.x = datos["x"]
        evento.y = datos["y"]
        evento.fecha_hora = datos["fecha_hora"]

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

    @staticmethod
    def _validar_revision(revision):
        if isinstance(revision, bool):
            raise ValueError("La revisión debe ser un entero positivo")
        try:
            numero_revision = int(revision)
        except (TypeError, ValueError) as error:
            raise ValueError("La revisión debe ser un entero positivo") from error

        if numero_revision != revision:
            raise ValueError("La revisión debe ser un entero positivo")
        if numero_revision <= 0:
            raise ValueError("La revisión debe ser un entero positivo")
        return numero_revision

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
