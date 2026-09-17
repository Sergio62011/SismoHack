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

    def getHijoDerecho(self):
        return self.right

    def getHijoIzquierdo(self):
        return self.left

    def getValor(self):
        return self.event.id_evento

    # =========================
    # AVL HELPERS
    # =========================

    def update_height(self):
        """Recalcula la altura según los hijos."""
        left_h = self.left.height if self.left else -1
        right_h = self.right.height if self.right else -1
        self.height = 1 + max(left_h, right_h)

    @property
    def balance_factor(self):
        """Altura izquierda - altura derecha."""
        left_h = self.left.height if self.left else -1
        right_h = self.right.height if self.right else -1
        return left_h - right_h

    def __repr__(self):
        return f"Node(id={self.event.id_evento}, h={self.height}, fb={self.balance_factor})"