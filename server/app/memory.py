import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from datetime import datetime, timedelta

class MessageRole(Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"

class FieldStatus(Enum):
    PENDING = "pending"
    COLLECTED = "collected"
    REFUSED = "refused"
    INVALID = "invalid"
    SKIPPED = "skipped"

@dataclass
class Message:
    role: MessageRole
    content: str
    timestamp: float = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.metadata is None:
            self.metadata = {}

@dataclass
class FieldState:
    name: str
    value: Optional[str] = None
    status: FieldStatus = FieldStatus.PENDING
    validation_errors: List[str] = None
    attempt_count: int = 0
    last_attempt: Optional[float] = None
    user_refused: bool = False
    skip_requested: bool = False

    def __post_init__(self):
        if self.validation_errors is None:
            self.validation_errors = []

class SessionState:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages: List[Message] = []
        self.fields: Dict[str, FieldState] = {}
        self.created_at = time.time()
        self.last_activity = time.time()
        self.completed = False
        self.current_field = None
        self.context = {
            "user_frustration_level": 0,
            "total_refusals": 0,
            "consecutive_errors": 0,
            "conversation_phase": "greeting"  # greeting, collecting, completing, error_recovery
        }
        self._lock = threading.Lock()

    def add_message(self, role: MessageRole, content: str, metadata: Dict[str, Any] = None):
        """Thread-safe message addition"""
        with self._lock:
            message = Message(role=role, content=content, metadata=metadata or {})
            self.messages.append(message)
            self.last_activity = time.time()
            return message

    def update_field(self, field_name: str, value: str = None, status: FieldStatus = None, 
                    validation_errors: List[str] = None):
        """Thread-safe field update"""
        with self._lock:
            if field_name not in self.fields:
                self.fields[field_name] = FieldState(name=field_name)
            
            field = self.fields[field_name]
            if value is not None:
                field.value = value
            if status is not None:
                field.status = status
            if validation_errors is not None:
                field.validation_errors = validation_errors
            
            field.last_attempt = time.time()
            if status in [FieldStatus.INVALID, FieldStatus.REFUSED]:
                field.attempt_count += 1

    def get_conversation_context(self, max_messages: int = 10) -> List[Dict[str, str]]:
        """Get recent conversation history for LLM context"""
        with self._lock:
            recent_messages = self.messages[-max_messages:] if self.messages else []
            return [
                {
                    "role": msg.role.value,
                    "content": msg.content,
                    "timestamp": msg.timestamp
                }
                for msg in recent_messages
            ]

    def get_field_summary(self) -> Dict[str, Any]:
        """Get current field collection status"""
        with self._lock:
            return {
                field_name: {
                    "value": field.value,
                    "status": field.status.value,
                    "attempts": field.attempt_count,
                    "refused": field.user_refused,
                    "skip_requested": field.skip_requested
                }
                for field_name, field in self.fields.items()
            }

    def increment_frustration(self):
        """Track user frustration for adaptive responses"""
        with self._lock:
            self.context["user_frustration_level"] = min(5, self.context["user_frustration_level"] + 1)

    def reset_frustration(self):
        """Reset frustration when interaction goes well"""
        with self._lock:
            self.context["user_frustration_level"] = max(0, self.context["user_frustration_level"] - 1)

class MemoryStore:
    def __init__(self, session_timeout_hours: int = 24):
        self.sessions: Dict[str, SessionState] = {}
        self.session_timeout = session_timeout_hours * 3600  # Convert to seconds
        self._lock = threading.RLock()
        self._start_cleanup_thread()

    def get_or_create_session(self, session_id: str) -> SessionState:
        """Get existing session or create new one"""
        with self._lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = SessionState(session_id)
            else:
                # Update last activity
                self.sessions[session_id].last_activity = time.time()
            
            return self.sessions[session_id]

    def delete_session(self, session_id: str) -> bool:
        """Delete a specific session"""
        with self._lock:
            return self.sessions.pop(session_id, None) is not None

    def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions"""
        current_time = time.time()
        expired_sessions = []
        
        with self._lock:
            for session_id, session in self.sessions.items():
                if current_time - session.last_activity > self.session_timeout:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self.sessions[session_id]
        
        return len(expired_sessions)

    def get_session_stats(self) -> Dict[str, Any]:
        """Get memory store statistics"""
        with self._lock:
            current_time = time.time()
            active_sessions = 0
            total_messages = 0
            
            for session in self.sessions.values():
                if current_time - session.last_activity <= 3600:  # Active in last hour
                    active_sessions += 1
                total_messages += len(session.messages)
            
            return {
                "total_sessions": len(self.sessions),
                "active_sessions": active_sessions,
                "total_messages": total_messages,
                "memory_usage_mb": self._estimate_memory_usage()
            }

    def _estimate_memory_usage(self) -> float:
        """Rough estimate of memory usage in MB"""
        try:
            # Very rough estimation
            total_chars = 0
            for session in self.sessions.values():
                for message in session.messages:
                    total_chars += len(message.content)
                for field in session.fields.values():
                    if field.value:
                        total_chars += len(field.value)
            
            # Assume ~2 bytes per character + overhead
            return (total_chars * 2 + len(self.sessions) * 1000) / (1024 * 1024)
        except Exception:
            return 0.0

    def _start_cleanup_thread(self):
        """Start background thread for session cleanup"""
        def cleanup_worker():
            while True:
                try:
                    time.sleep(3600)  # Run every hour
                    expired = self.cleanup_expired_sessions()
                    if expired > 0:
                        print(f"Cleaned up {expired} expired sessions")
                except Exception as e:
                    print(f"Error in session cleanup: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()

    def export_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Export session data for backup/analysis"""
        with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return None
            
            return {
                "session_id": session.session_id,
                "created_at": session.created_at,
                "last_activity": session.last_activity,
                "completed": session.completed,
                "messages": [asdict(msg) for msg in session.messages],
                "fields": {name: asdict(field) for name, field in session.fields.items()},
                "context": session.context.copy()
            }

# Global memory store instance
memory_store = MemoryStore()