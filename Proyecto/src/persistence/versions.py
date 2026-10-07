# Módulo versions: contiene la lógica relacionada con versions.
"""Named persistent versions backed by structural SismoLab JSON files.

Extracts the 'state' field from the version file before passing it to
JsonLoader, because the version file format differs from what the
loader directly expects.
"""

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from persistence.json_loader import JsonPersistenceError, JsonLoader
from persistence.json_saver import JsonSaver


# Representa PersistentVersionsError y agrupa sus datos y operaciones.
class PersistentVersionsError(ValueError):
    """Raised when the version catalog cannot be safely used."""


# Representa VersionManager y agrupa sus datos y operaciones.
class VersionManager:
    """Stores independently restorable, named operational snapshots."""

    MANIFEST_FILE = "versions.json"
    FORMAT = "SismoLab-Versions"
    SCHEMA_VERSION = 1

    # Define init.
    def __init__(self, directory=None):
        if directory is None:
            directory = Path(__file__).resolve().parents[2] / "versions"
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)

    # =========================================================
    # Public API
    # =========================================================

    # Gestiona save.
    def save(self, name, system):
        """Saves a named version and records it in the persistent catalog."""
        name = self._validate_name(name)
        versions = self._read_manifest()
        if any(version["name"] == name for version in versions):
            raise PersistentVersionsError(
                f"A version named '{name}' already exists"
            )

        filename = self._filename(name)
        path = self.directory / filename
        if path.exists():
            raise PersistentVersionsError(
                "The internal file for that version already exists"
            )

        state = JsonSaver.to_dict(system)

        now_simulation = system.clock.instant.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        version = {
            "format": "SismoLab-Version",
            "schema_version": 1,
            "version_name": name,
            "creation_date": now_simulation,
            "state": state,
        }

        try:
            with path.open("w", encoding="utf-8") as output:
                json.dump(version, output, ensure_ascii=False, indent=2)
                output.write("\n")
        except OSError as error:
            raise PersistentVersionsError(
                f"Could not save the version: {error}"
            ) from error

        entry = {
            "name": name,
            "file": filename,
            "created_at": version["creation_date"],
            "active_events": system.avl.size(),
            "historical_events": len(system._historical_events),
            "avl_height": system.avl.height(),
            "stress_mode": system.avl.stress_mode,
        }

        try:
            versions.append(entry)
            self._write_manifest(versions)
        except Exception:
            if path.exists():
                path.unlink()
            raise

        return dict(entry)

    # Gestiona list.
    def list(self):
        """Returns catalog entries ordered from newest to oldest."""
        return [dict(version) for version in reversed(self._read_manifest())]

    # Gestiona restore.
    def restore(self, name, current_system=None):
        """Loads a named version.

        Extracts the 'state' field from the version file and passes it
        to JsonLoader through a temporary file.
        """
        version = self._find(name)
        path = self._safe_path(version["file"])
        if not path.is_file():
            raise PersistentVersionsError(
                f"Cannot find the file for version '{version['name']}'"
            )

        try:
            with path.open("r", encoding="utf-8") as stream:
                data = json.load(stream)
        except (OSError, json.JSONDecodeError) as error:
            raise PersistentVersionsError(
                f"Could not read version '{name}': {error}"
            ) from error

        if not isinstance(data, dict) or "state" not in data:
            raise PersistentVersionsError(
                f"Version '{name}' does not contain a valid state"
            )

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            ) as tmp:
                json.dump(data["state"], tmp, ensure_ascii=False)
                tmp_path = tmp.name

            return JsonLoader.load_topology(
                tmp_path, current_system=current_system
            )
        except JsonPersistenceError as error:
            raise PersistentVersionsError(
                f"Version '{name}' is invalid: {error}"
            ) from error
        finally:
            if tmp_path is not None:
                Path(tmp_path).unlink(missing_ok=True)

    # Gestiona delete.
    def delete(self, name):
        """Removes a named version from the catalog and its snapshot file."""
        version = self._find(name)
        versions = self._read_manifest()
        remaining = [
            item for item in versions if item["name"] != version["name"]
        ]
        self._write_manifest(remaining)
        path = self._safe_path(version["file"])
        try:
            if path.exists():
                path.unlink()
        except OSError as error:
            raise PersistentVersionsError(
                f"The version was removed from the catalog, but its file "
                f"could not be deleted: {error}"
            ) from error

    # =========================================================
    # Internal
    # =========================================================

    # Gestiona find.
    def _find(self, name):
        name = self._validate_name(name)
        for version in self._read_manifest():
            if version["name"] == name:
                return version
        raise PersistentVersionsError(
            f"No version named '{name}' exists"
        )

    # Gestiona read manifest.
    def _read_manifest(self):
        path = self.directory / self.MANIFEST_FILE
        if not path.exists():
            return []
        try:
            with path.open("r", encoding="utf-8") as stream:
                data = json.load(stream)
        except (OSError, json.JSONDecodeError) as error:
            raise PersistentVersionsError(
                f"Could not read the version catalog: {error}"
            ) from error
        if (
            not isinstance(data, dict)
            or data.get("format") != self.FORMAT
            or data.get("schema_version") != self.SCHEMA_VERSION
            or not isinstance(data.get("versions"), list)
        ):
            raise PersistentVersionsError(
                "The version catalog has an invalid format"
            )

        names = set()
        versions = []
        for index, version in enumerate(data["versions"], start=1):
            if not isinstance(version, dict):
                raise PersistentVersionsError(
                    f"Version {index} in the catalog is not valid"
                )
            required = {
                "name", "file", "created_at", "active_events",
                "historical_events", "avl_height", "stress_mode",
            }
            if set(version) != required:
                raise PersistentVersionsError(
                    f"Version {index} has invalid fields"
                )
            name = self._validate_name(version["name"])
            if name in names:
                raise PersistentVersionsError(
                    f"The catalog repeats the name '{name}'"
                )
            names.add(name)
            self._safe_path(version["file"])
            self._validate_metadata(version, index)
            versions.append(dict(version))
        return versions

    # Gestiona write manifest.
    def _write_manifest(self, versions):
        self.directory.mkdir(parents=True, exist_ok=True)
        destination = self.directory / self.MANIFEST_FILE
        temp = destination.with_name(destination.name + ".tmp")
        data = {
            "format": self.FORMAT,
            "schema_version": self.SCHEMA_VERSION,
            "versions": versions,
        }
        try:
            with temp.open("w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(temp, destination)
        except OSError as error:
            if temp.exists():
                temp.unlink()
            raise PersistentVersionsError(
                f"Could not update the version catalog: {error}"
            ) from error

    # Gestiona safe path.
    def _safe_path(self, filename):
        if not isinstance(filename, str) or not filename.endswith(".json"):
            raise PersistentVersionsError(
                "The internal name of a version is invalid"
            )
        path = (self.directory / filename).resolve()
        if path.parent != self.directory:
            raise PersistentVersionsError(
                "The catalog contains an unauthorized path"
            )
        return path

    @staticmethod
    # Gestiona validate name.
    def _validate_name(name):
        if not isinstance(name, str):
            raise PersistentVersionsError(
                "The version name must be text"
            )
        name = name.strip()
        if not name or len(name) > 80 or "\n" in name or "\r" in name:
            raise PersistentVersionsError(
                "The version name must be between 1 and 80 characters"
            )
        return name

    @staticmethod
    # Gestiona filename.
    def _filename(name):
        identifier = hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
        return f"version-{identifier}.json"

    @staticmethod
    # Gestiona validate metadata.
    def _validate_metadata(version, index):
        for field in ("active_events", "historical_events"):
            value = version[field]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise PersistentVersionsError(
                    f"Field '{field}' of version {index} is invalid"
                )
        height = version["avl_height"]
        if isinstance(height, bool) or not isinstance(height, int) or height < -1:
            raise PersistentVersionsError(
                f"The height of version {index} is invalid"
            )
        if not isinstance(version["stress_mode"], bool):
            raise PersistentVersionsError(
                f"The stress mode of version {index} is invalid"
            )
        try:
            datetime.strptime(version["created_at"], "%Y-%m-%dT%H:%M:%SZ")
        except (TypeError, ValueError) as error:
            raise PersistentVersionsError(
                f"The date of version {index} is invalid"
            ) from error