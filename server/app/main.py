import re
import json
import base64
import tempfile
import os
import asyncio
import traceback
import zipfile
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import pyttsx3
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Request, status
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from pydantic import BaseModel, validator, Field
import logging
from datetime import datetime
import threading
from pathlib import Path
import uuid
from .llm import GeminiLLM
from .memory import memory_store, FieldStatus, MessageRole
from .form_builder import FormSchema, FormField, FieldType, FormResponse, form_store, SAMPLE_FORMS
from .dynamic_chat import DynamicFormConversation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('form_agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Form schema with metadata
FORM_FIELDS = [
    {
        "name": "full_name", 
        "type": "string", 
        "required": True,
        "label": "Full Name",
        "description": "Your complete name"
    },
    {
        "name": "email", 
        "type": "email", 
        "required": True,
        "label": "Email Address",
        "description": "Your email for important updates"
    },
    {
        "name": "phone", 
        "type": "string", 
        "required": True,
        "label": "Phone Number",
        "description": "Your contact number"
    },
    {
        "name": "dob", 
        "type": "date", 
        "required": True,
        "label": "Date of Birth",
        "description": "Your birth date (MM/DD/YYYY)"
    },
]

# Global TTS engine with thread safety
_tts_lock = threading.Lock()
_tts_engine = None

def get_tts_engine():
    """Get thread-safe TTS engine instance"""
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = pyttsx3.init()
        _tts_engine.setProperty("rate", 150)
        _tts_engine.setProperty("volume", 0.9)
    return _tts_engine

def tts_to_base64_wav(text: str) -> str:
    """Convert text to speech with robust error handling"""
    if not text or not text.strip():
        return ""
    
    # Sanitize text for TTS
    sanitized_text = re.sub(r'[^\w\s\.,!?\-]', '', text.strip())
    if not sanitized_text:
        sanitized_text = "I had trouble generating audio for that response."
    
    temp_path = None
    try:
        with _tts_lock:
            engine = get_tts_engine()
            
            # Create temp file with proper cleanup
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tf:
                temp_path = tf.name
            
            # Generate speech
            engine.save_to_file(sanitized_text, temp_path)
            engine.runAndWait()
            
            # Read and encode
            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                with open(temp_path, "rb") as f:
                    audio_data = f.read()
                return base64.b64encode(audio_data).decode("utf-8")
            else:
                logger.warning("TTS generated empty file")
                return ""
                
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        return ""  # Return empty string instead of failing
    finally:
        # Clean up temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup TTS temp file: {cleanup_error}")

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    # Startup
    logger.info("🚀 Form Agent starting up...")
    
    # Initialize LLM
    try:
        app.state.llm = GeminiLLM()
        logger.info("✅ LLM initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize LLM: {e}")
        raise
    
    # Test TTS
    try:
        test_audio = tts_to_base64_wav("System ready")
        if test_audio:
            logger.info("✅ TTS system initialized successfully")
        else:
            logger.warning("⚠️ TTS system may have issues")
    except Exception as e:
        logger.warning(f"⚠️ TTS initialization warning: {e}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Form Agent shutting down...")
    # Cleanup if needed
    logger.info("✅ Shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="Conversational Form Agent (Enhanced)",
    description="Production-ready AI-powered form filling with voice interaction",
    version="2.0.0",
    lifespan=lifespan
)

# Enhanced CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "https://*.netlify.app",
        "https://*.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Pydantic models with validation
class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=100)
    message: str = Field("", max_length=1000)
    
    @validator('session_id')
    def validate_session_id(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]+', v):
            raise ValueError('Session ID must contain only alphanumeric characters, hyphens, and underscores')
        return v

class ChatResponse(BaseModel):
    action: str
    reply: str
    ask: Optional[str] = None
    updates: Optional[Dict[str, Any]] = None
    audio_b64: Optional[str] = None
    session_status: Optional[Dict[str, Any]] = None
    field_focus: Optional[str] = None
    tone: Optional[str] = None

class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)

class TTSResponse(BaseModel):
    audio: str
    success: bool = True

class SubmitRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    dob: Optional[str] = None

