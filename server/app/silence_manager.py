"""
Silence Detection and Management
Handles "are you there?" prompts after periods of silence
"""
import time
import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from .language_support import Language, language_support

logger = logging.getLogger(__name__)

class SilenceState(Enum):
    ACTIVE = "active"
    WAITING = "waiting"
    PROMPTING = "prompting"
    TIMEOUT = "timeout"

@dataclass
class SilenceSession:
    session_id: str
    last_user_activity: float
    prompt_count: int = 0
    state: SilenceState = SilenceState.ACTIVE
    language: Language = Language.ENGLISH
    current_field: Optional[str] = None
    max_prompts: int = 3
    silence_threshold: float = 3.0  # 3 seconds
    prompt_interval: float = 3.0    # 3 seconds between prompts

class SilenceManager:
    """Manages silence detection and automatic prompting"""
    
    def __init__(self):
        self.sessions: Dict[str, SilenceSession] = {}
        self.active_timers: Dict[str, asyncio.Task] = {}
        
    def start_session(self, 
                     session_id: str, 
                     language: Language = Language.ENGLISH,
                     current_field: Optional[str] = None) -> None:
        """Start silence monitoring for a session"""
        self.sessions[session_id] = SilenceSession(
            session_id=session_id,
            last_user_activity=time.time(),
            language=language,
            current_field=current_field
        )
        logger.info(f"Started silence monitoring for session {session_id}")
    
    def update_activity(self, session_id: str) -> None:
        """Update last activity time for a session"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.last_user_activity = time.time()
            session.state = SilenceState.ACTIVE
            session.prompt_count = 0
            
            # Cancel existing timer
            if session_id in self.active_timers:
                self.active_timers[session_id].cancel()
                del self.active_timers[session_id]
            
            logger.debug(f"Updated activity for session {session_id}")
    
    def start_silence_detection(self, 
                              session_id: str, 
                              callback: Callable[[str, str, Language], None]) -> None:
        """Start silence detection with callback for prompts"""
        if session_id not in self.sessions:
            logger.warning(f"Session {session_id} not found for silence detection")
            return
        
        session = self.sessions[session_id]
        
        # Cancel existing timer
        if session_id in self.active_timers:
            self.active_timers[session_id].cancel()
        
        # Start new timer
        self.active_timers[session_id] = asyncio.create_task(
            self._silence_monitor(session, callback)
        )
        
        logger.info(f"Started silence detection for session {session_id}")
    
    async def _silence_monitor(self, 
                              session: SilenceSession, 
                              callback: Callable[[str, str, Language], None]) -> None:
        """Monitor silence and trigger prompts"""
        try:
            while session.state != SilenceState.TIMEOUT and session.prompt_count < session.max_prompts:
                current_time = time.time()
                silence_duration = current_time - session.last_user_activity
                
                if silence_duration >= session.silence_threshold:
                    if session.state == SilenceState.ACTIVE:
                        session.state = SilenceState.WAITING
                        logger.info(f"Session {session.session_id}: Silence detected ({silence_duration:.1f}s)")
                        
                        # Wait a bit more before first prompt
                        await asyncio.sleep(1.0)
                        
                        # Check if user responded during the wait
                        if time.time() - session.last_user_activity >= session.silence_threshold + 1.0:
                            session.state = SilenceState.PROMPTING
                            session.prompt_count += 1
                            
                            # Generate prompt message
                            prompt_message = self._generate_prompt_message(session)
                            
                            # Trigger callback
                            callback(session.session_id, prompt_message, session.language)
                            
                            logger.info(f"Session {session.session_id}: Sent prompt #{session.prompt_count}")
                            
                            # Reset timer for next prompt
                            session.last_user_activity = time.time()
                            session.state = SilenceState.WAITING
                
                # Check every second
                await asyncio.sleep(1.0)
            
            # Handle timeout
            if session.prompt_count >= session.max_prompts:
                session.state = SilenceState.TIMEOUT
                timeout_message = self._generate_timeout_message(session)
                callback(session.session_id, timeout_message, session.language)
                logger.info(f"Session {session.session_id}: Timed out after {session.max_prompts} prompts")
                
        except asyncio.CancelledError:
            logger.debug(f"Silence monitor cancelled for session {session.session_id}")
        except Exception as e:
            logger.error(f"Error in silence monitor for session {session.session_id}: {e}")
    
    def _generate_prompt_message(self, session: SilenceSession) -> str:
        """Generate appropriate prompt message based on session state"""
        if session.prompt_count == 1:
            # First prompt - gentle
            if session.language == Language.GUJARATI:
                return "તમે ત્યાં છો? કૃપા કરીને જવાબ આપો."
            else:
                return "Are you there? Please respond."
                
        elif session.prompt_count == 2:
            # Second prompt - more specific
            if session.current_field:
                field_context = f" for {session.current_field}" if session.language == Language.ENGLISH else f" {session.current_field} માટે"
                if session.language == Language.GUJARATI:
                    return f"કૃપા કરીને{field_context} જવાબ આપો અથવા 'છોડો' કહો."
                else:
                    return f"Please provide your response{field_context} or say 'skip'."
            else:
                if session.language == Language.GUJARATI:
                    return "કૃપા કરીને કંઈક કહો અથવા લખો."
                else:
                    return "Please say something or type your response."
                    
        else:
            # Final prompt - urgent
            if session.language == Language.GUJARATI:
                return "છેલ્લી તક - કૃપા કરીને જવાબ આપો અથવા સત્ર સમાપ્ત થશે."
            else:
                return "Last chance - please respond or the session will timeout."
    
    def _generate_timeout_message(self, session: SilenceSession) -> str:
        """Generate timeout message"""
        timeout_text = language_support.get_ui_text("session_timeout", session.language)
        return timeout_text
    
    def update_language(self, session_id: str, language: Language) -> None:
        """Update language for a session"""
        if session_id in self.sessions:
            self.sessions[session_id].language = language
            logger.info(f"Updated language to {language.value} for session {session_id}")
    
    def update_current_field(self, session_id: str, field_name: Optional[str]) -> None:
        """Update current field being processed"""
        if session_id in self.sessions:
            self.sessions[session_id].current_field = field_name
            logger.debug(f"Updated current field to {field_name} for session {session_id}")
    
    def stop_session(self, session_id: str) -> None:
        """Stop silence monitoring for a session"""
        if session_id in self.active_timers:
            self.active_timers[session_id].cancel()
            del self.active_timers[session_id]
        
        if session_id in self.sessions:
            del self.sessions[session_id]
        
        logger.info(f"Stopped silence monitoring for session {session_id}")
    
    def is_session_active(self, session_id: str) -> bool:
        """Check if session is actively monitored"""
        return session_id in self.sessions and session_id in self.active_timers

# Global silence manager instance
silence_manager = SilenceManager()