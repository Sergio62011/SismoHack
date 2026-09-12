from src.estructuras.bst import BST
from src.estructuras.nodo import Nodo


class AVL(BST):
    def insertar(self, evento):
        self.raiz = self._insertar_avl(self.raiz, evento)

    def _insertar_avl(self, nodo, evento):
        if nodo is None:
            return Nodo(evento)

        if evento.clave() < nodo.evento.clave():
            nodo.izquierda = self._insertar_avl(nodo.izquierda, evento)
        elif evento.clave() > nodo.evento.clave():
            nodo.derecha = self._insertar_avl(nodo.derecha, evento)
        else:
            raise ValueError("No se permiten claves duplicadas en el arbol.")

        self._actualizar_altura(nodo)
        return self._balancear(nodo)

    def eliminar(self, evento):
        self.raiz = self._eliminar_avl(self.raiz, evento.clave())

    def eliminar_por_clave(self, clave):
        self.raiz = self._eliminar_avl(self.raiz, clave)

    def _eliminar_avl(self, nodo, clave):
        if nodo is None:
            return None

        if clave < nodo.evento.clave():
            nodo.izquierda = self._eliminar_avl(nodo.izquierda, clave)
        elif clave > nodo.evento.clave():
            nodo.derecha = self._eliminar_avl(nodo.derecha, clave)
        else:
            if nodo.izquierda is None:
                return nodo.derecha
            if nodo.derecha is None:
                return nodo.izquierda

            sucesor = self._nodo_minimo(nodo.derecha)
            nodo.evento = sucesor.evento
            nodo.derecha = self._eliminar_avl(nodo.derecha, sucesor.evento.clave())

        self._actualizar_altura(nodo)
        return self._balancear(nodo)

    def _altura_nodo(self, nodo):
        if nodo is None:
            return -1
        return nodo.altura

    def _actualizar_altura(self, nodo):
        nodo.altura = max(self._altura_nodo(nodo.izquierda), self._altura_nodo(nodo.derecha)) + 1

    def factor_balance(self, nodo=None):
        if nodo is None:
            nodo = self.raiz
        if nodo is None:
            return 0
        return self._altura_nodo(nodo.izquierda) - self._altura_nodo(nodo.derecha)

    def _balancear(self, nodo):
        balance = self.factor_balance(nodo)

        if balance > 1:
            if self.factor_balance(nodo.izquierda) < 0:
                return self.rotacion_izquierda_derecha(nodo)
            return self.rotacion_derecha(nodo)

        if balance < -1:
            if self.factor_balance(nodo.derecha) > 0:
                return self.rotacion_derecha_izquierda(nodo)
            return self.rotacion_izquierda(nodo)

        return nodo

    def rotacion_derecha(self, nodo):
        nueva_raiz = nodo.izquierda
        subarbol_temporal = nueva_raiz.derecha

        nueva_raiz.derecha = nodo
        nodo.izquierda = subarbol_temporal

        self._actualizar_altura(nodo)
        self._actualizar_altura(nueva_raiz)

        return nueva_raiz

    def rotacion_izquierda(self, nodo):
        nueva_raiz = nodo.derecha
        subarbol_temporal = nueva_raiz.izquierda

        nueva_raiz.izquierda = nodo
        nodo.derecha = subarbol_temporal

        self._actualizar_altura(nodo)
        self._actualizar_altura(nueva_raiz)

        return nueva_raiz

    def rotacion_izquierda_derecha(self, nodo):
        nodo.izquierda = self.rotacion_izquierda(nodo.izquierda)
        return self.rotacion_derecha(nodo)

    def rotacion_derecha_izquierda(self, nodo):
        nodo.derecha = self.rotacion_derecha(nodo.derecha)
        return self.rotacion_izquierda(nodo)
