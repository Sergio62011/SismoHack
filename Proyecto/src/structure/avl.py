# structure/avl.py
from structure.node import Node


class AVL:

    def __init__(self):
        self.root = None
        self.modo_estres = False
        self.rotaciones_realizadas = 0

    # =========================================================
    # INSERT
    # =========================================================

    def insert(self, event):
        # The identifier is the earthquake identity, not merely a component
        # of its key. It cannot appear twice even after a key change.
        if self._find_by_id(self.root, event.id_evento) is not None:
            raise ValueError(f"Evento duplicado: ID {event.id_evento}")

        if self.root is None:
            self.root = Node(event)
        else:
            self.root = self._insert(self.root, event)
            self.root.parent = None

    def _find_by_id(self, node, event_id):
        """Searches an identity across the whole tree.

        The AVL is ordered by (priority, magnitude, identifier), so an ID
        alone cannot determine which branch to search.
        """
        if node is None:
            return None

        if node.event.id_evento == event_id:
            return node

        found = self._find_by_id(node.left, event_id)
        if found is not None:
            return found

        return self._find_by_id(node.right, event_id)

    def _insert(self, node, event):
        """Inserta recursivamente. Retorna la nueva raíz del subárbol."""

        # Caso base: llegamos a un lugar vacío
        if node is None:
            return Node(event)

        # Comparación por clave K = (P, M, I)
        if event < node.event:

            node.left = self._insert(node.left, event)
            if node.left is not None:
                node.left.parent = node

        elif event > node.event:

            node.right = self._insert(node.right, event)
            if node.right is not None:
                node.right.parent = node

        else:
            raise ValueError(f"Evento duplicado: ID {event.id_evento}")

        # Actualizar altura del nodo actual
        node.update_height()

        # Si estamos en modo estrés, NO balancear
        if self.modo_estres:
            return node

        # Balancear y retornar la nueva raíz del subárbol
        return self._balance(node)

    # =========================================================
    # BALANCE (rotaciones)
    # =========================================================

    def _balance(self, node):
        """Verifica el factor de balance y aplica rotaciones si hace falta."""

        fb = node.balance_factor

        # Caso LL: rotación simple a la derecha
        if fb > 1 and node.left.balance_factor >= 0:
            return self._rotate_right(node)

        # Caso LR: rotación doble izquierda-derecha
        if fb > 1 and node.left.balance_factor < 0:
            node.left = self._rotate_left(node.left)
            if node.left is not None:
                node.left.parent = node
            return self._rotate_right(node)

        # Caso RR: rotación simple a la izquierda
        if fb < -1 and node.right.balance_factor <= 0:
            return self._rotate_left(node)

        # Caso RL: rotación doble derecha-izquierda
        if fb < -1 and node.right.balance_factor > 0:
            node.right = self._rotate_right(node.right)
            if node.right is not None:
                node.right.parent = node
            return self._rotate_left(node)

        # Ya está balanceado
        return node

    # =========================================================
    # ROTACIONES
    # =========================================================

    def _rotate_right(self, z):
        """
              z                y
             / \              / \
            y   T4    →      x   z
           / \              / \ / \
          x   T3           T1 T2 T3 T4
         / \
        T1  T2
        """
        y = z.left
        T3 = y.right

        # Rotación
        y.right = z
        z.left = T3

        # Actualizar padres
        y.parent = z.parent
        z.parent = y
        if T3 is not None:
            T3.parent = z

        # Actualizar alturas (primero z, luego y)
        z.update_height()
        y.update_height()

        self.rotaciones_realizadas += 1
        return y

    def _rotate_left(self, z):
        """
            z                    y
           / \                  / \
          T1  y        →       z   x
             / \              / \ / \
            T2  x            T1 T2 T3 T4
               / \
              T3  T4
        """
        y = z.right
        T2 = y.left

        # Rotación
        y.left = z
        z.right = T2

        # Actualizar padres
        y.parent = z.parent
        z.parent = y
        if T2 is not None:
            T2.parent = z

        # Actualizar alturas
        z.update_height()
        y.update_height()

        self.rotaciones_realizadas += 1
        return y

    # =========================================================
    # SEARCH
    # =========================================================

    def search(self, key):
        return self._search(self.root, key)

    def _search(self, node, key):

        if node is None:
            return None

        node_key = node.event.calcular_clave()

        if key == node_key:
            return node

        if key < node_key:
            return self._search(node.left, key)

        return self._search(node.right, key)

    # =========================================================
    # PREORDER
    # =========================================================

    def pre_order(self):
        result = []
        self._pre_order(self.root, result)
        return result

    def _pre_order(self, node, result):

        if node is not None:
            result.append(node.event)
            self._pre_order(node.left, result)
            self._pre_order(node.right, result)

    # =========================================================
    # INORDER
    # =========================================================

    def in_order(self):
        result = []
        self._in_order(self.root, result)
        return result

    def _in_order(self, node, result):

        if node is not None:
            self._in_order(node.left, result)
            result.append(node.event)
            self._in_order(node.right, result)

    # =========================================================
    # POSTORDER
    # =========================================================

    def post_order(self):
        result = []
        self._post_order(self.root, result)
        return result

    def _post_order(self, node, result):

        if node is not None:
            self._post_order(node.left, result)
            self._post_order(node.right, result)
            result.append(node.event)

    # =========================================================
    # LEVEL ORDER / BFS
    # =========================================================

    def breadth_first(self):

        if self.root is None:
            return []

        queue = [self.root]
        result = []

        while len(queue) > 0:

            node = queue.pop(0)
            result.append(node.event)

            if node.left is not None:
                queue.append(node.left)

            if node.right is not None:
                queue.append(node.right)

        return result

    # =========================================================
    # HEIGHT
    # =========================================================

    def height(self):
        return self.root.height if self.root else -1

    # =========================================================
    # UPDATE HEIGHTS (recalcula todo el árbol)
    # =========================================================

    def update_heights(self):
        self._update_heights(self.root)

    def _update_heights(self, node):

        if node is None:
            return -1

        left_height = self._update_heights(node.left)
        right_height = self._update_heights(node.right)

        node.height = 1 + max(left_height, right_height)

        return node.height

    # =========================================================
    # SIZE / NUMBER OF NODES
    # =========================================================

    def size(self):
        return self._size(self.root)

    def _size(self, node):

        if node is None:
            return 0

        return 1 + self._size(node.left) + self._size(node.right)

    # =========================================================
    # NUMBER OF LEAVES
    # =========================================================

    def number_of_leaves(self):
        return self._number_of_leaves(self.root)

    def _number_of_leaves(self, node):

        if node is None:
            return 0

        if node.is_leaf():
            return 1

        return (
            self._number_of_leaves(node.left)
            + self._number_of_leaves(node.right)
        )

    # =========================================================
    # NODE LEVEL
    # =========================================================

    def node_level(self, key):
        return self._node_level(self.root, key, 0)

    def _node_level(self, node, key, level):

        if node is None:
            return -1

        node_key = node.event.calcular_clave()

        if key == node_key:
            return level

        if key < node_key:
            return self._node_level(node.left, key, level + 1)

        return self._node_level(node.right, key, level + 1)

    # =========================================================
    # NODES PER LEVEL
    # =========================================================

    def nodes_per_level(self):

        result = {}

        self._nodes_per_level(self.root, 0, result)

        return result

    def _nodes_per_level(self, node, level, result):

        if node is None:
            return

        if level not in result:
            result[level] = 0

        result[level] += 1

        self._nodes_per_level(node.left, level + 1, result)
        self._nodes_per_level(node.right, level + 1, result)

    # =========================================================
    # ROOT-TO-LEAF PATHS
    # =========================================================

    def root_to_leaf_paths(self):

        result = []

        self._root_to_leaf_paths(self.root, [], result)

        return result

    def _root_to_leaf_paths(self, node, path, result):

        if node is None:
            return

        path.append(node.event)

        if node.left is None and node.right is None:
            result.append(path.copy())

        else:

            self._root_to_leaf_paths(node.left, path, result)
            self._root_to_leaf_paths(node.right, path, result)

        path.pop()

    # =========================================================
    # BALANCE FACTOR
    # =========================================================

    def balance_factor(self, node):

        if node is None:
            return 0

        return node.balance_factor

    # =========================================================
    # MINIMUM
    # =========================================================

    def find_minimum(self, node):

        current = node

        while current.left is not None:
            current = current.left

        return current

    # =========================================================
    # MAXIMUM
    # =========================================================

    def find_maximum(self, node):

        current = node

        while current.right is not None:
            current = current.right

        return current

    # =========================================================
    # DELETE
    # =========================================================

    def delete(self, key):
        self.root = self._delete(self.root, key)

        if self.root is not None:
            self.root.parent = None

    def _delete(self, node, key):

        if node is None:
            return None

        node_key = node.event.calcular_clave()

        if key < node_key:

            node.left = self._delete(node.left, key)

            if node.left is not None:
                node.left.parent = node

        elif key > node_key:

            node.right = self._delete(node.right, key)

            if node.right is not None:
                node.right.parent = node

        else:

            # Case 1: leaf
            if node.left is None and node.right is None:
                return None

            # Case 2: only right child
            if node.left is None:
                node.right.parent = node.parent
                return node.right

            # Case 3: only left child
            if node.right is None:
                node.left.parent = node.parent
                return node.left

            # Case 4: two children
            successor = self.find_minimum(node.right)

            node.event = successor.event

            node.right = self._delete(
                node.right,
                successor.event.calcular_clave()
            )

            if node.right is not None:
                node.right.parent = node

        # Actualizar altura
        node.update_height()

        # Balancear (a menos que estemos en estrés)
        if self.modo_estres:
            return node

        return self._balance(node)

    # =========================================================
    # MODO ESTRÉS
    # =========================================================

    def activar_modo_estres(self):
        """Activa el modo estrés: no se aplican rotaciones."""
        self.modo_estres = True
        print("⚠️  Modo estrés activado: NO se aplicarán rotaciones.")

    def desactivar_modo_estres(self):
        """Desactiva el modo estrés."""
        self.modo_estres = False
        print("✅ Modo estrés desactivado.")

    # =========================================================
    # RECUPERACIÓN GLOBAL
    # =========================================================

    def recuperar_balance(self):
        """
        Recuperación global: aplica rotaciones bottom-up
        hasta que todo el árbol cumpla la propiedad AVL.
        """
        if self.root is None:
            return

        # Disable stress mode so the required rotations can occur.
        self.modo_estres = False

        # A degraded tree can have height differences greater than 2. One
        # postorder pass is not always enough, so repeat until it is AVL.
        while True:
            self.root = self._recuperar(self.root)
            self.root.parent = None

            if self._esta_balanceado(self.root):
                break

        # A completed global recovery returns the tree to normal mode.
        self.modo_estres = False

    def _esta_balanceado(self, node):
        """Checks that every node has a valid AVL balance factor."""
        if node is None:
            return True

        return (
            -1 <= node.balance_factor <= 1
            and self._esta_balanceado(node.left)
            and self._esta_balanceado(node.right)
        )

    def _recuperar(self, node):
        """Recorre post-orden y rebalancea cada nodo."""
        if node is None:
            return None

        # Primero rebalancear los hijos
        node.left = self._recuperar(node.left)
        if node.left is not None:
            node.left.parent = node

        node.right = self._recuperar(node.right)
        if node.right is not None:
            node.right.parent = node

        # Actualizar altura y balancear
        node.update_height()
        return self._balance(node)

    # =========================================================
    # DIBUJAR
    # =========================================================

    def dibujar(self, mostrar_info=False):
        """
        Dibuja el árbol en consola de forma horizontal.

        Args:
            mostrar_info: Si True, muestra altura y factor de balance.
        """
        if self.root is None:
            print("El árbol está vacío")
        else:
            modo = "ESTRÉS" if self.modo_estres else "NORMAL"
            print(f"\nÁrbol AVL [{modo}]:")
            print("-----------")
            self._dibujar(self.root, "", "R", mostrar_info)

    def _dibujar(self, node, espacio, posicion, mostrar_info):

        if node is not None:

            # Primero el hijo derecho
            self._dibujar(node.right, espacio + "     ", "D", mostrar_info)

            # Etiqueta del nodo
            if mostrar_info:
                etiqueta = (
                    f"{node.event.id_evento} "
                    f"(h={node.height}, fb={node.balance_factor})"
                )
            else:
                etiqueta = str(node.event.id_evento)

            print(espacio + posicion + "── " + etiqueta)

            # Finalmente el hijo izquierdo
            self._dibujar(node.left, espacio + "     ", "I", mostrar_info)
