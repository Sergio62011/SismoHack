from .node import Node


class BST:

    def __init__(self):
        self.root = None

    # =========================
    # INSERT
    # =========================

    def insert(self, event):
        # The identifier is the earthquake identity, not merely a component
        # of its key. It cannot appear twice even after a key change.
        if self._find_by_id(self.root, event.id_evento) is not None:
            raise ValueError(f"Evento duplicado: ID {event.id_evento}")

        if self.root is None:
            self.root = Node(event)
        else:
            self._insert(self.root, event)

    def _find_by_id(self, node, event_id):
        """Searches an identity across the whole tree.

        The BST is ordered by (priority, magnitude, identifier), so an ID
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

        if event < node.event:

            if node.left is None:
                node.left = Node(event)
                node.left.parent = node
            else:
                self._insert(node.left, event)

        elif event > node.event:

            if node.right is None:
                node.right = Node(event)
                node.right.parent = node
            else:
                self._insert(node.right, event)
        else:
            raise ValueError(f"Evento duplicado: ID {event.id_evento}")
    # =========================
    # SEARCH
    # =========================

    def search(self, key):
        return self._search(self.root, key)

    def _search(self, node, key):

        if node is None:
            return None

        if key == node.event.calcular_clave():
            return node

        if key < node.event.calcular_clave():
            return self._search(node.left, key)

        return self._search(node.right, key)

    # =========================
    # PREORDER
    # =========================

    def pre_order(self):
        result = []
        self._pre_order(self.root, result)
        return result

    def _pre_order(self, node, result):

        if node is not None:
            result.append(node.event)
            self._pre_order(node.left, result)
            self._pre_order(node.right, result)

    # =========================
    # INORDER
    # =========================

    def in_order(self):
        result = []
        self._in_order(self.root, result)
        return result

    def _in_order(self, node, result):

        if node is not None:
            self._in_order(node.left, result)
            result.append(node.event)
            self._in_order(node.right, result)

    # =========================
    # POSTORDER
    # =========================

    def post_order(self):
        result = []
        self._post_order(self.root, result)
        return result

    def _post_order(self, node, result):

        if node is not None:
            self._post_order(node.left, result)
            self._post_order(node.right, result)
            result.append(node.event)

    # =========================
    # LEVEL ORDER / BFS
    # =========================

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

    # =========================
    # HEIGHT
    # =========================

    def height(self):
        return self._height(self.root)

    def _height(self, node):

        if node is None:
            return -1

        return 1 + max(
            self._height(node.left),
            self._height(node.right)
        )

    # =========================
    # UPDATE HEIGHTS
    # =========================

    def update_heights(self):
        self._update_heights(self.root)

    def _update_heights(self, node):

        if node is None:
            return -1

        left_height = self._update_heights(node.left)
        right_height = self._update_heights(node.right)

        node.height = 1 + max(
            left_height,
            right_height
        )

        return node.height

    # =========================
    # SIZE / NUMBER OF NODES
    # =========================

    def size(self):
        return self._size(self.root)

    def _size(self, node):

        if node is None:
            return 0

        return (
            1
            + self._size(node.left)
            + self._size(node.right)
        )

    # =========================
    # NUMBER OF LEAVES
    # =========================

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

    # =========================
    # NODE LEVEL
    # =========================

    def node_level(self, key):
        return self._node_level(self.root, key, 0)

    def _node_level(self, node, key, level):

        if node is None:
            return -1

        if key == node.event.calcular_clave():
            return level

        if key < node.event.calcular_clave():
            return self._node_level(
                node.left,
                key,
                level + 1
            )

        return self._node_level(
            node.right,
            key,
            level + 1
        )

    # =========================
    # NODES PER LEVEL
    # =========================

    def nodes_per_level(self):

        result = {}

        self._nodes_per_level(
            self.root,
            0,
            result
        )

        return result

    def _nodes_per_level(self, node, level, result):

        if node is None:
            return

        if level not in result:
            result[level] = 0

        result[level] += 1

        self._nodes_per_level(
            node.left,
            level + 1,
            result
        )

        self._nodes_per_level(
            node.right,
            level + 1,
            result
        )

    # =========================
    # ROOT-TO-LEAF PATHS
    # =========================

    def root_to_leaf_paths(self):

        result = []

        self._root_to_leaf_paths(
            self.root,
            [],
            result
        )

        return result

    def _root_to_leaf_paths(
        self,
        node,
        path,
        result
    ):

        if node is None:
            return

        path.append(node.event)

        if node.left is None and node.right is None:
            result.append(path.copy())

        else:

            self._root_to_leaf_paths(
                node.left,
                path,
                result
            )

            self._root_to_leaf_paths(
                node.right,
                path,
                result
            )

        path.pop()

    # =========================
    # BALANCE FACTOR
    # =========================

    def balance_factor(self, node):

        if node is None:
            return 0

        left_height = self._height(node.left)
        right_height = self._height(node.right)

        return left_height - right_height

    # =========================
    # MINIMUM
    # =========================

    def find_minimum(self, node):

        current = node

        while current.left is not None:
            current = current.left

        return current

    # =========================
    # MAXIMUM
    # =========================

    def find_maximum(self, node):

        current = node

        while current.right is not None:
            current = current.right

        return current

    # =========================
    # DELETE
    # =========================

    def delete(self, key):
        self.root = self._delete(self.root, key)

        if self.root is not None:
            self.root.parent = None

    def _delete(self, node, key):

        if node is None:
            return None

        if key < node.event.calcular_clave():

            node.left = self._delete(
                node.left,
                key
            )

            if node.left is not None:
                node.left.parent = node

        elif key > node.event.calcular_clave():

            node.right = self._delete(
                node.right,
                key
            )

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

        return node
    
    def dibujar(self):
        """Dibuja el árbol en consola de forma horizontal (raíz a la izquierda)."""
        if self.root is None:
            print("El árbol está vacío")
        else:
            print("\nÁrbol BST:")
            print("-----------")
            self._dibujar(self.root, "", "R")

    def _dibujar(self, node, espacio, posicion):
        """Método auxiliar recursivo para dibujar el árbol."""
        if node is not None:
            # Primero el hijo derecho (va arriba)
            self._dibujar(node.right, espacio + "     ", "D")

            # Luego el nodo actual
            print(
                espacio +
                posicion + "── " +
                str(node.event.id_evento)
            )

            # Finalmente el hijo izquierdo (va abajo)
            self._dibujar(node.left, espacio + "     ", "I")
