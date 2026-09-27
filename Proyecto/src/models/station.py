class Estacion:
    """Representa una estación sísmica del escenario."""

    def __init__(self, id_estacion: str, nombre: str):
        if not isinstance(id_estacion, str) or not id_estacion.strip():
            raise ValueError("El identificador de la estación no puede estar vacío.")

        if not isinstance(nombre, str) or not nombre.strip():
            raise ValueError("El nombre de la estación no puede estar vacío.")

        self.id_estacion = id_estacion.strip()
        self.nombre = nombre.strip()

    def to_dict(self):
        return {
            "id_estacion": self.id_estacion,
            "nombre": self.nombre,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id_estacion=data["id_estacion"],
            nombre=data["nombre"],
        )

    def copia(self):
        return Estacion(
            self.id_estacion,
            self.nombre,
        )

    def __repr__(self):
        return (
            f"Estacion(id={self.id_estacion}, "
            f"nombre={self.nombre})"
        )