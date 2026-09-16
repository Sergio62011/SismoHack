class Node:

    def __init__(self, event):
        self.event = event
        self.left = None
        self.right = None
        self.parent = None
        self.height = 0

    def is_leaf(self):
        return self.left is None and self.right is None