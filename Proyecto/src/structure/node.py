# Módulo node: contiene la lógica relacionada con node.
# structure/node.py


# Representa Node y agrupa sus datos y operaciones.
class Node:

    # Define init.
    def __init__(self, event):
        self.event = event
        self.left = None
        self.right = None
        self.parent = None
        self.height = 0

    # Gestiona is leaf.
    def is_leaf(self):
        return self.left is None and self.right is None

    # Gestiona get right child.
    def get_right_child(self):
        return self.right

    # Gestiona get left child.
    def get_left_child(self):
        return self.left

    # Gestiona get value.
    def get_value(self):
        return self.event.event_id

    # =========================
    # AVL HELPERS
    # =========================

    # Gestiona update height.
    def update_height(self):
        """Recalculates the height from the children."""
        left_h = self.left.height if self.left else -1
        right_h = self.right.height if self.right else -1
        self.height = 1 + max(left_h, right_h)

    # Gestiona copy.
    def copy(self, new_parent=None):
        new = Node(self.event.copy())
        new.height = self.height
        new.parent = new_parent

        if self.left is not None:
            new.left = self.left.copy(new_parent=new)

        if self.right is not None:
            new.right = self.right.copy(new_parent=new)

        return new

    @property
    # Gestiona balance factor.
    def balance_factor(self):
        """Left height - right height."""
        left_h = self.left.height if self.left else -1
        right_h = self.right.height if self.right else -1
        return left_h - right_h

    # Define repr.
    def __repr__(self):
        return (
            f"Node(id={self.event.event_id}, h={self.height}, "
            f"fb={self.balance_factor})"
        )