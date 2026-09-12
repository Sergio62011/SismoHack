from src.estructuras.nodo import Nodo


class BST:
    def __init__(self):
        self.raiz = None

    def insertar(self, evento):
        self.raiz = self._insertar_recursivo(self.raiz, evento)

    def _insertar_recursivo(self, nodo, evento):
        if nodo is None:
            return Nodo(evento)

        if evento.clave() < nodo.evento.clave():
            nodo.izquierda = self._insertar_recursivo(nodo.izquierda, evento)
        elif evento.clave() > nodo.evento.clave():
            nodo.derecha = self._insertar_recursivo(nodo.derecha, evento)
        else:
            raise ValueError("No se permiten claves duplicadas en el arbol.")

        return nodo

    def buscar(self, evento):
        return self._buscar_recursivo(self.raiz, evento.clave())

    def buscar_por_clave(self, clave):
        return self._buscar_recursivo(self.raiz, clave)

    def _buscar_recursivo(self, nodo, clave):
        if nodo is None:
            return None

        if clave == nodo.evento.clave():
            return nodo.evento
        if clave < nodo.evento.clave():
            return self._buscar_recursivo(nodo.izquierda, clave)
        return self._buscar_recursivo(nodo.derecha, clave)

    def eliminar(self, evento):
        self.raiz = self._eliminar_recursivo(self.raiz, evento.clave())

    def eliminar_por_clave(self, clave):
        self.raiz = self._eliminar_recursivo(self.raiz, clave)

    def _eliminar_recursivo(self, nodo, clave):
        if nodo is None:
            return None

        if clave < nodo.evento.clave():
            nodo.izquierda = self._eliminar_recursivo(nodo.izquierda, clave)
        elif clave > nodo.evento.clave():
            nodo.derecha = self._eliminar_recursivo(nodo.derecha, clave)
        else:
            if nodo.izquierda is None:
                return nodo.derecha
            if nodo.derecha is None:
                return nodo.izquierda

            sucesor = self._nodo_minimo(nodo.derecha)
            nodo.evento = sucesor.evento
            nodo.derecha = self._eliminar_recursivo(nodo.derecha, sucesor.evento.clave())

        return nodo

    def _nodo_minimo(self, nodo):
        actual = nodo
        while actual.izquierda is not None:
            actual = actual.izquierda
        return actual

    def altura(self):
        return self._altura_recursiva(self.raiz)

    def _altura_recursiva(self, nodo):
        if nodo is None:
            return -1
        return max(self._altura_recursiva(nodo.izquierda), self._altura_recursiva(nodo.derecha)) + 1

    def profundidad(self, evento):
        return self.profundidad_por_clave(evento.clave())

    def profundidad_por_clave(self, clave):
        return self._profundidad_recursiva(self.raiz, clave, 0)

    def _profundidad_recursiva(self, nodo, clave, profundidad_actual):
        if nodo is None:
            return -1

        if clave == nodo.evento.clave():
            return profundidad_actual
        if clave < nodo.evento.clave():
            return self._profundidad_recursiva(nodo.izquierda, clave, profundidad_actual + 1)
        return self._profundidad_recursiva(nodo.derecha, clave, profundidad_actual + 1)

    def inorder(self):
        eventos = []
        self._inorder_recursivo(self.raiz, eventos)
        return eventos

    def _inorder_recursivo(self, nodo, eventos):
        if nodo is not None:
            self._inorder_recursivo(nodo.izquierda, eventos)
            eventos.append(nodo.evento)
            self._inorder_recursivo(nodo.derecha, eventos)

    def preorder(self):
        eventos = []
        self._preorder_recursivo(self.raiz, eventos)
        return eventos

    def _preorder_recursivo(self, nodo, eventos):
        if nodo is not None:
            eventos.append(nodo.evento)
            self._preorder_recursivo(nodo.izquierda, eventos)
            self._preorder_recursivo(nodo.derecha, eventos)

    def postorder(self):
        eventos = []
        self._postorder_recursivo(self.raiz, eventos)
        return eventos

    def _postorder_recursivo(self, nodo, eventos):
        if nodo is not None:
            self._postorder_recursivo(nodo.izquierda, eventos)
            self._postorder_recursivo(nodo.derecha, eventos)
            eventos.append(nodo.evento)

    def cantidad_hojas(self):
        return self._cantidad_hojas_recursiva(self.raiz)

    def _cantidad_hojas_recursiva(self, nodo):
        if nodo is None:
            return 0
        if nodo.izquierda is None and nodo.derecha is None:
            return 1
        return self._cantidad_hojas_recursiva(nodo.izquierda) + self._cantidad_hojas_recursiva(nodo.derecha)

    def factor_balance(self, nodo=None):
        if nodo is None:
            nodo = self.raiz
        if nodo is None:
            return 0
        return self._altura_recursiva(nodo.izquierda) - self._altura_recursiva(nodo.derecha)
