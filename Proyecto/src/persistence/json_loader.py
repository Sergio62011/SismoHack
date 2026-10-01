"""Strict JSON loaders for SismoLab structural and insertion modes."""

import json
from collections import deque
from pathlib import Path

from models.escenario import Escenario
from models.event import Evento
from models.report import Reporte
from services.sistema_sismico import SistemaSismico
from structure.avl import AVL
from structure.bst import BST
from structure.node import Node


class ErrorJsonPersistencia(ValueError):
    """Raised when a JSON file cannot safely become a system state."""


class JsonLoader:
    """Loads JSON only after every required invariant has been verified."""

    FORMAT = "SismoLab-AVL"
    SCHEMA_VERSION = 1
    METRICAS_REQUERIDAS = {
        "correcciones_aceptadas",
        "reportes_descartados",
        "conflictos",
        "confirmaciones",
        "creados_por_reporte",
        "reactivados",
        "archivos_masivos",
        "eventos_archivados",
    }
   
    COSTO_RECUPERACION_REQUERIDAS = {
        "altura_antes",
        "altura_despues",
        "rotaciones",
        "giros",
        "pasadas",
        "nodos_visitados",
    }


    @classmethod
    def cargar_topologia(cls, ruta, sistema_actual=None):
        """Restores the stored AVL links exactly as they appear in JSON.

        [FIX] Si se recibe un sistema_actual, se toma un snapshot y se
        restaura si cualquier validación o construcción falla. Esto
        garantiza que la carga sea completa o no se aplique.
        """
        datos = cls._leer_archivo(ruta)
        cls._validar_encabezado(datos)

        snapshot = None
        if sistema_actual is not None:
            snapshot = sistema_actual._snapshot()

        try:
            escenario = cls._cargar_escenario(datos)
            ejecucion = cls._cargar_ejecucion(datos.get("execution"))
            arbol, activos = cls._construir_arbol_topologico(
                datos.get("active_tree"), escenario, ejecucion["stress_mode"]
            )
            historicos = cls._cargar_historicos(
                datos.get("historical_events"), escenario, set(activos)
            )
            eliminados = cls._cargar_eliminados(
                datos.get("removed_ids"), set(activos), set(historicos)
            )
            # [FIX] Validar que ningún evento apunte a un eliminado
            cls._validar_asociaciones(
                {**activos, **historicos}, eliminados
            )
            cola = cls._cargar_cola(datos.get("report_queue"), escenario)
            ultimo_reporte = cls._cargar_ultimo_reporte(
                datos.get("last_processed_report"), escenario
            )
            # [FIX] Validar coherencia de acceso costoso según L
            cls._validar_acceso_costoso(
                arbol.root, escenario.parametros.l
            )
            # [FIX] Validar que el último reporte procesado no siga en cola
            cls._validar_ultimo_reporte_fuera_de_cola(ultimo_reporte, cola)

            sistema = SistemaSismico(escenario)
            sistema.avl = arbol
            sistema.avl.rotaciones_realizadas = ejecucion["rotations_total"]
            sistema._eventos_activos = activos
            sistema._historicos = historicos
            sistema.ids_eliminados = eliminados
            sistema.cola_reportes = cola
            sistema.ultimo_reporte_procesado = ultimo_reporte
            sistema.metricas = ejecucion["metrics"]
            sistema.ultimas_rotaciones = ejecucion["last_rotations"]
            sistema.ultimo_costo_recuperacion = ejecucion["last_recovery_cost"]
            return sistema

        except Exception:
            if sistema_actual is not None and snapshot is not None:
                sistema_actual._restaurar(snapshot)
            raise

    @classmethod
    def cargar_por_inserciones(cls, ruta):
        """Creates an AVL and a plain BST with the same event sequence.

        [FIX] Fuerza modo normal durante toda la carga, tal como exige
        el enunciado ('Esta carga se realiza con balanceo activo').
        """
        datos = cls._leer_archivo(ruta)
        cls._validar_encabezado(datos)
        escenario = cls._cargar_escenario(datos)
        secuencia = datos.get("insertion_events")
        if not isinstance(secuencia, list):
            raise ErrorJsonPersistencia(
                "La carga por inserciones requiere la lista 'insertion_events'"
            )

        sistema = SistemaSismico(escenario)
        sistema.avl.modo_estres = False  # [FIX] Forzar modo normal
        bst = BST()
        ids = set()
        eventos = []
        for posicion, datos_evento in enumerate(secuencia, start=1):
            evento = cls._crear_evento(
                datos_evento, escenario, "activo", f"insertion_events[{posicion}]"
            )
            if evento.id_evento in ids:
                raise ErrorJsonPersistencia(
                    f"Identificador duplicado en la secuencia: {evento.id_evento}"
                )
            ids.add(evento.id_evento)
            eventos.append(evento)

        for evento in eventos:
            sistema.avl.insert(evento)
            sistema._eventos_activos[evento.id_evento] = evento
            bst.insert(evento.copia())

        return sistema, bst

    

    @classmethod
    def _leer_archivo(cls, ruta):
        archivo = Path(ruta)
        if not archivo.is_file():
            raise ErrorJsonPersistencia("El archivo JSON seleccionado no existe")
        try:
            with archivo.open("r", encoding="utf-8") as entrada:
                datos = json.load(entrada)
        except json.JSONDecodeError as error:
            raise ErrorJsonPersistencia(
                f"JSON inválido en línea {error.lineno}: {error.msg}"
            ) from error
        except OSError as error:
            raise ErrorJsonPersistencia(
                f"No se pudo leer el archivo: {error}"
            ) from error
        if not isinstance(datos, dict):
            raise ErrorJsonPersistencia("La raíz del JSON debe ser un objeto")
        return datos

    @classmethod
    def _validar_encabezado(cls, datos):
        if datos.get("format") != cls.FORMAT:
            raise ErrorJsonPersistencia("El archivo no pertenece a SismoLab-AVL")
        if datos.get("schema_version") != cls.SCHEMA_VERSION:
            raise ErrorJsonPersistencia("La versión del esquema JSON no es compatible")

  

    @classmethod
    def _cargar_escenario(cls, datos):
        escenario_datos = datos.get("scenario")
        if not isinstance(escenario_datos, dict):
            raise ErrorJsonPersistencia("Falta el objeto 'scenario'")
        try:
            return Escenario.from_dict(escenario_datos)
        except (KeyError, TypeError, ValueError) as error:
            raise ErrorJsonPersistencia(
                f"Escenario inválido: {error}"
            ) from error

    @classmethod
    def _cargar_ejecucion(cls, datos_ejecucion):
        if not isinstance(datos_ejecucion, dict):
            raise ErrorJsonPersistencia("Falta el objeto 'execution'")
        cls._requerir_campos(
            datos_ejecucion,
            {"stress_mode", "rotations_total", "last_rotations",
             "last_recovery_cost", "metrics"},
            "execution",
        )
        if not isinstance(datos_ejecucion["stress_mode"], bool):
            raise ErrorJsonPersistencia("'execution.stress_mode' debe ser booleano")
        rotaciones_total = datos_ejecucion["rotations_total"]
        if (isinstance(rotaciones_total, bool)
                or not isinstance(rotaciones_total, int)
                or rotaciones_total < 0):
            raise ErrorJsonPersistencia("'execution.rotations_total' es inválido")
        rotaciones = datos_ejecucion["last_rotations"]
        if (not isinstance(rotaciones, list)
                or any(r not in {"LL", "RR", "LR", "RL"} for r in rotaciones)):
            raise ErrorJsonPersistencia("'execution.last_rotations' es inválido")
        metricas = datos_ejecucion["metrics"]
        if (not isinstance(metricas, dict)
                or set(metricas) != cls.METRICAS_REQUERIDAS):
            raise ErrorJsonPersistencia("Las métricas almacenadas no son válidas")
        for nombre, valor in metricas.items():
            if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
                raise ErrorJsonPersistencia(f"Métrica inválida: {nombre}")

        # [FIX] Validar estructura completa de last_recovery_cost
        costo = datos_ejecucion["last_recovery_cost"]
        if costo is not None:
            if not isinstance(costo, dict):
                raise ErrorJsonPersistencia(
                    "'execution.last_recovery_cost' debe ser objeto o null"
                )
            faltantes = cls.COSTO_RECUPERACION_REQUERIDAS - set(costo)
            if faltantes:
                raise ErrorJsonPersistencia(
                    f"'last_recovery_cost' incompleto: {sorted(faltantes)}"
                )
            if not isinstance(costo["rotaciones"], list):
                raise ErrorJsonPersistencia(
                    "'last_recovery_cost.rotaciones' debe ser lista"
                )
            for campo in ("altura_antes", "altura_despues", "giros",
                          "pasadas", "nodos_visitados"):
                valor = costo[campo]
                if isinstance(valor, bool) or not isinstance(valor, int):
                    raise ErrorJsonPersistencia(
                        f"'last_recovery_cost.{campo}' debe ser entero"
                    )

        return {
            "stress_mode": datos_ejecucion["stress_mode"],
            "rotations_total": rotaciones_total,
            "last_rotations": list(rotaciones),
            "last_recovery_cost": costo,
            "metrics": dict(metricas),
        }

    # Topología

    @classmethod
    def _construir_arbol_topologico(cls, datos_arbol, escenario, modo_estres):
        if not isinstance(datos_arbol, dict):
            raise ErrorJsonPersistencia("Falta el objeto 'active_tree'")
        raiz_id = datos_arbol.get("root")
        nodos_datos = datos_arbol.get("nodes")
        if not isinstance(nodos_datos, list):
            raise ErrorJsonPersistencia("'active_tree.nodes' debe ser una lista")
        if raiz_id is None and nodos_datos:
            raise ErrorJsonPersistencia("Un árbol con nodos debe tener raíz")
        if raiz_id is not None and not nodos_datos:
            raise ErrorJsonPersistencia("Una raíz requiere al menos un nodo")

        nodos = {}
        enlaces = {}
        activos = {}
        for posicion, datos_nodo in enumerate(nodos_datos, start=1):
            if not isinstance(datos_nodo, dict):
                raise ErrorJsonPersistencia(
                    f"active_tree.nodes[{posicion}] debe ser un objeto"
                )
            cls._requerir_campos(
                datos_nodo,
                {"event", "left", "right", "height", "balance_factor"},
                f"active_tree.nodes[{posicion}]",
            )
            evento = cls._crear_evento(
                datos_nodo["event"], escenario, "activo",
                f"active_tree.nodes[{posicion}].event",
            )
            event_id = evento.id_evento
            if event_id in nodos:
                raise ErrorJsonPersistencia(
                    f"El evento activo {event_id} aparece más de una vez"
                )
            altura = datos_nodo["height"]
            if isinstance(altura, bool) or not isinstance(altura, int) or altura < 0:
                raise ErrorJsonPersistencia(
                    f"La altura almacenada de {event_id} es inválida"
                )
            factor = datos_nodo["balance_factor"]
            if isinstance(factor, bool) or not isinstance(factor, int):
                raise ErrorJsonPersistencia(
                    f"El factor almacenado de {event_id} es inválido"
                )
            nodo = Node(evento)
            nodo.height = altura
            nodos[event_id] = nodo
            enlaces[event_id] = (datos_nodo["left"], datos_nodo["right"], factor)
            activos[event_id] = evento

        if raiz_id is None:
            arbol_vacio = AVL()
            arbol_vacio.modo_estres = modo_estres
            return arbol_vacio, activos

        cls._validar_id_referencia(raiz_id, nodos, "La raíz")

        padres = set()
        for event_id, (izquierda, derecha, _) in enlaces.items():
            for lado, hijo_id in (("izquierdo", izquierda), ("derecho", derecha)):
                if hijo_id is None:
                    continue
                cls._validar_id_referencia(
                    hijo_id, nodos, f"Hijo {lado} de {event_id}"
                )
                if hijo_id in padres:
                    raise ErrorJsonPersistencia(
                        f"El nodo {hijo_id} tiene más de un padre"
                    )
                padres.add(hijo_id)
            nodos[event_id].left = nodos.get(izquierda)
            nodos[event_id].right = nodos.get(derecha)
            if izquierda is not None:
                nodos[izquierda].parent = nodos[event_id]
            if derecha is not None:
                nodos[derecha].parent = nodos[event_id]

        if raiz_id in padres:
            raise ErrorJsonPersistencia("La raíz no puede tener padre")

        visitados = set()

        def recorrer(nodo):
            event_id = nodo.event.id_evento
            if event_id in visitados:
                raise ErrorJsonPersistencia("La topología contiene un ciclo")
            visitados.add(event_id)
            if nodo.left:
                recorrer(nodo.left)
            if nodo.right:
                recorrer(nodo.right)

        recorrer(nodos[raiz_id])
        if visitados != set(nodos):
            faltantes = sorted(set(nodos) - visitados)
            raise ErrorJsonPersistencia(
                f"Nodos activos fuera de la topología: {faltantes}"
            )

        cls._validar_bst_y_metadatos(nodos[raiz_id], enlaces, modo_estres)
        arbol = AVL()
        arbol.root = nodos[raiz_id]
        arbol.modo_estres = modo_estres
        return arbol, activos

    @classmethod
    def _validar_bst_y_metadatos(cls, raiz, enlaces, modo_estres):
        def recorrer(nodo, limite_inferior, limite_superior):
            clave = nodo.event.calcular_clave()
            if limite_inferior is not None and clave <= limite_inferior:
                raise ErrorJsonPersistencia(
                    f"El orden BST es inválido en el evento {nodo.event.id_evento}"
                )
            if limite_superior is not None and clave >= limite_superior:
                raise ErrorJsonPersistencia(
                    f"El orden BST es inválido en el evento {nodo.event.id_evento}"
                )
            altura_izquierda = (
                recorrer(nodo.left, limite_inferior, clave) if nodo.left else -1
            )
            altura_derecha = (
                recorrer(nodo.right, clave, limite_superior) if nodo.right else -1
            )
            altura = 1 + max(altura_izquierda, altura_derecha)
            factor = altura_izquierda - altura_derecha
            almacenado = enlaces[nodo.event.id_evento]
            if nodo.height != altura:
                raise ErrorJsonPersistencia(
                    f"Altura inconsistente en el evento {nodo.event.id_evento}"
                )
            if almacenado[2] != factor:
                raise ErrorJsonPersistencia(
                    f"Factor de balance inconsistente en el evento {nodo.event.id_evento}"
                )
            if not modo_estres and abs(factor) > 1:
                raise ErrorJsonPersistencia(
                    "Una topología desbalanceada requiere modo estrés"
                )
            return altura

        recorrer(raiz, None, None)

   
    @classmethod
    def _cargar_historicos(cls, datos_historicos, escenario, ids_activos):
        if not isinstance(datos_historicos, list):
            raise ErrorJsonPersistencia("'historical_events' debe ser una lista")
        historicos = {}
        for posicion, datos_evento in enumerate(datos_historicos, start=1):
            evento = cls._crear_evento(
                datos_evento, escenario, "archivado",
                f"historical_events[{posicion}]",
            )
            if evento.id_evento in ids_activos or evento.id_evento in historicos:
                raise ErrorJsonPersistencia(
                    f"El identificador {evento.id_evento} está duplicado"
                )
            historicos[evento.id_evento] = evento
        return historicos

    @classmethod
    def _cargar_eliminados(cls, datos_eliminados, ids_activos, ids_historicos):
        if not isinstance(datos_eliminados, list):
            raise ErrorJsonPersistencia("'removed_ids' debe ser una lista")
        eliminados = set()
        for identificador in datos_eliminados:
            event_id = cls._validar_entero_id(identificador, "Identificador eliminado")
            if event_id in eliminados:
                raise ErrorJsonPersistencia(
                    f"Identificador eliminado duplicado: {event_id}"
                )
            if event_id in ids_activos or event_id in ids_historicos:
                raise ErrorJsonPersistencia(
                    f"El identificador {event_id} está activo, histórico y eliminado"
                )
            eliminados.add(event_id)
        return eliminados

    @classmethod
    def _crear_evento(cls, datos, escenario, ubicacion, contexto):
        if not isinstance(datos, dict):
            raise ErrorJsonPersistencia(f"{contexto} debe ser un objeto")
        requeridos = {
            "id_evento", "magnitud", "profundidad", "x", "y", "fecha_hora",
            "revision", "estado", "estaciones", "en_zona_poblada", "prioridad",
            "acceso_costoso", "ubicacion", "referencia", "referenciado_por",
        }
        cls._requerir_campos(datos, requeridos, contexto)

        # [FIX] Capturar la prioridad almacenada ANTES de from_dict,
        # porque Evento.from_dict recalcula la prioridad y perderíamos
        # la capacidad de detectar inconsistencias en el JSON.
        prioridad_almacenada = datos["prioridad"]

        try:
            evento = Evento.from_dict(datos)
            SistemaSismico._validar_id(evento.id_evento)
            SistemaSismico._validar_revision(evento.revision)
            SistemaSismico._validar_datos(
                evento.magnitud, evento.profundidad,
                evento.x, evento.y, evento.fecha_hora,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ErrorJsonPersistencia(
                f"Evento inválido en {contexto}: {error}"
            ) from error

        if evento.fecha_hora > escenario.reloj.instante:
            raise ErrorJsonPersistencia(
                f"El evento {evento.id_evento} es posterior al reloj del escenario"
            )
        if evento.estado not in {"pendiente", "revisado"}:
            raise ErrorJsonPersistencia(
                f"Estado inválido en el evento {evento.id_evento}"
            )
        if evento.ubicacion != ubicacion:
            raise ErrorJsonPersistencia(
                f"Ubicación inválida en el evento {evento.id_evento}"
            )

        estaciones = datos["estaciones"]
        if (not isinstance(estaciones, list)
                or len(set(estaciones)) != len(estaciones)):
            raise ErrorJsonPersistencia(
                f"Estaciones inválidas en el evento {evento.id_evento}"
            )
        if any(estacion not in escenario.estaciones for estacion in estaciones):
            raise ErrorJsonPersistencia(
                f"El evento {evento.id_evento} referencia una estación inexistente"
            )

        en_zona = escenario.mapa.esta_en_zona_poblada(evento.x, evento.y)
        if evento.en_zona_poblada != en_zona:
            raise ErrorJsonPersistencia(
                f"Zona poblada inconsistente en el evento {evento.id_evento}"
            )

        # [FIX] Comparar contra la prioridad almacenada en el JSON, no
        # contra la que Evento.from_dict ya recalculó.
        if prioridad_almacenada != evento.prioridad:
            raise ErrorJsonPersistencia(
                f"Prioridad almacenada inconsistente en el evento "
                f"{evento.id_evento}: JSON={prioridad_almacenada}, "
                f"calculada={evento.prioridad}"
            )
        if not isinstance(datos["en_zona_poblada"], bool):
            raise ErrorJsonPersistencia(
                f"Zona poblada inválida en el evento {evento.id_evento}"
            )
        if not isinstance(datos["acceso_costoso"], bool):
            raise ErrorJsonPersistencia(
                f"Marca de acceso inválida en el evento {evento.id_evento}"
            )
        return evento

    # =========================================================
    # Reportes
    # =========================================================

    @classmethod
    def _cargar_cola(cls, datos_cola, escenario):
        if not isinstance(datos_cola, list):
            raise ErrorJsonPersistencia("'report_queue' debe ser una lista")
        cola = deque()
        for posicion, datos_reporte in enumerate(datos_cola, start=1):
            cola.append(cls._crear_reporte(
                datos_reporte, escenario, f"report_queue[{posicion}]"
            ))
        return cola

    @classmethod
    def _cargar_ultimo_reporte(cls, datos_reporte, escenario):
        if datos_reporte is None:
            return None
        return cls._crear_reporte(
            datos_reporte, escenario, "last_processed_report"
        )

    @classmethod
    def _crear_reporte(cls, datos, escenario, contexto):
        if not isinstance(datos, dict):
            raise ErrorJsonPersistencia(f"{contexto} debe ser un objeto")
        requeridos = {
            "id_evento", "magnitud", "profundidad", "x", "y", "fecha_hora",
            "revision", "estacion",
        }
        cls._requerir_campos(datos, requeridos, contexto)
        try:
            reporte = Reporte.from_dict(datos)
            SistemaSismico._validar_id(reporte.id_evento)
            SistemaSismico._validar_revision(reporte.revision)
            SistemaSismico._validar_datos(
                reporte.magnitud, reporte.profundidad,
                reporte.x, reporte.y, reporte.fecha_hora,
            )
            SistemaSismico._validar_estacion(reporte.estacion)
        except (KeyError, TypeError, ValueError) as error:
            raise ErrorJsonPersistencia(
                f"Reporte inválido en {contexto}: {error}"
            ) from error
        if reporte.estacion not in escenario.estaciones:
            raise ErrorJsonPersistencia(
                f"El reporte en {contexto} referencia una estación inexistente"
            )
        return reporte

    # =========================================================
    # Asociaciones
    # =========================================================

    @classmethod
    def _validar_asociaciones(cls, eventos, ids_eliminados=None):
        # [FIX] Validar que las referencias no apunten a eliminados
        ids_eliminados = ids_eliminados or set()

        for evento in eventos.values():
            referencia = evento.referencia
            if referencia is not None:
                if referencia in ids_eliminados:
                    raise ErrorJsonPersistencia(
                        f"El evento {evento.id_evento} referencia al eliminado "
                        f"{referencia}"
                    )
                if referencia not in eventos or referencia == evento.id_evento:
                    raise ErrorJsonPersistencia(
                        f"Referencia inválida en el evento {evento.id_evento}"
                    )
                if evento.id_evento not in eventos[referencia].referenciado_por:
                    raise ErrorJsonPersistencia(
                        f"Referencia no recíproca en el evento {evento.id_evento}"
                    )
            for referenciado in evento.referenciado_por:
                if referenciado in ids_eliminados:
                    raise ErrorJsonPersistencia(
                        f"El evento {evento.id_evento} es referenciado por el "
                        f"eliminado {referenciado}"
                    )
                if referenciado not in eventos:
                    raise ErrorJsonPersistencia(
                        f"Asociación inválida en el evento {evento.id_evento}"
                    )
                if eventos[referenciado].referencia != evento.id_evento:
                    raise ErrorJsonPersistencia(
                        f"Asociación no recíproca en el evento {evento.id_evento}"
                    )

        for evento in eventos.values():
            visitados = set()
            actual = evento
            while actual.referencia is not None:
                if actual.id_evento in visitados:
                    raise ErrorJsonPersistencia(
                        "Las asociaciones contienen un ciclo"
                    )
                visitados.add(actual.id_evento)
                actual = eventos[actual.referencia]

    @classmethod
    def _validar_ultimo_reporte_fuera_de_cola(cls, ultimo_reporte, cola):
        """[FIX] Un reporte ya procesado no debería seguir en la cola."""
        if ultimo_reporte is None:
            return
        for reporte in cola:
            if (
                reporte.id_evento == ultimo_reporte.id_evento
                and reporte.revision == ultimo_reporte.revision
                and reporte.estacion == ultimo_reporte.estacion
            ):
                raise ErrorJsonPersistencia(
                    f"El último reporte procesado ({ultimo_reporte.id_evento} "
                    f"rev {ultimo_reporte.revision}) sigue en la cola"
                )

    @classmethod
    def _validar_acceso_costoso(cls, raiz, limite_l):
        """[FIX] La marca de acceso costoso debe ser coherente con L y
        la profundidad del nodo dentro de la topología restaurada.
        """
        def recorrer(nodo, profundidad):
            if nodo is None:
                return
            esperado = (
                nodo.event.prioridad == 3 and profundidad > limite_l
            )
            if nodo.event.acceso_costoso != esperado:
                raise ErrorJsonPersistencia(
                    f"Marca de acceso costoso inconsistente en el evento "
                    f"{nodo.event.id_evento}: almacenada="
                    f"{nodo.event.acceso_costoso}, esperada={esperado} "
                    f"(profundidad={profundidad}, L={limite_l})"
                )
            recorrer(nodo.left, profundidad + 1)
            recorrer(nodo.right, profundidad + 1)

        recorrer(raiz, 0)

    # =========================================================
    # Helpers
    # =========================================================

    @classmethod
    def _validar_id_referencia(cls, valor, nodos, contexto):
        if (isinstance(valor, bool)
                or not isinstance(valor, int)
                or valor not in nodos):
            raise ErrorJsonPersistencia(
                f"{contexto} referencia un nodo inexistente"
            )

    @classmethod
    def _validar_entero_id(cls, valor, contexto):
        try:
            return SistemaSismico._validar_id(valor)
        except ValueError as error:
            raise ErrorJsonPersistencia(
                f"{contexto} inválido: {error}"
            ) from error

    @staticmethod
    def _requerir_campos(datos, requeridos, contexto):
        faltantes = sorted(requeridos - set(datos))
        if faltantes:
            raise ErrorJsonPersistencia(
                f"Faltan campos en {contexto}: {', '.join(faltantes)}"
            )