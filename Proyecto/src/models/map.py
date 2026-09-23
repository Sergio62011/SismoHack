class Zona:
    """Represents a rectangular zone inside the simulated map."""

    def __init__(self, nombre, x_min, y_min, x_max, y_max, poblada):
        self.nombre = nombre
        self.x_min = float(x_min)
        self.y_min = float(y_min)
        self.x_max = float(x_max)
        self.y_max = float(y_max)
        self.poblada = bool(poblada)

    def contiene_punto(self, x, y):
        """Returns True when the point is inside the zone or on its border."""
        return (
            self.x_min <= x <= self.x_max
            and self.y_min <= y <= self.y_max
        )

    def simbolo(self):
        return "P" if self.poblada else "N"

    # === Persistencia y copia ===

    def to_dict(self):
        return {
            "nombre": self.nombre,
            "x_min": self.x_min,
            "y_min": self.y_min,
            "x_max": self.x_max,
            "y_max": self.y_max,
            "poblada": self.poblada,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            data["nombre"],
            data["x_min"], data["y_min"],
            data["x_max"], data["y_max"],
            data["poblada"],
        )

    def copia(self):
        return Zona(
            self.nombre, self.x_min, self.y_min,
            self.x_max, self.y_max, self.poblada,
        )

    def __repr__(self):
        tipo = "poblada" if self.poblada else "no poblada"
        return f"Zona({self.nombre}, {tipo})"


class MapaSismico:
    """Simple matrix map for zones and seismic events."""

    def __init__(self, ancho_km=1000, alto_km=1000, filas=10, columnas=10):
        self.ancho_km = ancho_km
        self.alto_km = alto_km
        self.filas = filas
        self.columnas = columnas
        self.zonas = []

    def agregar_zona(self, zona):
        self.zonas.append(zona)

    def obtener_zonas_del_punto(self, x, y):
        return [
            zona
            for zona in self.zonas
            if zona.contiene_punto(float(x), float(y))
        ]

    def esta_en_zona_poblada(self, x, y):
        zonas_del_punto = self.obtener_zonas_del_punto(x, y)
        return any(zona.poblada for zona in zonas_del_punto)

    def asignar_zona_a_evento(self, evento):
        evento.en_zona_poblada = self.esta_en_zona_poblada(evento.x, evento.y)
        evento.recalcular_prioridad()

    def convertir_coordenada_a_celda(self, x, y):
        columna = int((float(x) / self.ancho_km) * self.columnas)
        fila_desde_abajo = int((float(y) / self.alto_km) * self.filas)

        columna = min(max(columna, 0), self.columnas - 1)
        fila_desde_abajo = min(max(fila_desde_abajo, 0), self.filas - 1)

        fila = (self.filas - 1) - fila_desde_abajo
        return fila, columna

    def crear_matriz_vacia(self):
        return [["." for _ in range(self.columnas)] for _ in range(self.filas)]

    def crear_matriz_zonas(self):
        matriz = self.crear_matriz_vacia()
        for fila in range(self.filas):
            for columna in range(self.columnas):
                x, y = self._centro_de_celda(fila, columna)
                zonas = self.obtener_zonas_del_punto(x, y)
                if any(zona.poblada for zona in zonas):
                    matriz[fila][columna] = "P"
                elif len(zonas) > 0:
                    matriz[fila][columna] = "N"
        return matriz

    def crear_matriz_con_eventos(self, eventos):
        matriz = self.crear_matriz_zonas()
        for evento in eventos:
            fila, columna = self.convertir_coordenada_a_celda(
                evento.x, evento.y
            )
            matriz[fila][columna] = "E"
        return matriz

    def imprimir_matriz(self, matriz):
        print(
            "Leyenda: . = vacio | P = zona poblada | "
            "N = zona no poblada | E = evento"
        )
        for fila in matriz:
            print(" ".join(fila))

    def _centro_de_celda(self, fila, columna):
        ancho_celda = self.ancho_km / self.columnas
        alto_celda = self.alto_km / self.filas
        x = (columna + 0.5) * ancho_celda
        fila_desde_abajo = (self.filas - 1) - fila
        y = (fila_desde_abajo + 0.5) * alto_celda
        return x, y

    # === Persistencia y copia ===

    def to_dict(self):
        return {
            "ancho_km": self.ancho_km,
            "alto_km": self.alto_km,
            "filas": self.filas,
            "columnas": self.columnas,
            "zonas": [z.to_dict() for z in self.zonas],
        }

    @classmethod
    def from_dict(cls, data):
        mapa = cls(
            ancho_km=data["ancho_km"],
            alto_km=data["alto_km"],
            filas=data["filas"],
            columnas=data["columnas"],
        )
        for z in data["zonas"]:
            mapa.agregar_zona(Zona.from_dict(z))
        return mapa

    def copia(self):
        nuevo = MapaSismico(
            self.ancho_km, self.alto_km, self.filas, self.columnas
        )
        for z in self.zonas:
            nuevo.agregar_zona(z.copia())
        return nuevo