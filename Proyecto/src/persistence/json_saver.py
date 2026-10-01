"""JSON serialization for the complete SismoLab operational state."""

import json
import os
from pathlib import Path


class JsonSaver:
    """Exports a system without flattening the active AVL topology."""

    FORMAT = "SismoLab-AVL"
    SCHEMA_VERSION = 1

    @classmethod
    def guardar(cls, sistema, ruta):
        """Writes a complete structural snapshot to a user-selected path."""
        destino = Path(ruta)
        if not destino.name:
            raise ValueError("Debes seleccionar un archivo JSON")
        if destino.suffix.lower() != ".json":
            destino = destino.with_suffix(".json")

        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_name(destino.name + ".tmp")
        datos = cls.a_diccionario(sistema)

        try:
            with temporal.open("w", encoding="utf-8") as archivo:
                json.dump(datos, archivo, ensure_ascii=False, indent=2)
                archivo.write("\n")
            os.replace(temporal, destino)
        except OSError as error:
            if temporal.exists():
                temporal.unlink()
            raise ValueError(f"No se pudo guardar el archivo: {error}") from error

        return destino

    @classmethod
    def a_diccionario(cls, sistema):
        """Builds the JSON-compatible representation of a system."""
        arbol = cls._serializar_arbol(sistema.avl.root)
        return {
            "format": cls.FORMAT,
            "schema_version": cls.SCHEMA_VERSION,
            # [FIX] Guardar el modo de carga de forma explícita
            "meta": {
                "modo_carga": "topologia",
            },
            "scenario": sistema.escenario.to_dict(),
            "execution": {
                "stress_mode": sistema.avl.modo_estres,
                "rotations_total": sistema.avl.rotaciones_realizadas,
                "last_rotations": list(sistema.ultimas_rotaciones),
                "last_recovery_cost": sistema.ultimo_costo_recuperacion,
                "metrics": dict(sistema.metricas),
            },
            "active_tree": arbol,
            "historical_events": [
                evento.to_dict()
                for _, evento in sorted(sistema._historicos.items())
            ],
            "removed_ids": sorted(sistema.ids_eliminados),
            "report_queue": [
                reporte.to_dict() for reporte in sistema.cola_reportes
            ],
            "last_processed_report": (
                sistema.ultimo_reporte_procesado.to_dict()
                if sistema.ultimo_reporte_procesado is not None
                else None
            ),
            "insertion_events": cls._eventos_preorden(sistema.avl.root),
        }

    @classmethod
    def _serializar_arbol(cls, raiz):
        nodos = []

        def visitar(nodo):
            if nodo is None:
                return
            nodos.append({
                "event": nodo.event.to_dict(),
                "left": nodo.left.event.id_evento if nodo.left else None,
                "right": nodo.right.event.id_evento if nodo.right else None,
                "height": nodo.height,
                "balance_factor": nodo.balance_factor,
            })
            visitar(nodo.left)
            visitar(nodo.right)

        visitar(raiz)
        return {
            "root": raiz.event.id_evento if raiz else None,
            "nodes": nodos,
        }

    @classmethod
    def _eventos_preorden(cls, raiz):
        eventos = []

        def visitar(nodo):
            if nodo is None:
                return
            eventos.append(nodo.event.to_dict())
            visitar(nodo.left)
            visitar(nodo.right)

        visitar(raiz)
        return eventos