class SessionInfoResponse(BaseModel):
    session_id: str
    created_at: float
    last_activity: float
    completed: bool
    field_summary: Dict[str, Any]
    message_count: int
    context: Dict[str, Any]

# Form Builder Models
class CreateFormRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    fields: List[Dict[str, Any]]
    confirmation_message: str = "Thank you for your response!"

class UpdateFormRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    fields: Optional[List[Dict[str, Any]]] = None
    confirmation_message: Optional[str] = None
    is_active: Optional[bool] = None

class DynamicChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=100)
    form_id: str = Field(..., min_length=1)
    message: str = Field("", max_length=1000)

class DynamicChatResponse(BaseModel):
    action: str
    reply: str
    ask: Optional[str] = None
    updates: Optional[Dict[str, Any]] = None
    audio_b64: Optional[str] = None
    form_summary: Optional[Dict[str, Any]] = None
    completion_status: Optional[Dict[str, Any]] = None
    field_focus: Optional[str] = None
    tone: Optional[str] = None

# # Normalize user speech input
# def normalize_user_text(text: str) -> str:
#     """Enhanced text normalization for speech-to-text input"""
#     if not text:
#         return ""
    
#     s = text.strip()
    
#     # Email-specific corrections
#     s = re.sub(r'\bat\s+the\s+rate\b', '@', s, flags=re.IGNORECASE)
#     s = re.sub(r'\bat\b', '@', s, flags=re.IGNORECASE)
#     s = re.sub(r'\bdot\s+com\b', '.com', s, flags=re.IGNORECASE)
#     s = re.sub(r'\bdot\b', '.', s, flags=re.IGNORECASE)
#     s = re.sub(r'\bgmail\s+com\b', 'gmail.com', s, flags=re.IGNORECASE)
    
#     # Phone number corrections
#     s = re.sub(r'\b(\d)\s+(\d)\s+(\d)\b', r'\1\2\3', s)  # "1 2 3" -> "123"
    
#     # Date corrections
#     s = re.sub(r'\b(\d{1,2})\s+(\d{1,2})\s+(\d{4})\b', r'\1/\2/\3', s)
    
#     # Collapse spelled out letters
#     def collapse_spelled(match):
#         letters = re.findall(r'\b[A-Za-z]\b', match.group(0))
#         return ''.join(letters) if len(letters) <= 10 else match.group(0)
    
#     s = re.sub(r'(?:\b[A-Za-z]\b\s*){3,}', collapse_spelled, s)
    
#     # Clean up whitespace
#     s = re.sub(r'\s+', ' ', s).strip()
    
#     return s

# Enhanced normalization - add this RIGHT BEFORE the llm.infer call
def enhanced_normalize_speech(text: str) -> str:
    """Enhanced speech-to-text normalization"""
    if not text:
        return ""
    
    s = text.strip()
    
    # SUPER AGGRESSIVE email corrections for "at the rate" issue
    s = re.sub(r'\bat\s*the\s*rate\b', '@', s, flags=re.IGNORECASE)
    s = re.sub(r'\bat\s*rate\b', '@', s, flags=re.IGNORECASE)
    s = re.sub(r'\bthe\s*rate\b', '@', s, flags=re.IGNORECASE)  # Sometimes "at" gets dropped
    s = re.sub(r'\brate\s*([a-zA-Z])', r'@\1', s, flags=re.IGNORECASE)  # "rate gmail" -> "@gmail"
    
    # Handle cases where @ gets converted to "at" 
    s = re.sub(r'(\w+)\s*at\s*([a-zA-Z]+\.com)', r'\1@\2', s, flags=re.IGNORECASE)
    s = re.sub(r'(\w+)\s*(\d+)\s*at\s*([a-zA-Z]+\.com)', r'\1\2@\3', s, flags=re.IGNORECASE)
    s = re.sub(r'(\w+)\s*(\d+)\s*at\s*the\s*rate\s*([a-zA-Z]+\.com)', r'\1\2@\3', s, flags=re.IGNORECASE)
    
    # Enhanced dot handling
    s = re.sub(r'\bdot\s*com\b', '.com', s, flags=re.IGNORECASE)
    s = re.sub(r'\bdot\s*gmail\s*com\b', '.gmail.com', s, flags=re.IGNORECASE)
    s = re.sub(r'\bgmail\s*dot\s*com\b', 'gmail.com', s, flags=re.IGNORECASE)
    
    # Fix specific patterns from the user's example: "Om Patel 2212 at the rate gmail.com"
    s = re.sub(r'(\w+\s+\w+)\s+(\d+)\s+at\s+the\s+rate\s+([a-zA-Z]+\.com)', r'\1\2@\3', s, flags=re.IGNORECASE)
    s = re.sub(r'(\w+)\s+(\d+)\s+at\s+the\s+rate\s+([a-zA-Z]+\.com)', r'\1\2@\3', s, flags=re.IGNORECASE)
    
    # Handle dots more broadly
    s = re.sub(r'\bdot\b', '.', s, flags=re.IGNORECASE)
    
    # Clean up whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    
    return s

