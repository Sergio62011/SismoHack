class Evento:
    PRIORIDADES = {
        "P1": 1,
        "P2": 2,
        "P3": 3,
    }

    def __init__(
        self,
        id_evento,
        magnitud,
        profundidad,
        x,
        y,
        fecha_hora,
        revision,
        prioridad,
        estado,
    ):
        self.id_evento = int(id_evento)
        self.magnitud = float(magnitud)
        self.profundidad = float(profundidad)
        self.x = float(x)
        self.y = float(y)
        self.fecha_hora = fecha_hora
        self.revision = int(revision)
        self.prioridad = prioridad
        self.estado = estado

    def prioridad_numerica(self):
        return self.PRIORIDADES[self.prioridad]

    def clave(self):
        return (self.prioridad_numerica(), self.magnitud, self.id_evento)

    def __lt__(self, otro):
        return self.clave() < otro.clave()

    def __eq__(self, otro):
        if not isinstance(otro, Evento):
            return False
        return self.clave() == otro.clave()

    def __repr__(self):
        return (
            f"Evento(id={self.id_evento}, magnitud={self.magnitud}, "
            f"prioridad={self.prioridad}, estado={self.estado})"
        )
