# memory.py

class MemoryStore:
    def __init__(self):
        self.sessions = {}

    def add_message(self, session_id: str, role: str, content: str):
        """Add a message to a session. Create session if not exists."""
        if session_id not in self.sessions:
            self.sessions[session_id] = []

        self.sessions[session_id].append({"role": role, "content": content})

    def get_messages(self, session_id: str):
        """Get all messages in a session."""
        if session_id not in self.sessions:
            return []
        return self.sessions[session_id]

    def clear(self):
        """Clear all sessions."""
        self.sessions = {}