# Exception handlers
@app.exception_handler(ValueError)
async def validation_exception_handler(request: Request, exc: ValueError):
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc), "type": "validation_error"}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred",
            "type": "server_error",
            "timestamp": datetime.now().isoformat()
        }
    )

# Health check endpoints
@app.get("/health")
def health():
    """Basic health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    }

@app.get("/health/detailed")
def detailed_health():
    """Detailed health check with system status"""
    try:
        # Test LLM
        llm_status = "healthy"
        try:
            if hasattr(app.state, 'llm'):
                test_response = app.state.llm.infer_freeform("test")
                if not test_response:
                    llm_status = "degraded"
        except Exception:
            llm_status = "unhealthy"
        
        # Test TTS
        tts_status = "healthy"
        try:
            test_audio = tts_to_base64_wav("test")
            if not test_audio:
                tts_status = "degraded"
        except Exception:
            tts_status = "unhealthy"
        
        # Memory stats
        memory_stats = memory_store.get_session_stats()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "llm": llm_status,
                "tts": tts_status,
                "memory": "healthy"
            },
            "memory_stats": memory_stats
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
        )

# Session management
@app.post("/reset")
def reset_session(session_id: str = Query("session1", min_length=1)):
    """Reset a session to initial state"""
    try:
        # Delete existing session
        memory_store.delete_session(session_id)
        
        # Create new session
        session = memory_store.get_or_create_session(session_id)
        session.add_message(
            MessageRole.SYSTEM, 
            "Session reset - ready to collect form information"
        )
        
        logger.info(f"Session {session_id} reset successfully")
        
        return {
            "status": "reset",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to reset session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset session"
        )

@app.get("/session/{session_id}/info", response_model=SessionInfoResponse)
def get_session_info(session_id: str):
    """Get detailed session information"""
    try:
        session = memory_store.get_or_create_session(session_id)
        
        return SessionInfoResponse(
            session_id=session.session_id,
            created_at=session.created_at,
            last_activity=session.last_activity,
            completed=session.completed,
            field_summary=session.get_field_summary(),
            message_count=len(session.messages),
            context=session.context.copy()
        )
        
    except Exception as e:
        logger.error(f"Failed to get session info for {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session information"
        )

# Main chat endpoint
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Enhanced chat endpoint with full context awareness"""
    session_id = req.session_id
    
    try:
        # Get or create session
        session = memory_store.get_or_create_session(session_id)
        
        # Normalize user input
        raw_message = req.message.strip()
        normalized_message = enhanced_normalize_speech(raw_message)
        
        # Add user message to session
        session.add_message(MessageRole.USER, normalized_message)
        
        # Determine current field if not set
        if not session.current_field:
            field_summary = session.get_field_summary()
            for field in FORM_FIELDS:
                field_name = field["name"]
                if field_name not in field_summary or field_summary[field_name]["status"] in ["pending", "invalid"]:
                    session.current_field = field_name
                    break
        
        # Get LLM response
        llm_response = app.state.llm.infer(FORM_FIELDS, session, normalized_message)
        
        # Process LLM response
        action = llm_response.get("action", "ask")
        updates = llm_response.get("updates", {})
        ask_text = llm_response.get("ask", "")
        field_focus = llm_response.get("field_focus")
        tone = llm_response.get("tone", "professional")

        # *** ADD THIS ENHANCED UPDATE LOGIC ***
        # Apply field updates with better tracking
        for field_name, value in updates.items():
            if value and value.strip():
                session.update_field(field_name, value, FieldStatus.COLLECTED)
                logger.info(f"Updated field {field_name} = {value}")

        # ENHANCED DOB PROCESSING - Parse natural date formats
        # Check for DOB in recent conversation context
        recent_user_messages = [msg['content'] for msg in session.get_conversation_context(5) if msg.get('role') == 'user']
        combined_text = ' '.join(recent_user_messages).lower()
        
        # Look for DOB patterns in conversation
        if ('dob' in updates or 'date' in combined_text or 'birth' in combined_text or 
            any(month in combined_text for month in ['january', 'february', 'march', 'april', 'may', 'june', 
                                                   'july', 'august', 'september', 'october', 'november', 'december',
                                                   'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'])):
            
            import calendar
            month_names = {month.lower(): idx for idx, month in enumerate(calendar.month_name[1:], 1)}
            month_abbrev = {month.lower(): idx for idx, month in enumerate(calendar.month_abbr[1:], 1)}
            all_months = {**month_names, **month_abbrev}
            
            # Enhanced DOB extraction patterns
            dob_patterns = [
                # "22nd December 2004" or "December 22nd 2004"  
                r'(\d{1,2})(st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*(\d{4})',
                r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2})(st|nd|rd|th)?\s*(\d{4})',
                # "12/22/2004" or "22/12/2004"
                r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',
                # "December 22, 2004"
                r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2}),?\s*(\d{4})'
            ]
            
            dob_found = False
            for pattern in dob_patterns:
                match = re.search(pattern, combined_text, re.IGNORECASE)
                if match and not dob_found:
                    try:
                        groups = match.groups()
                        day, month, year = None, None, None
                        
                        # Pattern 1: "22nd December 2004"
                        if groups[0].isdigit() and groups[2] in all_months:
                            day = int(groups[0])
                            month = all_months[groups[2]]
                            year = int(groups[3])
                        
                        # Pattern 2: "December 22nd 2004"
                        elif groups[0] in all_months and groups[1].isdigit():
                            month = all_months[groups[0]]
                            day = int(groups[1])
                            year = int(groups[3])
                        
                        # Pattern 3: "12/22/2004" - assume MM/DD/YYYY for US format
                        elif len(groups) == 3 and all(g.isdigit() for g in groups):
                            month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                        
                        # Pattern 4: "December 22, 2004"
                        elif groups[0] in all_months and groups[1].isdigit():
                            month = all_months[groups[0]]
                            day = int(groups[1])
                            year = int(groups[2])
                        
                        # Validate and format the date
                        if month and day and year and 1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2025:
                            formatted_dob = f"{year}-{month:02d}-{day:02d}"  # ISO format for backend
                            session.update_field('dob', formatted_dob, FieldStatus.COLLECTED)
                            updates['dob'] = formatted_dob
                            logger.info(f"Auto-extracted DOB: {formatted_dob} from: {combined_text}")
                            dob_found = True
                            break
                            
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Failed to parse DOB pattern: {e}")
                        continue
            
        # AUTO-DETECT missing updates from conversation context
        # Check if user provided data that wasn't captured
        recent_messages = session.get_conversation_context(3)
        if len(recent_messages) >= 2:
            last_user_msg = next((msg for msg in reversed(recent_messages) if msg['role'] == 'user'), None)
            if last_user_msg:
                user_text = last_user_msg['content'].lower()
                
                # Auto-detect DOB patterns that might have been missed
                dob_patterns = [
                    r'(\d{1,2})\s*(st|nd|rd|th)?\s*(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*(\d{4})',
                    r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',
                    r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}),?\s*(\d{4})'
                ]
                
                for pattern in dob_patterns:
                    match = re.search(pattern, user_text, re.IGNORECASE)
                    if match and 'dob' not in updates:
                        # Extract and format date
                        if '/' in user_text or '-' in user_text:
                            dob_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', user_text)
                            if dob_match:
                                month, day, year = dob_match.groups()
                                formatted_dob = f"{int(month):02d}/{int(day):02d}/{year}"
                                session.update_field('dob', formatted_dob, FieldStatus.COLLECTED)
                                updates['dob'] = formatted_dob
                                logger.info(f"Auto-detected DOB: {formatted_dob}")
                        break
        
        # Apply field updates
        for field_name, value in updates.items():
            session.update_field(field_name, value, FieldStatus.COLLECTED)
        
        # Update current field
        if field_focus:
            session.current_field = field_focus
        
        # Handle different actions
        reply_text = ask_text
        if not reply_text:
            default_replies = {
                "ask": "Could you help me with that information?",
                "set": "Got it, thanks!",
                "done": "Perfect! I have all the information I need.",
                "clarify": "Let me clarify that for you.",
                "skip": "No problem, let's move on.",
                "error": "I didn't quite catch that. Could you try again?"
            }
            reply_text = default_replies.get(action, "How can I help you?")
        
        # Update session context based on interaction
        if action == "error":
            session.context["consecutive_errors"] = session.context.get("consecutive_errors", 0) + 1
            if session.context["consecutive_errors"] >= 3:
                session.increment_frustration()
        else:
            session.context["consecutive_errors"] = 0
            if action in ["set", "done"]:
                session.reset_frustration()
        
        # Generate audio
        audio_b64 = ""
        if reply_text:
            try:
                audio_b64 = tts_to_base64_wav(reply_text)
            except Exception as e:
                logger.warning(f"TTS generation failed: {e}")
                # Continue without audio rather than failing
        
        # Add agent response to session
        session.add_message(MessageRole.AGENT, reply_text)
        
        # Check if form is complete
        if action == "done":
            session.completed = True
            session.context["conversation_phase"] = "completed"
        
        # Build response
        response = ChatResponse(
            action=action,
            reply=reply_text,
            ask=ask_text if ask_text else None,
            updates=session.get_field_summary(),
            audio_b64=audio_b64,
            session_status={
                "completed": session.completed,
                "current_field": session.current_field,
                "frustration_level": session.context.get("user_frustration_level", 0)
            },
            field_focus=field_focus,
            tone=tone
        )
        
        logger.info(f"Chat processed for session {session_id}: action={action}")
        return response
        
    except Exception as e:
        logger.error(f"Chat processing failed for session {session_id}: {e}\n{traceback.format_exc()}")
        
        # Return graceful error response
        error_reply = "I'm having a technical issue. Could you please try again?"
        error_audio = ""
        try:
            error_audio = tts_to_base64_wav(error_reply)
        except Exception:
            pass
        
        return ChatResponse(
            action="error",
            reply=error_reply,
            audio_b64=error_audio,
            session_status={"completed": False, "current_field": None, "frustration_level": 0}
        )

