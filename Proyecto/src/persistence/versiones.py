"""Named persistent versions backed by structural SismoLab JSON files.

[FIX] Ahora extrae el campo 'estado' del archivo de versión antes de
pasarlo al JsonLoader, porque el formato del archivo de versión es
distinto al formato que espera el loader directamente.
"""

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from persistence.json_loader import ErrorJsonPersistencia, JsonLoader
from persistence.json_saver import JsonSaver


class ErrorVersionesPersistentes(ValueError):
    """Raised when the version catalog cannot be safely used."""


class GestorVersiones:
    """Stores independently restorable, named operational snapshots."""

    MANIFEST_FILE = "versiones.json"
    FORMAT = "SismoLab-Versiones"
    SCHEMA_VERSION = 1

    def __init__(self, directorio=None):
        if directorio is None:
            directorio = Path(__file__).resolve().parents[2] / "versiones"
        self.directorio = Path(directorio).resolve()
        # [FIX] Crear el directorio en __init__ en vez de esperar a guardar
        self.directorio.mkdir(parents=True, exist_ok=True)

    # =========================================================
    # API pública
    # =========================================================

    def guardar(self, nombre, sistema):
        """Saves a named version and records it in the persistent catalog."""
        nombre = self._validar_nombre(nombre)
        versiones = self._leer_manifest()
        if any(version["name"] == nombre for version in versiones):
            raise ErrorVersionesPersistentes(
                f"Ya existe una versión llamada '{nombre}'"
            )

        archivo = self._nombre_archivo(nombre)
        ruta = self.directorio / archivo
        if ruta.exists():
            raise ErrorVersionesPersistentes(
                "El archivo interno de esa versión ya existe"
            )

        # Serializar el estado con JsonSaver y envolverlo en el formato
        # de versión (que tiene metadatos adicionales).
        estado = JsonSaver.a_diccionario(sistema)
        version = {
            "format": "SismoLab-Version",
            "schema_version": 1,
            "nombre_version": nombre,
            "fecha_creacion": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "estado": estado,
        }

        try:
            with ruta.open("w", encoding="utf-8") as archivo_salida:
                json.dump(version, archivo_salida, ensure_ascii=False, indent=2)
                archivo_salida.write("\n")
        except OSError as error:
            raise ErrorVersionesPersistentes(
                f"No se pudo guardar la versión: {error}"
            ) from error

        entrada = {
            "name": nombre,
            "file": archivo,
            "created_at": version["fecha_creacion"],
            "active_events": sistema.avl.size(),
            "historical_events": len(sistema._historicos),
            "avl_height": sistema.avl.height(),
            "stress_mode": sistema.avl.modo_estres,
        }

        try:
            versiones.append(entrada)
            self._escribir_manifest(versiones)
        except Exception:
            # Rollback: si falla el manifest, borrar el archivo recién creado
            if ruta.exists():
                ruta.unlink()
            raise

        return dict(entrada)

    def listar(self):
        """Returns catalog entries ordered from newest to oldest."""
        return [dict(version) for version in reversed(self._leer_manifest())]

    def restaurar(self, nombre, sistema_actual=None):
        """Loads a named version.

        [FIX] Extrae el campo 'estado' del archivo de versión y lo pasa
        al JsonLoader mediante un archivo temporal. El formato del
        archivo de versión NO es el mismo que el que espera el loader.
        """
        version = self._buscar(nombre)
        ruta = self._ruta_segura(version["file"])
        if not ruta.is_file():
            raise ErrorVersionesPersistentes(
                f"No se encuentra el archivo de la versión '{version['name']}'"
            )

        # Leer el archivo de versión (formato SismoLab-Version)
        try:
            with ruta.open("r", encoding="utf-8") as archivo_entrada:
                datos = json.load(archivo_entrada)
        except (OSError, json.JSONDecodeError) as error:
            raise ErrorVersionesPersistentes(
                f"No se pudo leer la versión '{nombre}': {error}"
            ) from error

        if not isinstance(datos, dict) or "estado" not in datos:
            raise ErrorVersionesPersistentes(
                f"La versión '{nombre}' no contiene un estado válido"
            )

        # Escribir el estado interno a un archivo temporal con el formato
        # que espera JsonLoader (SismoLab-AVL)
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            ) as tmp:
                json.dump(datos["estado"], tmp, ensure_ascii=False)
                tmp_path = tmp.name

            return JsonLoader.cargar_topologia(
                tmp_path, sistema_actual=sistema_actual
            )
        except ErrorJsonPersistencia as error:
            raise ErrorVersionesPersistentes(
                f"La versión '{nombre}' es inválida: {error}"
            ) from error
        finally:
            if tmp_path is not None:
                Path(tmp_path).unlink(missing_ok=True)

    def eliminar(self, nombre):
        """Removes a named version from the catalog and its snapshot file."""
        version = self._buscar(nombre)
        versiones = self._leer_manifest()
        restantes = [item for item in versiones if item["name"] != version["name"]]
        self._escribir_manifest(restantes)
        ruta = self._ruta_segura(version["file"])
        try:
            if ruta.exists():
                ruta.unlink()
        except OSError as error:
            raise ErrorVersionesPersistentes(
                f"La versión se quitó del catálogo, pero no se pudo borrar su archivo: {error}"
            ) from error

    # =========================================================
    # Internos
    # =========================================================

    def _buscar(self, nombre):
        nombre = self._validar_nombre(nombre)
        for version in self._leer_manifest():
            if version["name"] == nombre:
                return version
        raise ErrorVersionesPersistentes(
            f"No existe una versión llamada '{nombre}'"
        )

    def _leer_manifest(self):
        ruta = self.directorio / self.MANIFEST_FILE
        if not ruta.exists():
            return []
        try:
            with ruta.open("r", encoding="utf-8") as archivo:
                datos = json.load(archivo)
        except (OSError, json.JSONDecodeError) as error:
            raise ErrorVersionesPersistentes(
                f"No se pudo leer el catálogo de versiones: {error}"
            ) from error
        if (
            not isinstance(datos, dict)
            or datos.get("format") != self.FORMAT
            or datos.get("schema_version") != self.SCHEMA_VERSION
            or not isinstance(datos.get("versions"), list)
        ):
            raise ErrorVersionesPersistentes(
                "El catálogo de versiones tiene un formato inválido"
            )

        nombres = set()
        versiones = []
        for indice, version in enumerate(datos["versions"], start=1):
            if not isinstance(version, dict):
                raise ErrorVersionesPersistentes(
                    f"La versión {indice} del catálogo no es válida"
                )
            requeridos = {
                "name", "file", "created_at", "active_events",
                "historical_events", "avl_height", "stress_mode",
            }
            if set(version) != requeridos:
                raise ErrorVersionesPersistentes(
                    f"La versión {indice} tiene campos inválidos"
                )
            nombre = self._validar_nombre(version["name"])
            if nombre in nombres:
                raise ErrorVersionesPersistentes(
                    f"El catálogo repite el nombre '{nombre}'"
                )
            nombres.add(nombre)
            self._ruta_segura(version["file"])
            self._validar_metadatos(version, indice)
            versiones.append(dict(version))
        return versiones

    def _escribir_manifest(self, versiones):
        self.directorio.mkdir(parents=True, exist_ok=True)
        destino = self.directorio / self.MANIFEST_FILE
        temporal = destino.with_name(destino.name + ".tmp")
        datos = {
            "format": self.FORMAT,
            "schema_version": self.SCHEMA_VERSION,
            "versions": versiones,
        }
        try:
            with temporal.open("w", encoding="utf-8") as archivo:
                json.dump(datos, archivo, ensure_ascii=False, indent=2)
                archivo.write("\n")
            os.replace(temporal, destino)
        except OSError as error:
            if temporal.exists():
                temporal.unlink()
            raise ErrorVersionesPersistentes(
                f"No se pudo actualizar el catálogo de versiones: {error}"
            ) from error

    def _ruta_segura(self, archivo):
        if not isinstance(archivo, str) or not archivo.endswith(".json"):
            raise ErrorVersionesPersistentes(
                "El nombre interno de una versión es inválido"
            )
        ruta = (self.directorio / archivo).resolve()
        if ruta.parent != self.directorio:
            raise ErrorVersionesPersistentes(
                "El catálogo contiene una ruta no permitida"
            )
        return ruta

    @staticmethod
    def _validar_nombre(nombre):
        if not isinstance(nombre, str):
            raise ErrorVersionesPersistentes(
                "El nombre de la versión debe ser texto"
            )
        nombre = nombre.strip()
        if not nombre or len(nombre) > 80 or "\n" in nombre or "\r" in nombre:
            raise ErrorVersionesPersistentes(
                "El nombre de la versión debe tener entre 1 y 80 caracteres"
            )
        return nombre

    @staticmethod
    def _nombre_archivo(nombre):
        identificador = hashlib.sha256(nombre.encode("utf-8")).hexdigest()[:16]
        return f"version-{identificador}.json"

    @staticmethod
    def _validar_metadatos(version, indice):
        for campo in ("active_events", "historical_events"):
            valor = version[campo]
            if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
                raise ErrorVersionesPersistentes(
                    f"El campo '{campo}' de la versión {indice} es inválido"
                )
        altura = version["avl_height"]
        if isinstance(altura, bool) or not isinstance(altura, int) or altura < -1:
            raise ErrorVersionesPersistentes(
                f"La altura de la versión {indice} es inválida"
            )
        if not isinstance(version["stress_mode"], bool):
            raise ErrorVersionesPersistentes(
                f"El modo estrés de la versión {indice} es inválido"
            )
        try:
            datetime.strptime(version["created_at"], "%Y-%m-%dT%H:%M:%SZ")
        except (TypeError, ValueError) as error:
            raise ErrorVersionesPersistentes(
                f"La fecha de la versión {indice} es inválida"
            ) from error