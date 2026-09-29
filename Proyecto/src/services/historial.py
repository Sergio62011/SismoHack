class Accion():
    def __init__(self, descripcion, estado):
        self.descripcion = descripcion
        self.estado_antes = estado
        

class Historial:
    def __init__(self):
        self._pila = []
        
    def registro_accion(self, accion):
        self._pila.append(accion)
        
    def deshacer(self):
        if not self._pila:
            return None
        return self._pila.pop()
    
    def pila_vacia(self):
        return len(self._pila) == 0
    
    def cantidad(self):
        return len(self._pila)