# Standalone TTS endpoint
@app.post("/tts", response_model=TTSResponse)
async def text_to_speech(req: TTSRequest):
    """Convert text to speech"""
    try:
        audio_b64 = tts_to_base64_wav(req.text)
        return TTSResponse(audio=audio_b64, success=bool(audio_b64))
        
    except Exception as e:
        logger.error(f"TTS conversion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Text-to-speech conversion failed"
        )

# Form submission endpoint
@app.post("/submit")
async def submit_form(req: SubmitRequest, background_tasks: BackgroundTasks):
    """Submit completed form data"""
    try:
        session = memory_store.get_or_create_session(req.session_id)
        
        # Get current field values from session
        field_summary = session.get_field_summary()
        
        # Build submission data
        submission_data = {
            "session_id": req.session_id,
            "submitted_at": datetime.now().isoformat(),
            "fields": {}
        }
        
        # Include all collected fields
        for field in FORM_FIELDS:
            field_name = field["name"]
            if field_name in field_summary and field_summary[field_name]["value"]:
                submission_data["fields"][field_name] = field_summary[field_name]["value"]
        
        # Override with any explicitly provided values
        for field_name in ["full_name", "email", "phone", "dob"]:
            value = getattr(req, field_name, None)
            if value:
                submission_data["fields"][field_name] = value
        
        # Mark session as completed
        session.completed = True
        session.context["conversation_phase"] = "completed"
        
        # Log submission (in production, save to database)
        logger.info(f"Form submitted for session {req.session_id}: {json.dumps(submission_data, indent=2)}")
        
        # Background task for additional processing
        def process_submission(data):
            # Here you could:
            # - Save to database
            # - Send confirmation email
            # - Trigger webhooks
            # - Analytics tracking
            logger.info(f"Background processing for submission: {data['session_id']}")
        
        background_tasks.add_task(process_submission, submission_data)
        
        return {
            "status": "success",
            "message": "Form submitted successfully",
            "submission_id": f"sub_{req.session_id}_{int(datetime.now().timestamp())}",
            "data": submission_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Form submission failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Form submission failed"
        )

