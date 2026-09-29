class Accion():
    def __init__(self, descripcion, estado):
        self.descripcion = descripcion
        self.estado_antes = estado
        

class Historial:
    def __init__(self):
        self.pila = []
        
    def registro_accion(self, accion):
        self.pila.append(accion)
        
    def deshacer(self):
        if not self.pila:
            return None
        return self.pila.pop()
    
    def pila_vacia(self):
        return len(self.pila) == 0
    
    def cantidad(self):
        return len(self._pila)