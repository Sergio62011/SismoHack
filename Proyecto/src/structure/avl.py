from collections import deque
from typing import Optional

from node import Node


class AVL:

    def __init__(self):
        self.raiz = None



    def _obtener_altura(self, nodo: Optional[Node]) -> int:
        if nodo is None:
            return 0
        return nodo.altura

    def _actualizar_altura(self, nodo: Node) -> None:
        nodo.altura = 1 + max(
            self._obtener_altura(nodo.izquierda),
            self._obtener_altura(nodo.derecha)
        )


    def _factor_balance(self, nodo: Optional[Node]) -> int:
        if nodo is None:
            return 0

        return (
            self._obtener_altura(nodo.izquierda)
            - self._obtener_altura(nodo.derecha)
        )
    

    def _rotacion_derecha(self, y: Node) -> Node:

        x = y.izquierda
        temporal = x.derecha

        x.derecha = y
        y.izquierda = temporal

        self._actualizar_altura(y)
        self._actualizar_altura(x)

        return x

    def _rotacion_izquierda(self, x: Node) -> Node:

        y = x.derecha
        temporal = y.izquierda

        y.izquierda = x
        x.derecha = temporal

        self._actualizar_altura(x)
        self._actualizar_altura(y)

        return y


    def insertar(self, valor: int) -> None:
        self.raiz = self._insertar(self.raiz, valor)

    def _insertar(
        self,
        nodo: Optional[Node],
        valor: int
    ) -> Node:

        if nodo is None:
            return Node(valor)

        if valor < nodo.valor:
            nodo.izquierda = self._insertar(
                nodo.izquierda,
                valor
            )

        elif valor > nodo.valor:
            nodo.derecha = self._insertar(
                nodo.derecha,
                valor
            )

        else:
            return nodo

        self._actualizar_altura(nodo)

        balance = self._factor_balance(nodo)


        if balance > 1 and valor < nodo.izquierda.valor:
            return self._rotacion_derecha(nodo)


        if balance < -1 and valor > nodo.derecha.valor:
            return self._rotacion_izquierda(nodo)


        if balance > 1 and valor > nodo.izquierda.valor:

            nodo.izquierda = self._rotacion_izquierda(
                nodo.izquierda
            )

            return self._rotacion_derecha(nodo)


        if balance < -1 and valor < nodo.derecha.valor:

            nodo.derecha = self._rotacion_derecha(
                nodo.derecha
            )

            return self._rotacion_izquierda(nodo)

        return nodo


    def pre_order(self) -> None:

        if self.raiz is None:
            print("", end="")
        else:
            self._pre_order(self.raiz)

    def _pre_order(self, raiz: Optional[Node]) -> None:

        if raiz is None:
            return

        print(raiz.valor, end=" ")

        self._pre_order(raiz.izquierda)
        self._pre_order(raiz.derecha)


    def in_order(self) -> None:

        if self.raiz is None:
            print("", end="")
        else:
            self._in_order(self.raiz)

    def _in_order(self, raiz: Optional[Node]) -> None:

        if raiz is None:
            return

        self._in_order(raiz.izquierda)

        print(raiz.valor, end=" ")

        self._in_order(raiz.derecha)


    def post_order(self) -> None:

        if self.raiz is None:
            print("", end="")
        else:
            self._post_order(self.raiz)

    def _post_order(self, raiz: Optional[Node]) -> None:

        if raiz is None:
            return

        self._post_order(raiz.izquierda)
        self._post_order(raiz.derecha)

        print(raiz.valor, end=" ")


    def anchura(self) -> None:

        if self.raiz is None:
            print("", end="")
        else:
            self._anchura(self.raiz)

    def _anchura(self, raiz: Node) -> None:

        cola = deque([raiz])

        while cola:

            nodo = cola.popleft()

            print(nodo.valor, end=" ")

            if nodo.izquierda is not None:
                cola.append(nodo.izquierda)

            if nodo.derecha is not None:
                cola.append(nodo.derecha)



    def _buscar_minimo(self, raiz: Node) -> Node:

        actual = raiz

        while actual.izquierda is not None:
            actual = actual.izquierda

        return actual


    def eliminar(self, valor: int) -> None:
        self.raiz = self._eliminar(
            self.raiz,
            valor
        )

    def _eliminar(
        self,
        raiz: Optional[Node],
        valor: int
    ) -> Optional[Node]:

        if raiz is None:
            return None


        if valor < raiz.valor:

            raiz.izquierda = self._eliminar(
                raiz.izquierda,
                valor
            )

        elif valor > raiz.valor:

            raiz.derecha = self._eliminar(
                raiz.derecha,
                valor
            )

        else:

            # Nodo hoja
            if raiz.es_hoja():
                return None

            # Solo tiene hijo derecho
            if raiz.izquierda is None:
                return raiz.derecha

            # Solo tiene hijo izquierdo
            if raiz.derecha is None:
                return raiz.izquierda

            # Tiene dos hijos
            sucesor = self._buscar_minimo(
                raiz.derecha
            )

            raiz.valor = sucesor.valor

            raiz.derecha = self._eliminar(
                raiz.derecha,
                sucesor.valor
            )


        self._actualizar_altura(raiz)


        balance = self._factor_balance(raiz)


        if (
            balance > 1
            and self._factor_balance(raiz.izquierda) >= 0
        ):
            return self._rotacion_derecha(raiz)


        if (
            balance > 1
            and self._factor_balance(raiz.izquierda) < 0
        ):

            raiz.izquierda = self._rotacion_izquierda(
                raiz.izquierda
            )

            return self._rotacion_derecha(raiz)


        if (
            balance < -1
            and self._factor_balance(raiz.derecha) <= 0
        ):
            return self._rotacion_izquierda(raiz)


        if (
            balance < -1
            and self._factor_balance(raiz.derecha) > 0
        ):

            raiz.derecha = self._rotacion_derecha(
                raiz.derecha
            )

            return self._rotacion_izquierda(raiz)

        return raiz


    def altura(self) -> int:

        if self.raiz is None:
            return -1

        return self._altura(self.raiz)

    def _altura(
        self,
        nodo: Optional[Node]
    ) -> int:

        if nodo is None:
            return -1

        return 1 + max(
            self._altura(nodo.izquierda),
            self._altura(nodo.derecha)
        )


    def peso(self) -> int:

        if self.raiz is None:
            return 0

        return self._peso(self.raiz)

    def _peso(
        self,
        nodo: Optional[Node]
    ) -> int:

        if nodo is None:
            return 0

        return (
            1
            + self._peso(nodo.izquierda)
            + self._peso(nodo.derecha)
        )


    def recorrido_por_ramas(self) -> None:

        if self.raiz is None:
            print("El árbol está vacío.")
            return

        print("Caminos por ramas:")

        self._recorrido_por_ramas(
            self.raiz,
            []
        )