# Admin endpoints
@app.get("/admin/sessions")
def list_sessions(limit: int = Query(50, ge=1, le=100)):
    """List all active sessions (admin only)"""
    try:
        sessions_info = []
        for session_id, session in list(memory_store.sessions.items())[:limit]:
            sessions_info.append({
                "session_id": session_id,
                "created_at": session.created_at,
                "last_activity": session.last_activity,
                "completed": session.completed,
                "message_count": len(session.messages),
                "fields_collected": len([f for f in session.fields.values() if f.status == FieldStatus.COLLECTED])
            })
        
        return {
            "sessions": sessions_info,
            "total_count": len(memory_store.sessions),
            "stats": memory_store.get_session_stats()
        }
        
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sessions"
        )

@app.delete("/admin/sessions/cleanup")
def cleanup_expired_sessions():
    """Clean up expired sessions"""
    try:
        cleaned_count = memory_store.cleanup_expired_sessions()
        return {
            "status": "success",
            "cleaned_sessions": cleaned_count,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Session cleanup failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session cleanup failed"
        )

# Export session data
@app.get("/admin/sessions/{session_id}/export")
def export_session(session_id: str):
    """Export complete session data"""
    try:
        session_data = memory_store.export_session(session_id)
        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        return {
            "status": "success",
            "session_data": session_data,
            "exported_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session export failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session export failed"
        )

