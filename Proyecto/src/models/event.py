from datetime import datetime
from typing import Set, Optional


class Evento:
    """Representa un evento sísmico con todos sus datos."""
    
    def __init__(
        self,
        id_evento: int,
        magnitud: float,
        profundidad: float,
        x: float,
        y: float,
        fecha_hora: datetime,
        revision: int = 1,
        estado: str = "pendiente",
    ):
        # === Datos físicos (inmutables en identidad) ===
        self.id_evento = int(id_evento)
        self.magnitud = float(magnitud)
        self.profundidad = float(profundidad)
        self.x = float(x)
        self.y = float(y)
        self.fecha_hora = fecha_hora  # datetime UTC
        
        # === Revisión y estado ===
        self.revision = int(revision)
        self.estado = estado  # "pendiente" | "revisado"
        self.estaciones: Set[str] = set()  # ← NUEVO
        
        # === Datos derivados ===
        self.prioridad = self._calcular_prioridad()  # se recalcula
        self.en_zona_poblada = False                 # ← NUEVO
        self.acceso_costoso = False                  # ← NUEVO
        
        # === Ubicación lógica ===
        self.ubicacion = "activo"  # "activo" | "archivado" | "eliminado"
        
        # === Asociaciones ===
        self.referencia: Optional[int] = None  # ID del evento referencia
        self.referenciado_por: Set[int] = set()  # IDs que lo usan
    
    # === Cálculo de prioridad (Sección 4 del PDF) ===
    def _calcular_prioridad(self) -> int:
        """Calcula la prioridad según reglas del proyecto."""
        if self.magnitud >= 6.0:
            return 3
        if (self.magnitud >= 4.5 and 
            self.profundidad <= 30.0 and 
            self.en_zona_poblada):
            return 3
        if self.magnitud >= 4.5:
            return 2
        return 1
    
    # === Clave K = (P, M, I) ===
    def calcular_clave(self) -> tuple:
        """Devuelve la clave ordenable para el AVL."""
        return (self.prioridad, self.magnitud, self.id_evento)
    
    # === Recalcular prioridad (tras corrección o cambio de zona) ===
    def recalcular_prioridad(self):
        self.prioridad = self._calcular_prioridad()
    
    # === Comparación por clave K (Sección 5) ===
    def __lt__(self, otro):
        return self.calcular_clave() < otro.calcular_clave()
    
    def __eq__(self, otro):
        return self.calcular_clave() == otro.calcular_clave()
    
    def __hash__(self):
        return hash(self.calcular_clave())
    
    # === Representación para debug ===
    def __repr__(self):
        return (f"Evento(id={self.id_evento}, M={self.magnitud}, "
                f"H={self.profundidad}, P={self.prioridad}, "
                f"clave={self.calcular_clave()})")