"""
Enhanced Silence Manager with Phone Call Experience
Manages conversation timeouts, silence detection, and automatic question repetition
"""
import time
import asyncio
import logging
import threading
from typing import Dict, Optional, Callable, Any
from enum import Enum
from dataclasses import dataclass
from .language_support import Language

logger = logging.getLogger(__name__)

class SilenceState(Enum):
    WAITING_FOR_RESPONSE = "waiting_for_response"
    REPEATING_QUESTION = "repeating_question" 
    SESSION_TIMEOUT = "session_timeout"
    ACTIVE = "active"

@dataclass
class SilenceSession:
    session_id: str
    language: Language
    current_field: Optional[str]
    last_activity: float
    silence_start: Optional[float]
    repetition_count: int
    state: SilenceState
    callback: Optional[Callable]
    question_text: Optional[str]
    timer_handle: Optional[threading.Timer]

class EnhancedSilenceManager:
    """Enhanced silence manager with phone call-like experience"""
    
    def __init__(self):
        self.sessions: Dict[str, SilenceSession] = {}
        self.silence_timeout = 3.0  # 3 seconds before first prompt
        self.max_repetitions = 3   # Maximum number of question repetitions
        self.repetition_interval = 4.0  # 4 seconds between repetitions
        self.session_timeout = 30.0  # 30 seconds total timeout
        
        # Silence prompts in multiple languages
        self.silence_prompts = {
            Language.ENGLISH: {
                1: "Are you there?",
                2: "Are you still there? Please respond.",
                3: "Hello? I'm waiting for your answer. Should we continue?"
            },
            Language.GUJARATI: {
                1: "તમે ત્યાં છો?",
                2: "તમે હજી પણ ત્યાં છો? કૃપા કરીને જવાબ આપો.",
                3: "હેલો? હું તમારા જવાબની રાહ જોઈ રહ્યો છું. શું આપણે આગળ વધીએ?"
            }
        }
    
    def start_session(self, session_id: str, language: Language, callback: Optional[Callable] = None):
        """Start silence monitoring for a session"""
        if session_id in self.sessions:
            self.stop_session(session_id)
        
        session = SilenceSession(
            session_id=session_id,
            language=language,
            current_field=None,
            last_activity=time.time(),
            silence_start=None,
            repetition_count=0,
            state=SilenceState.ACTIVE,
            callback=callback,
            question_text=None,
            timer_handle=None
        )
        
        self.sessions[session_id] = session
        logger.info(f"Started silence monitoring for session {session_id} in {language.value}")
    
    def stop_session(self, session_id: str):
        """Stop silence monitoring for a session"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            if session.timer_handle:
                session.timer_handle.cancel()
            del self.sessions[session_id]
            logger.info(f"Stopped silence monitoring for session {session_id}")
    
    def update_activity(self, session_id: str):
        """Update last activity time - user has spoken"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.last_activity = time.time()
            session.silence_start = None
            session.repetition_count = 0
            session.state = SilenceState.ACTIVE
            
            # Cancel any pending timer
            if session.timer_handle:
                session.timer_handle.cancel()
                session.timer_handle = None
            
            logger.debug(f"Activity updated for session {session_id}")
    
    def start_silence_detection(self, session_id: str, callback: Optional[Callable] = None, question_text: Optional[str] = None):
        """Start detecting silence after asking a question"""
        if session_id not in self.sessions:
            logger.warning(f"Session {session_id} not found for silence detection")
            return
        
        session = self.sessions[session_id]
        session.callback = callback
        session.question_text = question_text
        session.silence_start = time.time()
        session.repetition_count = 0
        session.state = SilenceState.WAITING_FOR_RESPONSE
        
        # Cancel any existing timer
        if session.timer_handle:
            session.timer_handle.cancel()
        
        # Start silence detection timer
        session.timer_handle = threading.Timer(self.silence_timeout, self._handle_silence_timeout, [session_id])
        session.timer_handle.start()
        
        logger.info(f"Started silence detection for session {session_id}")
    
    def _handle_silence_timeout(self, session_id: str):
        """Handle silence timeout - trigger question repetition"""
        if session_id not in self.sessions:
            return
        
        session = self.sessions[session_id]
        current_time = time.time()
        
        # Check if we've exceeded maximum repetitions
        if session.repetition_count >= self.max_repetitions:
            session.state = SilenceState.SESSION_TIMEOUT
            self._trigger_session_timeout(session_id)
            return
        
        # Check total session timeout
        if current_time - session.silence_start > self.session_timeout:
            session.state = SilenceState.SESSION_TIMEOUT
            self._trigger_session_timeout(session_id)
            return
        
        # Increment repetition count and generate prompt
        session.repetition_count += 1
        session.state = SilenceState.REPEATING_QUESTION
        
        # Generate appropriate silence prompt
        prompt_text = self._generate_silence_prompt(session)
        
        # Trigger callback with silence prompt
        if session.callback:
            try:
                session.callback(session_id, prompt_text, session.language)
            except Exception as e:
                logger.error(f"Silence callback failed for session {session_id}: {e}")
        
        # Schedule next repetition
        session.timer_handle = threading.Timer(self.repetition_interval, self._handle_silence_timeout, [session_id])
        session.timer_handle.start()
        
        logger.info(f"Silence prompt {session.repetition_count}/{self.max_repetitions} sent for session {session_id}")
    
    def _generate_silence_prompt(self, session: SilenceSession) -> str:
        """Generate appropriate silence prompt based on repetition count"""
        prompts = self.silence_prompts.get(session.language, self.silence_prompts[Language.ENGLISH])
        
        # Get prompt based on repetition count
        prompt = prompts.get(session.repetition_count, prompts[1])
        
        # Add question context if available
        if session.question_text and session.repetition_count == 1:
            if session.language == Language.GUJARATI:
                return f"{prompt} {session.question_text}"
            else:
                return f"{prompt} {session.question_text}"
        
        return prompt
    
    def _trigger_session_timeout(self, session_id: str):
        """Handle complete session timeout"""
        if session_id not in self.sessions:
            return
        
        session = self.sessions[session_id]
        
        # Generate timeout message
        if session.language == Language.GUJARATI:
            timeout_msg = "સેશન સમાપ્ત થઈ ગયો છે. કૃપા કરીને વાતચીત ફરીથી શરૂ કરો."
        else:
            timeout_msg = "Session timeout. Please restart the conversation."
        
        # Trigger callback with timeout message
        if session.callback:
            try:
                session.callback(session_id, timeout_msg, session.language)
            except Exception as e:
                logger.error(f"Timeout callback failed for session {session_id}: {e}")
        
        # Stop session
        self.stop_session(session_id)
        
        logger.info(f"Session {session_id} timed out after {self.max_repetitions} repetitions")
    
    def update_language(self, session_id: str, language: Language):
        """Update language for a session"""
        if session_id in self.sessions:
            self.sessions[session_id].language = language
            logger.info(f"Updated language to {language.value} for session {session_id}")
    
    def update_current_field(self, session_id: str, field_name: str):
        """Update current field being processed"""
        if session_id in self.sessions:
            self.sessions[session_id].current_field = field_name
            logger.debug(f"Updated current field to {field_name} for session {session_id}")
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics about active sessions"""
        active_sessions = len(self.sessions)
        sessions_by_state = {}
        sessions_by_language = {}
        
        for session in self.sessions.values():
            # Count by state
            state = session.state.value
            sessions_by_state[state] = sessions_by_state.get(state, 0) + 1
            
            # Count by language
            lang = session.language.value
            sessions_by_language[lang] = sessions_by_language.get(lang, 0) + 1
        
        return {
            "active_sessions": active_sessions,
            "sessions_by_state": sessions_by_state,
            "sessions_by_language": sessions_by_language,
            "silence_timeout": self.silence_timeout,
            "max_repetitions": self.max_repetitions
        }
    
    def cleanup_expired_sessions(self, max_age_hours: float = 24.0) -> int:
        """Clean up old sessions"""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            if current_time - session.last_activity > max_age_seconds:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self.stop_session(session_id)
        
        logger.info(f"Cleaned up {len(expired_sessions)} expired silence sessions")
        return len(expired_sessions)

# Global enhanced silence manager instance
silence_manager = EnhancedSilenceManager()