# ========================================
# FORM BUILDER ENDPOINTS
# ========================================

@app.get("/forms")
def list_forms():
    """List all available forms"""
    try:
        forms = form_store.list_forms()
        return {
            "status": "success",
            "forms": [
                {
                    "id": form.id,
                    "title": form.title,
                    "description": form.description,
                    "field_count": len(form.fields),
                    "is_active": form.is_active,
                    "created_at": form.created_at,
                    "updated_at": form.updated_at
                }
                for form in forms
            ],
            "count": len(forms)
        }
    except Exception as e:
        logger.error(f"Error listing forms: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list forms"
        )

@app.post("/forms")
def create_form(req: CreateFormRequest):
    """Create a new dynamic form"""
    try:
        # Validate field types
        valid_types = [t.value for t in FieldType]
        for field_data in req.fields:
            if field_data.get("type") not in valid_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid field type: {field_data.get('type')}. Valid types: {valid_types}"
                )
        
        form_data = req.dict()
        form = form_store.create_form(form_data)
        
        logger.info(f"Created new form: {form.id} - {form.title}")
        
        return {
            "status": "success",
            "message": "Form created successfully",
            "form": {
                "id": form.id,
                "title": form.title,
                "description": form.description,
                "fields": [
                    {
                        "id": field.id,
                        "name": field.name,
                        "type": field.type.value,
                        "label": field.label,
                        "required": field.validation.required,
                        "order": field.order
                    }
                    for field in form.fields
                ]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating form: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create form"
        )

@app.get("/forms/{form_id}")
def get_form(form_id: str):
    """Get form by ID"""
    try:
        form = form_store.get_form(form_id)
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Form not found"
            )
        
        return {
            "status": "success",
            "form": form.dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting form {form_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve form"
        )

@app.put("/forms/{form_id}")
def update_form(form_id: str, req: UpdateFormRequest):
    """Update existing form"""
    try:
        form = form_store.get_form(form_id)
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Form not found"
            )
        
        # Prepare update data
        update_data = form.dict()
        
        if req.title is not None:
            update_data["title"] = req.title
        if req.description is not None:
            update_data["description"] = req.description
        if req.fields is not None:
            update_data["fields"] = req.fields
        if req.confirmation_message is not None:
            update_data["confirmation_message"] = req.confirmation_message
        if req.is_active is not None:
            update_data["is_active"] = req.is_active
        
        updated_form = form_store.update_form(form_id, update_data)
        
        logger.info(f"Updated form: {form_id}")
        
        return {
            "status": "success",
            "message": "Form updated successfully",
            "form": updated_form.dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating form {form_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update form"
        )

@app.delete("/forms/{form_id}")
def delete_form(form_id: str):
    """Delete form and all responses"""
    try:
        success = form_store.delete_form(form_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Form not found"
            )
        
        logger.info(f"Deleted form: {form_id}")
        
        return {
            "status": "success",
            "message": "Form deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting form {form_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete form"
        )

# Dynamic Chat for Forms
@app.post("/dynamic-chat", response_model=DynamicChatResponse)
async def dynamic_chat(req: DynamicChatRequest):
    """Enhanced chat endpoint for dynamic forms"""
    try:
        # Get or create session
        session = memory_store.get_or_create_session(req.session_id)
        
        # Add user message to session
        session.add_message(MessageRole.USER, req.message)
        
        # Create dynamic form conversation handler
        form_conversation = DynamicFormConversation(req.form_id, session)
        
        # Process user input
        llm_response = form_conversation.process_user_input(req.message)
        
        # Generate audio response
        audio_b64 = ""
        reply_text = llm_response.get("ask", llm_response.get("reply", ""))
        if reply_text:
            try:
                audio_b64 = tts_to_base64_wav(reply_text)
            except Exception as e:
                logger.warning(f"TTS generation failed: {e}")
        
        # Add agent response to session
        session.add_message(MessageRole.AGENT, reply_text)
        
        # Get form summary
        form_summary = form_conversation.get_form_summary()
        
        response = DynamicChatResponse(
            action=llm_response.get("action", "ask"),
            reply=reply_text,
            ask=llm_response.get("ask"),
            updates=llm_response.get("updates", {}),
            audio_b64=audio_b64,
            form_summary=form_summary,
            completion_status=llm_response.get("completion_status"),
            field_focus=llm_response.get("field_focus"),
            tone=llm_response.get("tone", "friendly")
        )
        
        logger.info(f"Dynamic chat processed for session {req.session_id}, form {req.form_id}")
        return response
        
    except Exception as e:
        logger.error(f"Dynamic chat processing failed: {e}\n{traceback.format_exc()}")
        
        return DynamicChatResponse(
            action="error",
            reply="I'm having a technical issue. Could you please try again?",
            audio_b64="",
            form_summary=None
        )

# Form Response Endpoints
@app.post("/forms/{form_id}/submit")
async def submit_form_response(form_id: str, response_data: Dict[str, Any]):
    """Submit a response to a form"""
    try:
        form = form_store.get_form(form_id)
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Form not found"
            )
        
        # Create response
        submission = {
            "form_id": form_id,
            "session_id": response_data.get("session_id", str(uuid.uuid4())),
            "responses": response_data.get("responses", {}),
            "user_email": response_data.get("user_email")
        }
        
        response = form_store.submit_response(submission)
        
        logger.info(f"Form response submitted: {response.id} for form {form_id}")
        
        return {
            "status": "success",
            "message": form.confirmation_message,
            "response_id": response.id,
            "submitted_at": response.submitted_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting form response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit form response"
        )

