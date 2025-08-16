from typing import Dict, Any
import copy

class MemoryStore:
    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def init_session(self, session_id: str, schema: dict):
        self._sessions[session_id] = {
            "schema": schema,
            "index": 0,
            "form": {},
            "completed": False,
        }

    def require(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self._sessions:
            raise KeyError(f"Session {session_id} not found.")
        return self._sessions[session_id]

    def get_state(self, session_id: str) -> Dict[str, Any]:
        return copy.deepcopy(self.require(session_id))

    def save(self, session_id: str, state: Dict[str, Any]):
        self._sessions[session_id] = copy.deepcopy(state)

    def reset(self, session_id: str):
        self._sessions.pop(session_id, None)
