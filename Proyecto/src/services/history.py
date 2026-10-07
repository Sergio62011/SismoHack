# Módulo history: contiene la lógica relacionada con history.
# Representa Action y agrupa sus datos y operaciones.
class Action:
    # Define init.
    def __init__(self, description, previous_state):
        self.description = description
        self.previous_state = previous_state


# Representa History y agrupa sus datos y operaciones.
class History:
    # Define init.
    def __init__(self):
        self._stack = []

    # Gestiona record action.
    def record_action(self, action):
        self._stack.append(action)

    # Gestiona undo.
    def undo(self):
        if not self._stack:
            return None
        return self._stack.pop()

    # Gestiona is empty.
    def is_empty(self):
        return len(self._stack) == 0

    # Gestiona count.
    def count(self):
        return len(self._stack)