@app.get("/forms/{form_id}/responses")
def get_form_responses(form_id: str):
    """Get all responses for a form"""
    try:
        form = form_store.get_form(form_id)
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Form not found"
            )
        
        responses = form_store.get_responses(form_id)
        
        return {
            "status": "success",
            "form_title": form.title,
            "response_count": len(responses),
            "responses": [
                {
                    "id": resp.id,
                    "session_id": resp.session_id,
                    "responses": resp.responses,
                    "submitted_at": resp.submitted_at,
                    "user_email": resp.user_email
                }
                for resp in responses
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting form responses: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve form responses"
        )

# Sample Forms and Templates
@app.get("/forms/templates/list")
def list_form_templates():
    """List available form templates"""
    try:
        return {
            "status": "success",
            "templates": [
                {
                    "id": template_id,
                    "title": template_data["title"],
                    "description": template_data["description"],
                    "field_count": len(template_data["fields"])
                }
                for template_id, template_data in SAMPLE_FORMS.items()
            ]
        }
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list templates"
        )

@app.post("/forms/templates/{template_id}")
def create_form_from_template(template_id: str, title_override: Optional[str] = None):
    """Create a new form from a template"""
    try:
        if template_id not in SAMPLE_FORMS:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        template_data = SAMPLE_FORMS[template_id].copy()
        
        if title_override:
            template_data["title"] = title_override
        
        form = form_store.create_form(template_data)
        
        logger.info(f"Created form from template {template_id}: {form.id}")
        
        return {
            "status": "success",
            "message": "Form created from template successfully",
            "form": form.dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating form from template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create form from template"
        )

