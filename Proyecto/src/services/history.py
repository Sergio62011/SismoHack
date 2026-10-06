class Action:
    def __init__(self, description, previous_state):
        self.description = description
        self.previous_state = previous_state


class History:
    def __init__(self):
        self._stack = []

    def record_action(self, action):
        self._stack.append(action)

    def undo(self):
        if not self._stack:
            return None
        return self._stack.pop()

    def is_empty(self):
        return len(self._stack) == 0

    def count(self):
        return len(self._stack)