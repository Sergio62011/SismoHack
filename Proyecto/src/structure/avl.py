# structure/avl.py
from .node import Node


class AVL:
    """
    AVL ordered by key K = (priority, magnitude, id).

    The tree itself does NOT validate identifier uniqueness. That is the
    responsibility of the business layer, which owns the id index. This
    keeps every insertion O(log n) instead of O(n).
    """

    def __init__(self):
        self.root = None
        self.modo_estres = False
        self.rotaciones_realizadas = 0
        self.rotaciones_ultima_operacion = []

    # =========================================================
    # INSERT
    # =========================================================

    def insert(self, event):
        self.rotaciones_ultima_operacion = []

        if self.root is None:
            self.root = Node(event)
            self.root.parent = None
            return

        self.root = self._insert(self.root, event)
        self.root.parent = None

    def _insert(self, node, event):
        if node is None:
            return Node(event)

        if event < node.event:
            node.left = self._insert(node.left, event)
            if node.left is not None:
                node.left.parent = node

        elif event > node.event:
            node.right = self._insert(node.right, event)
            if node.right is not None:
                node.right.parent = node

        else:
            raise ValueError(f"Evento duplicado: clave {event.calcular_clave()}")

        node.update_height()

        if self.modo_estres:
            return node

        return self._balance(node)

    # =========================================================
    # BALANCE
    # =========================================================

    def _balance(self, node):
        fb = node.balance_factor

        # LL
        if fb > 1 and node.left is not None and node.left.balance_factor >= 0:
            self.rotaciones_ultima_operacion.append("LL")
            return self._rotate_right(node)

        # LR
        if fb > 1 and node.left is not None and node.left.balance_factor < 0:
            self.rotaciones_ultima_operacion.append("LR")
            node.left = self._rotate_left(node.left)
            if node.left is not None:
                node.left.parent = node
            return self._rotate_right(node)

        # RR
        if fb < -1 and node.right is not None and node.right.balance_factor <= 0:
            self.rotaciones_ultima_operacion.append("RR")
            return self._rotate_left(node)

        # RL
        if fb < -1 and node.right is not None and node.right.balance_factor > 0:
            self.rotaciones_ultima_operacion.append("RL")
            node.right = self._rotate_right(node.right)
            if node.right is not None:
                node.right.parent = node
            return self._rotate_left(node)

        return node

    # =========================================================
    # ROTATIONS
    # =========================================================

    def _rotate_right(self, z):
        y = z.left
        if y is None:
            return z

        T3 = y.right

        y.right = z
        z.left = T3

        y.parent = z.parent
        z.parent = y
        if T3 is not None:
            T3.parent = z

        z.update_height()
        y.update_height()

        self.rotaciones_realizadas += 1
        return y

    def _rotate_left(self, z):
        y = z.right
        if y is None:
            return z

        T2 = y.left

        y.left = z
        z.right = T2

        y.parent = z.parent
        z.parent = y
        if T2 is not None:
            T2.parent = z

        z.update_height()
        y.update_height()

        self.rotaciones_realizadas += 1
        return y

    # =========================================================
    # SEARCH BY KEY
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
    # TRAVERSALS
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

    def in_order(self):
        result = []
        self._in_order(self.root, result)
        return result

    def _in_order(self, node, result):
        if node is not None:
            self._in_order(node.left, result)
            result.append(node.event)
            self._in_order(node.right, result)

    def post_order(self):
        result = []
        self._post_order(self.root, result)
        return result

    def _post_order(self, node, result):
        if node is not None:
            self._post_order(node.left, result)
            self._post_order(node.right, result)
            result.append(node.event)

    def breadth_first(self):
        if self.root is None:
            return []

        queue = [self.root]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node.event)
            if node.left is not None:
                queue.append(node.left)
            if node.right is not None:
                queue.append(node.right)

        return result

    def reverse_in_order(self):
        """Descending order by key."""
        result = []
        self._reverse_in_order(self.root, result)
        return result

    def _reverse_in_order(self, node, result):
        if node is not None:
            self._reverse_in_order(node.right, result)
            result.append(node.event)
            self._reverse_in_order(node.left, result)

    # =========================================================
    # METRICS
    # =========================================================

    def height(self):
        return self.root.height if self.root else -1

    def size(self):
        return self._size(self.root)

    def _size(self, node):
        if node is None:
            return 0
        return 1 + self._size(node.left) + self._size(node.right)

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

    def node_depth(self, key):
        """Depth of a node by key (root = 0). Returns -1 if absent."""
        return self._node_depth(self.root, key, 0)

    def _node_depth(self, node, key, depth):
        if node is None:
            return -1

        node_key = node.event.calcular_clave()
        if key == node_key:
            return depth
        if key < node_key:
            return self._node_depth(node.left, key, depth + 1)
        return self._node_depth(node.right, key, depth + 1)

    def nodes_per_level(self):
        result = {}
        self._nodes_per_level(self.root, 0, result)
        return result

    def _nodes_per_level(self, node, level, result):
        if node is None:
            return
        result[level] = result.get(level, 0) + 1
        self._nodes_per_level(node.left, level + 1, result)
        self._nodes_per_level(node.right, level + 1, result)

    def update_heights(self):
        self._update_heights(self.root)

    def _update_heights(self, node):
        if node is None:
            return -1
        left_h = self._update_heights(node.left)
        right_h = self._update_heights(node.right)
        node.height = 1 + max(left_h, right_h)
        return node.height

    # =========================================================
    # MIN / MAX
    # =========================================================

    def find_minimum(self, node):
        current = node
        while current is not None and current.left is not None:
            current = current.left
        return current

    def find_maximum(self, node):
        current = node
        while current is not None and current.right is not None:
            current = current.right
        return current

    # =========================================================
    # DELETE
    # =========================================================

    def delete(self, key):
        self.rotaciones_ultima_operacion = []
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
            # Leaf
            if node.left is None and node.right is None:
                return None

            # Only right child
            if node.left is None:
                node.right.parent = node.parent
                return node.right

            # Only left child
            if node.right is None:
                node.left.parent = node.parent
                return node.left

            # Two children: copy successor event, then delete successor node
            successor = self.find_minimum(node.right)
            node.event = successor.event
            node.right = self._delete(
                node.right, successor.event.calcular_clave()
            )
            if node.right is not None:
                node.right.parent = node

        node.update_height()

        if self.modo_estres:
            return node

        return self._balance(node)

    # =========================================================
    # STRESS MODE
    # =========================================================

    def activar_modo_estres(self):
        self.modo_estres = True

    def desactivar_modo_estres(self):
        self.modo_estres = False

    # =========================================================
    # GLOBAL RECOVERY
    # =========================================================

    def recuperar_balance(self):
        """
        Global recovery. Rebuilds the tree by repeated local rotations
        using a postorder pass. Repeats until AVL property holds.
        """
        self.rotaciones_ultima_operacion = []
        self.modo_estres = False

        if self.root is None:
            return

        max_passes = self.size() * 2 + 5
        passes = 0
        while passes < max_passes:
            self.root = self._recover_pass(self.root)
            self.root.parent = None
            if self._is_avl(self.root):
                break
            passes += 1

        self.modo_estres = False

    def _recover_pass(self, node):
        if node is None:
            return None

        node.left = self._recover_pass(node.left)
        if node.left is not None:
            node.left.parent = node

        node.right = self._recover_pass(node.right)
        if node.right is not None:
            node.right.parent = node

        node.update_height()

        safety = 0
        while abs(node.balance_factor) > 1 and safety < 64:
            node = self._balance(node)
            node.update_height()
            safety += 1

        return node

    def _is_avl(self, node):
        if node is None:
            return True
        if abs(node.balance_factor) > 1:
            return False
        return self._is_avl(node.left) and self._is_avl(node.right)

    # =========================================================
    # DEBUG DRAW
    # =========================================================

    def dibujar(self, mostrar_info=False):
        if self.root is None:
            print("El árbol está vacío")
            return

        modo = "ESTRÉS" if self.modo_estres else "NORMAL"
        print(f"\nÁrbol AVL [{modo}]:")
        print("-----------")
        self._dibujar(self.root, "", "R", mostrar_info)

    def _dibujar(self, node, espacio, posicion, mostrar_info):
        if node is not None:
            self._dibujar(node.right, espacio + "     ", "D", mostrar_info)

            if mostrar_info:
                etiqueta = (
                    f"{node.event.id_evento} "
                    f"(h={node.height}, fb={node.balance_factor})"
                )
            else:
                etiqueta = str(node.event.id_evento)

            print(espacio + posicion + "── " + etiqueta)

            self._dibujar(node.left, espacio + "     ", "I", mostrar_info)