#backtracking
    def _recorrido_por_ramas(
        self,
        nodo: Node,
        camino: list
    ) -> None:

        camino.append(nodo.valor)

        if nodo.es_hoja():

            print(
                " -> ".join(
                    map(str, camino)
                )
            )

        else:

            if nodo.izquierda is not None:

                self._recorrido_por_ramas(
                    nodo.izquierda,
                    camino.copy()
                )

            if nodo.derecha is not None:

                self._recorrido_por_ramas(
                    nodo.derecha,
                    camino.copy()
                )


    def nivel_de_un_nodo(
        self,
        valor: int
    ) -> int:

        if self.raiz is None:
            return -1

        return self._nivel_de_un_nodo(
            self.raiz,
            valor,
            0
        )

    def _nivel_de_un_nodo(
        self,
        nodo: Optional[Node],
        valor: int,
        nivel_actual: int
    ) -> int:

        if nodo is None:
            return -1

        if nodo.valor == valor:
            return nivel_actual

        if valor < nodo.valor:

            return self._nivel_de_un_nodo(
                nodo.izquierda,
                valor,
                nivel_actual + 1
            )

        else:

            return self._nivel_de_un_nodo(
                nodo.derecha,
                valor,
                nivel_actual + 1
            )


    def cantidad_de_nodos_por_nivel(self) -> dict:

        if self.raiz is None:
            return {}

        conteo = {}

        self._cantidad_de_nodos_por_nivel(
            self.raiz,
            0,
            conteo
        )

        return conteo

    def _cantidad_de_nodos_por_nivel(
        self,
        nodo: Optional[Node],
        nivel: int,
        conteo: dict
    ) -> None:

        if nodo is None:
            return

        conteo[nivel] = (
            conteo.get(nivel, 0) + 1
        )

        self._cantidad_de_nodos_por_nivel(
            nodo.izquierda,
            nivel + 1,
            conteo
        )

        self._cantidad_de_nodos_por_nivel(
            nodo.derecha,
            nivel + 1,
            conteo
        )