# ========================================
# CODE EXPORT FUNCTIONALITY  
# ========================================

@app.get("/export/project")
async def export_project():
    """Export entire project as ZIP file"""
    try:
        # Create temporary zip file
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, "form-with-ai-project.zip")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add all project files
            project_root = Path("/app")
            
            for root, dirs, files in os.walk(project_root):
                # Skip certain directories
                dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.emergent', 'node_modules', '.venv']]
                
                for file in files:
                    # Skip certain file types
                    if file.endswith(('.pyc', '.log', '.tmp')):
                        continue
                    
                    file_path = Path(root) / file
                    arc_path = file_path.relative_to(project_root)
                    
                    try:
                        zipf.write(file_path, arc_path)
                    except Exception as e:
                        logger.warning(f"Skipped file {file_path}: {e}")
        
        # Read zip file
        with open(zip_path, 'rb') as f:
            zip_data = f.read()
        
        # Cleanup
        os.remove(zip_path)
        os.rmdir(temp_dir)
        
        # Return as streaming response
        def generate():
            yield zip_data
        
        return StreamingResponse(
            generate(),
            media_type="application/zip",
            headers={
                "Content-Disposition": "attachment; filename=form-with-ai-project.zip",
                "Content-Length": str(len(zip_data))
            }
        )
        
    except Exception as e:
        logger.error(f"Project export failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export project"
        )

@app.get("/export/setup-guide")
def get_setup_guide():
    """Get setup instructions for local development"""
    try:
        guide = {
            "title": "Local Development Setup Guide",
            "steps": [
                {
                    "step": 1,
                    "title": "Download Project",
                    "description": "Download the project ZIP from /export/project endpoint"
                },
                {
                    "step": 2,
                    "title": "Extract Files",
                    "description": "Extract the ZIP file to your desired directory"
                },
                {
                    "step": 3,
                    "title": "Backend Setup",
                    "commands": [
                        "cd server",
                        "python -m venv venv",
                        "source venv/bin/activate  # On Windows: venv\\Scripts\\activate",
                        "pip install -r requirements.txt"
                    ]
                },
                {
                    "step": 4,
                    "title": "Frontend Setup", 
                    "commands": [
                        "cd Form-with-AI-Frontend",
                        "npm install"
                    ]
                },
                {
                    "step": 5,
                    "title": "Environment Variables",
                    "description": "Update .env files with your API keys",
                    "files": [
                        "server/.env - Add your GEMINI_API_KEY",
                        "Form-with-AI-Frontend/.env - Update REACT_APP_BACKEND_URL if needed"
                    ]
                },
                {
                    "step": 6,
                    "title": "Run Backend",
                    "commands": [
                        "cd server",
                        "python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
                    ]
                },
                {
                    "step": 7,
                    "title": "Run Frontend",
                    "commands": [
                        "cd Form-with-AI-Frontend",
                        "npm run dev"
                    ]
                },
                {
                    "step": 8,
                    "title": "Access Application",
                    "description": "Open browser and go to:",
                    "urls": [
                        "Frontend: http://localhost:5173",
                        "Backend API: http://localhost:8000",
                        "API Docs: http://localhost:8000/docs"
                    ]
                }
            ],
            "requirements": {
                "python": "3.8+",
                "node": "16+",
                "npm": "8+"
            },
            "api_keys_needed": [
                "GEMINI_API_KEY - Get from Google AI Studio"
            ]
        }
        
        return {
            "status": "success",
            "setup_guide": guide
        }
        
    except Exception as e:
        logger.error(f"Error generating setup guide: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate setup guide"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )