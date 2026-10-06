# structure/node.py


class Node:

    def __init__(self, event):
        self.event = event
        self.left = None
        self.right = None
        self.parent = None
        self.height = 0

    def is_leaf(self):
        return self.left is None and self.right is None

    def get_right_child(self):
        return self.right

    def get_left_child(self):
        return self.left

    def get_value(self):
        return self.event.event_id

    # =========================
    # AVL HELPERS
    # =========================

    def update_height(self):
        """Recalculates the height from the children."""
        left_h = self.left.height if self.left else -1
        right_h = self.right.height if self.right else -1
        self.height = 1 + max(left_h, right_h)

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
    def balance_factor(self):
        """Left height - right height."""
        left_h = self.left.height if self.left else -1
        right_h = self.right.height if self.right else -1
        return left_h - right_h

    def __repr__(self):
        return (
            f"Node(id={self.event.event_id}, h={self.height}, "
            f"fb={self.balance_factor})"
        )