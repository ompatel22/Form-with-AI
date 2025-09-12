"""
Enhanced Silence Manager with Intelligent Question Repetition
Manages conversation timeouts, silence detection, and context-aware automatic question repetition
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
    context: Optional[Dict[str, Any]]  # Added for intelligent responses

class IntelligentSilenceManager:
    """Enhanced silence manager with context-aware question repetition"""
    
    def __init__(self):
        self.sessions: Dict[str, SilenceSession] = {}
        self.silence_timeout = 3.0  # 3 seconds before first prompt (as requested)
        self.max_repetitions = 3   # Maximum number of question repetitions
        self.repetition_interval = 4.0  # 4 seconds between repetitions
        self.session_timeout = 30.0  # 30 seconds total timeout
        
        # Intelligent silence prompts based on context
        self.context_aware_prompts = {
            Language.ENGLISH: {
                "initial": {
                    1: "I'm here when you're ready.",
                    2: "Are you still there? Take your time.",
                    3: "Hello? I'm waiting for your response. Should we continue with the next question?"
                },
                "form_field": {
                    1: "I'm waiting for your {field_type}. Please respond when ready.",
                    2: "Could you please provide your {field_type}? I'm here to help.",
                    3: "I still need your {field_type} to continue. Are you having trouble with this question?"
                },
                "confirmation": {
                    1: "Please confirm if this information is correct.",
                    2: "I need your confirmation to proceed. Please say yes or no.",
                    3: "Are you still there? Please confirm so we can move forward."
                }
            },
            Language.GUJARATI: {
                "initial": {
                    1: "હું અહીં છું જ્યારે તમે તૈયાર હો.",
                    2: "તમે હજી પણ ત્યાં છો? તમારો સમય લો.",
                    3: "હેલો? હું તમારા જવાબની રાહ જોઈ રહ્યો છું. શું આપણે આગળના પ્રશ્ન સાથે આગળ વધીએ?"
                },
                "form_field": {
                    1: "હું તમારા {field_type} ની રાહ જોઈ રહ્યો છું. કૃપા કરીને તૈયાર થયા પછી જવાબ આપો.",
                    2: "કૃપા કરીને તમારું {field_type} આપો? હું મદદ કરવા અહીં છું.",
                    3: "મને હજી પણ તમારા {field_type} ની જરૂર છે. શું તમને આ પ્રશ્ન સાથે મુશ્કેલી છે?"
                },
                "confirmation": {
                    1: "કૃપા કરીને પુષ્ટિ કરો કે આ માહિતી સાચી છે.",
                    2: "આગળ વધવા માટે મને તમારી પુષ્ટિ જોઈએ. કૃપા કરીને હા અથવા ના કહો.",
                    3: "તમે હજી પણ ત્યાં છો? કૃપા કરીને પુષ્ટિ કરો જેથી આપણે આગળ વધી શકીએ."
                }
            }
        }
        
        # Field type translations for contextual prompts
        self.field_translations = {
            Language.ENGLISH: {
                "name": "name",
                "email": "email address", 
                "phone": "phone number",
                "dob": "date of birth",
                "address": "address"
            },
            Language.GUJARATI: {
                "name": "નામ",
                "email": "ઈમેઈલ સરનામું",
                "phone": "ફોન નંબર", 
                "dob": "જન્મતારીખ",
                "address": "સરનામું"
            }
        }
    
    def start_session(self, session_id: str, language: Language, callback: Optional[Callable] = None):
        """Start intelligent silence monitoring for a session"""
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
            timer_handle=None,
            context={}
        )
        
        self.sessions[session_id] = session
        logger.info(f"Started intelligent silence monitoring for session {session_id} in {language.value}")
    
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
    
    def start_silence_detection(self, session_id: str, callback: Optional[Callable] = None, 
                               question_text: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """Start intelligent silence detection with context awareness"""
        if session_id not in self.sessions:
            logger.warning(f"Session {session_id} not found for silence detection")
            return
        
        session = self.sessions[session_id]
        session.callback = callback
        session.question_text = question_text
        session.context = context or {}
        session.silence_start = time.time()
        session.repetition_count = 0
        session.state = SilenceState.WAITING_FOR_RESPONSE
        
        # Cancel any existing timer
        if session.timer_handle:
            session.timer_handle.cancel()
        
        # Start silence detection timer
        session.timer_handle = threading.Timer(self.silence_timeout, self._handle_silence_timeout, [session_id])
        session.timer_handle.start()
        
        logger.info(f"Started intelligent silence detection for session {session_id} with context: {context}")
    
    def _handle_silence_timeout(self, session_id: str):
        """Handle silence timeout with intelligent context-aware prompts"""
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
        
        # Increment repetition count and generate intelligent prompt
        session.repetition_count += 1
        session.state = SilenceState.REPEATING_QUESTION
        
        # Generate context-aware silence prompt
        prompt_text = self._generate_intelligent_prompt(session)
        
        # Trigger callback with intelligent prompt
        if session.callback:
            try:
                session.callback(session_id, prompt_text, session.language)
            except Exception as e:
                logger.error(f"Silence callback failed for session {session_id}: {e}")
        
        # Schedule next repetition
        session.timer_handle = threading.Timer(self.repetition_interval, self._handle_silence_timeout, [session_id])
        session.timer_handle.start()
        
        logger.info(f"Intelligent silence prompt {session.repetition_count}/{self.max_repetitions} sent for session {session_id}")
    
    def _generate_intelligent_prompt(self, session: SilenceSession) -> str:
        """Generate intelligent, context-aware silence prompt"""
        context = session.context or {}
        prompts = self.context_aware_prompts.get(session.language, self.context_aware_prompts[Language.ENGLISH])
        
        # Determine prompt type based on context
        prompt_type = "initial"
        if context.get("field_name"):
            prompt_type = "form_field"
        elif context.get("awaiting_confirmation"):
            prompt_type = "confirmation"
        
        # Get base prompt
        prompt_templates = prompts.get(prompt_type, prompts["initial"])
        base_prompt = prompt_templates.get(session.repetition_count, prompt_templates[1])
        
        # Add context-specific information
        if prompt_type == "form_field" and context.get("field_name"):
            field_name = context["field_name"].lower()
            field_translations = self.field_translations.get(session.language, self.field_translations[Language.ENGLISH])
            
            # Find appropriate field translation
            field_type = "information"  # default
            for key, translation in field_translations.items():
                if key in field_name:
                    field_type = translation
                    break
            
            base_prompt = base_prompt.format(field_type=field_type)
        
        # For first repetition, include the original question if available
        if session.repetition_count == 1 and session.question_text:
            if session.language == Language.GUJARATI:
                return f"{base_prompt}\n\nમૂળ પ્રશ્ન: {session.question_text}"
            else:
                return f"{base_prompt}\n\nOriginal question: {session.question_text}"
        
        return base_prompt
    
    def _trigger_session_timeout(self, session_id: str):
        """Handle complete session timeout with intelligent messaging"""
        if session_id not in self.sessions:
            return
        
        session = self.sessions[session_id]
        
        # Generate intelligent timeout message based on context
        context = session.context or {}
        if session.language == Language.GUJARATI:
            if context.get("field_name"):
                timeout_msg = f"સમય સમાપ્ત. અમે પછીથી '{context['field_name']}' વિશે પૂછીશું. કૃપા કરીને વાતચીત ફરીથી શરૂ કરો."
            else:
                timeout_msg = "સેશન સમાપ્ત થઈ ગયો છે. કૃપા કરીને વાતચીત ફરીથી શરૂ કરો."
        else:
            if context.get("field_name"):
                timeout_msg = f"Session timeout. We'll ask about '{context['field_name']}' later. Please restart the conversation."
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
        
        logger.info(f"Session {session_id} timed out intelligently after {self.max_repetitions} repetitions")
    
    def update_context(self, session_id: str, context: Dict[str, Any]):
        """Update context for intelligent prompts"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.context.update(context)
            logger.debug(f"Updated context for session {session_id}: {context}")
    
    def set_field_context(self, session_id: str, field_name: str, field_type: str = None):
        """Set field-specific context for better prompts"""
        if session_id in self.sessions:
            context = {
                "field_name": field_name,
                "field_type": field_type or "information",
                "awaiting_field_response": True
            }
            self.update_context(session_id, context)
    
    def set_confirmation_context(self, session_id: str, confirmation_text: str):
        """Set confirmation context for better prompts"""
        if session_id in self.sessions:
            context = {
                "awaiting_confirmation": True,
                "confirmation_text": confirmation_text
            }
            self.update_context(session_id, context)
    
    def update_language(self, session_id: str, language: Language):
        """Update language for a session"""
        if session_id in self.sessions:
            self.sessions[session_id].language = language
            logger.info(f"Updated language to {language.value} for session {session_id}")
    
    def update_current_field(self, session_id: str, field_name: str):
        """Update current field being processed"""
        if session_id in self.sessions:
            self.sessions[session_id].current_field = field_name
            # Also update field context
            self.set_field_context(session_id, field_name)
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
            "max_repetitions": self.max_repetitions,
            "intelligent_features": True
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
        
        logger.info(f"Cleaned up {len(expired_sessions)} expired intelligent silence sessions")
        return len(expired_sessions)

# Global intelligent silence manager instance
silence_manager = IntelligentSilenceManager()