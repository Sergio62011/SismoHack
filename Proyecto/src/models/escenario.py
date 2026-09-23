# models/escenario.py
from datetime import datetime, timedelta, timezone


class Reloj:
    """Reloj de simulación explícito, en UTC, que solo avanza."""

    def __init__(self, instante_inicial=None):
        if instante_inicial is None:
            instante_inicial = datetime(
                2026, 9, 7, 0, 0, 0, tzinfo=timezone.utc
            )
        if instante_inicial.tzinfo is None:
            raise ValueError("El reloj debe tener zona horaria UTC")
        self.instante = instante_inicial.astimezone(timezone.utc)

    # === Operaciones ===

    def avanzar(self, segundos):
        if segundos <= 0:
            raise ValueError("El avance del reloj debe ser positivo")
        self.instante += timedelta(seconds=segundos)

    def avanzar_horas(self, horas):
        self.avanzar(horas * 3600)

    def no_es_futura(self, fecha_hora):
        if fecha_hora.tzinfo is None:
            raise ValueError("La fecha debe tener zona horaria UTC")
        return fecha_hora <= self.instante

    def antiguedad_horas(self, fecha_hora):
        if fecha_hora.tzinfo is None:
            raise ValueError("La fecha debe tener zona horaria UTC")
        delta = self.instante - fecha_hora
        return delta.total_seconds() / 3600.0

    def copia(self):
        return Reloj(self.instante)

    # === Persistencia ===

    def to_dict(self):
        return {
            "instante": self.instante.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    @classmethod
    def from_dict(cls, data):
        if "instante" not in data:
            raise ValueError("El reloj debe tener un campo 'instante'")
        instante = datetime.strptime(
            data["instante"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        return cls(instante)

    def __repr__(self):
        return f"Reloj({self.instante.isoformat()})"


class Parametros:
    """Parámetros configurables del escenario: W, R, L, T."""

    def __init__(self, w=24.0, r=100.0, l=3, t=72.0):
        self.w = self._validar_positivo("W", w)
        self.r = self._validar_positivo("R", r)
        self.l = self._validar_entero_no_negativo("L", l)
        self.t = self._validar_positivo("T", t)

    def set_w(self, valor):
        self.w = self._validar_positivo("W", valor)

    def set_r(self, valor):
        self.r = self._validar_positivo("R", valor)

    def set_l(self, valor):
        self.l = self._validar_entero_no_negativo("L", valor)

    def set_t(self, valor):
        self.t = self._validar_positivo("T", valor)

    @staticmethod
    def _validar_positivo(nombre, valor):
        if isinstance(valor, bool):
            raise ValueError(f"{nombre} debe ser un número positivo")
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            raise ValueError(
                f"{nombre} debe ser un número positivo"
            ) from None
        if numero <= 0:
            raise ValueError(f"{nombre} debe ser positivo")
        return numero

    @staticmethod
    def _validar_entero_no_negativo(nombre, valor):
        if isinstance(valor, bool):
            raise ValueError(f"{nombre} debe ser un entero no negativo")
        try:
            numero = int(valor)
        except (TypeError, ValueError):
            raise ValueError(
                f"{nombre} debe ser un entero no negativo"
            ) from None
        if numero != valor or numero < 0:
            raise ValueError(f"{nombre} debe ser un entero no negativo")
        return numero

    # === Persistencia y copia ===

    def to_dict(self):
        return {"w": self.w, "r": self.r, "l": self.l, "t": self.t}

    @classmethod
    def from_dict(cls, data):
        for campo in ("w", "r", "l", "t"):
            if campo not in data:
                raise ValueError(f"Falta el parámetro '{campo}'")
        return cls(w=data["w"], r=data["r"], l=data["l"], t=data["t"])

    def copia(self):
        return Parametros(self.w, self.r, self.l, self.t)

    def __repr__(self):
        return f"Parametros(W={self.w}, R={self.r}, L={self.l}, T={self.t})"


class Escenario:
    """Estado del escenario: reloj, parámetros y mapa."""

    def __init__(self, mapa, reloj=None, parametros=None):
        self.mapa = mapa
        self.reloj = reloj if reloj is not None else Reloj()
        self.parametros = (
            parametros if parametros is not None else Parametros()
        )

    # === Persistencia y copia ===

    def to_dict(self):
        return {
            "reloj": self.reloj.to_dict(),
            "parametros": self.parametros.to_dict(),
            "mapa": self.mapa.to_dict(),
        }

    @classmethod
    def from_dict(cls, data):
        from models.map import MapaSismico
        if "reloj" not in data:
            raise ValueError("El escenario debe tener 'reloj'")
        if "parametros" not in data:
            raise ValueError("El escenario debe tener 'parametros'")
        if "mapa" not in data:
            raise ValueError("El escenario debe tener 'mapa'")
        return cls(
            mapa=MapaSismico.from_dict(data["mapa"]),
            reloj=Reloj.from_dict(data["reloj"]),
            parametros=Parametros.from_dict(data["parametros"]),
        )

    def copia(self):
        return Escenario(
            mapa=self.mapa.copia(),
            reloj=self.reloj.copia(),
            parametros=self.parametros.copia(),
        )

    def __repr__(self):
        return f"Escenario({self.reloj}, {self.parametros})"