# Módulo avl: contiene la lógica relacionada con avl.
# structure/avl.py
from .node import Node


# Representa AVL y agrupa sus datos y operaciones.
class AVL:
    """
    AVL ordered by key K = (priority, magnitude, id).

    The tree itself does NOT validate identifier uniqueness. That is the
    responsibility of the business layer, which owns the id index. This
    keeps every insertion O(log n) instead of O(n).
    """

    # Define init.
    def __init__(self):
        self.root = None
        self.stress_mode = False
        self.rotations_performed = 0
        self.ll_cases = 0
        self.rr_cases = 0
        self.lr_cases = 0
        self.rl_cases = 0
        self.single_left_rotations = 0
        self.single_right_rotations = 0
        self.rotations_last_operation = []
        self.recovery_passes = 0
        self.recovery_nodes_visited = 0

    # =========================================================
    # INSERT
    # =========================================================

    # Gestiona insert.
    def insert(self, event):
        self.rotations_last_operation = []

        if self.root is None:
            self.root = Node(event)
            self.root.parent = None
            return

        self.root = self._insert(self.root, event)
        self.root.parent = None

    # Gestiona insert.
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
            raise ValueError(
                f"Duplicate event: key {event.calculate_key()}"
            )

        node.update_height()

        if self.stress_mode:
            return node

        return self._balance(node)

    # =========================================================
    # BALANCE
    # =========================================================

    # Gestiona balance.
    def _balance(self, node):
        bf = node.balance_factor

        if bf > 1 and node.left is not None and node.left.balance_factor >= 0:
            self.rotations_last_operation.append("LL")
            self.ll_cases += 1
            self.single_right_rotations += 1
            return self._rotate_right(node)

        if bf > 1 and node.left is not None and node.left.balance_factor < 0:
            self.rotations_last_operation.append("LR")
            self.lr_cases += 1
            self.single_left_rotations += 1
            self.single_right_rotations += 1
            node.left = self._rotate_left(node.left)
            if node.left is not None:
                node.left.parent = node
            return self._rotate_right(node)

        if bf < -1 and node.right is not None and node.right.balance_factor <= 0:
            self.rotations_last_operation.append("RR")
            self.rr_cases += 1
            self.single_left_rotations += 1
            return self._rotate_left(node)

        if bf < -1 and node.right is not None and node.right.balance_factor > 0:
            self.rotations_last_operation.append("RL")
            self.rl_cases += 1
            self.single_right_rotations += 1
            self.single_left_rotations += 1
            node.right = self._rotate_right(node.right)
            if node.right is not None:
                node.right.parent = node
            return self._rotate_left(node)

        return node

    # =========================================================
    # ROTATIONS
    # =========================================================

    # Gestiona rotate right.
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

        self.rotations_performed += 1
        return y

    # Gestiona rotate left.
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

        self.rotations_performed += 1
        return y

    # =========================================================
    # SEARCH BY KEY
    # =========================================================

    # Gestiona search.
    def search(self, key):
        return self._search(self.root, key)

    # Gestiona search.
    def _search(self, node, key):
        if node is None:
            return None

        node_key = node.event.calculate_key()

        if key == node_key:
            return node
        if key < node_key:
            return self._search(node.left, key)
        return self._search(node.right, key)

    # =========================================================
    # TRAVERSALS
    # =========================================================

    # Gestiona pre order.
    def pre_order(self):
        result = []
        self._pre_order(self.root, result)
        return result

    # Gestiona pre order.
    def _pre_order(self, node, result):
        if node is not None:
            result.append(node.event)
            self._pre_order(node.left, result)
            self._pre_order(node.right, result)

    # Gestiona in order.
    def in_order(self):
        result = []
        self._in_order(self.root, result)
        return result

    # Gestiona in order.
    def _in_order(self, node, result):
        if node is not None:
            self._in_order(node.left, result)
            result.append(node.event)
            self._in_order(node.right, result)

    # Gestiona post order.
    def post_order(self):
        result = []
        self._post_order(self.root, result)
        return result

    # Gestiona post order.
    def _post_order(self, node, result):
        if node is not None:
            self._post_order(node.left, result)
            self._post_order(node.right, result)
            result.append(node.event)

    # Gestiona breadth first.
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

    # Gestiona reverse in order.
    def reverse_in_order(self):
        """Descending order by key."""
        result = []
        self._reverse_in_order(self.root, result)
        return result

    # Gestiona reverse in order.
    def _reverse_in_order(self, node, result):
        if node is not None:
            self._reverse_in_order(node.right, result)
            result.append(node.event)
            self._reverse_in_order(node.left, result)

    # =========================================================
    # METRICS
    # =========================================================

    # Gestiona height.
    def height(self):
        return self.root.height if self.root else -1

    # Gestiona size.
    def size(self):
        return self._size(self.root)

    # Gestiona size.
    def _size(self, node):
        if node is None:
            return 0
        return 1 + self._size(node.left) + self._size(node.right)

    # Gestiona number of leaves.
    def number_of_leaves(self):
        return self._number_of_leaves(self.root)

    # Gestiona number of leaves.
    def _number_of_leaves(self, node):
        if node is None:
            return 0
        if node.is_leaf():
            return 1
        return (
            self._number_of_leaves(node.left)
            + self._number_of_leaves(node.right)
        )

    # Gestiona node depth.
    def node_depth(self, key):
        """Depth of a node by key (root = 0). Returns -1 if absent."""
        return self._node_depth(self.root, key, 0)

    # Gestiona node depth.
    def _node_depth(self, node, key, depth):
        if node is None:
            return -1

        node_key = node.event.calculate_key()
        if key == node_key:
            return depth
        if key < node_key:
            return self._node_depth(node.left, key, depth + 1)
        return self._node_depth(node.right, key, depth + 1)

    # Gestiona nodes per level.
    def nodes_per_level(self):
        result = {}
        self._nodes_per_level(self.root, 0, result)
        return result

    # Gestiona nodes per level.
    def _nodes_per_level(self, node, level, result):
        if node is None:
            return
        result[level] = result.get(level, 0) + 1
        self._nodes_per_level(node.left, level + 1, result)
        self._nodes_per_level(node.right, level + 1, result)

    # Gestiona update heights.
    def update_heights(self):
        self._update_heights(self.root)

    # Gestiona update heights.
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

    # Gestiona find minimum.
    def find_minimum(self, node):
        current = node
        while current is not None and current.left is not None:
            current = current.left
        return current

    # Gestiona find maximum.
    def find_maximum(self, node):
        current = node
        while current is not None and current.right is not None:
            current = current.right
        return current

    # =========================================================
    # DELETE
    # =========================================================

    # Gestiona delete.
    def delete(self, key):
        self.rotations_last_operation = []
        self.root = self._delete(self.root, key)
        if self.root is not None:
            self.root.parent = None

    # Gestiona delete.
    def _delete(self, node, key):
        if node is None:
            return None

        node_key = node.event.calculate_key()

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
                node.right, successor.event.calculate_key()
            )
            if node.right is not None:
                node.right.parent = node

        node.update_height()

        if self.stress_mode:
            return node

        return self._balance(node)

    # =========================================================
    # STRESS MODE
    # =========================================================

    # Gestiona enable stress mode.
    def enable_stress_mode(self):
        self.stress_mode = True

    # Gestiona disable stress mode.
    def disable_stress_mode(self):
        self.stress_mode = False

    # =========================================================
    # GLOBAL RECOVERY
    # =========================================================

    # Gestiona recover balance.
    def recover_balance(self):
        self.rotations_last_operation = []
        self.recovery_passes = 0
        self.recovery_nodes_visited = 0
        self.stress_mode = False

        if self.root is None:
            return

        max_passes = self.size() * 2 + 5
        passes = 0
        while passes < max_passes:
            self.root = self._recover_pass(self.root)
            self.root.parent = None
            self.recovery_passes += 1
            if self._is_avl(self.root):
                break
            passes += 1

        self.stress_mode = False

    # Gestiona recover pass.
    def _recover_pass(self, node):
        if node is None:
            return None

        self.recovery_nodes_visited += 1

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

    # Gestiona is avl.
    def _is_avl(self, node):
        if node is None:
            return True
        if abs(node.balance_factor) > 1:
            return False
        return self._is_avl(node.left) and self._is_avl(node.right)

    # Gestiona copy.
    def copy(self):
        new = AVL()
        new.stress_mode = self.stress_mode
        new.rotations_performed = self.rotations_performed
        new.rotations_last_operation = list(self.rotations_last_operation)
        new.ll_cases = self.ll_cases
        new.rr_cases = self.rr_cases
        new.lr_cases = self.lr_cases
        new.rl_cases = self.rl_cases
        new.single_left_rotations = self.single_left_rotations
        new.single_right_rotations = self.single_right_rotations

        if self.root is not None:
            new.root = self.root.copy(new_parent=None)

        return new

    # Gestiona draw.
    def draw(self, show_info=False):
        if self.root is None:
            print("The tree is empty")
            return

        mode = "STRESS" if self.stress_mode else "NORMAL"
        print(f"\nAVL tree [{mode}]:")
        print("-----------")
        self._draw(self.root, "", "R", show_info)

    # Gestiona draw.
    def _draw(self, node, space, position, show_info):
        if node is not None:
            self._draw(node.right, space + "     ", "R", show_info)

            if show_info:
                label = (
                    f"{node.event.event_id} "
                    f"(h={node.height}, fb={node.balance_factor})"
                )
            else:
                label = str(node.event.event_id)

            print(space + position + "── " + label)

            self._draw(node.left, space + "     ", "L", show_info)