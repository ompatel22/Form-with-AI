import re
import json
import base64
import tempfile
import os
import asyncio
import traceback
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
from .stt import transcribe_b64, warm_up_models
from .memory import memory_store, FieldStatus, MessageRole
from .form_builder import FormSchema, FormField, FieldType, FormResponse, form_store, SAMPLE_FORMS
from .enhanced_dynamic_chat import EnhancedDynamicFormConversation
from .language_support import Language, language_support
from .silence_manager import silence_manager
from .voice_interruption import voice_interruption_handler
from .google_tts import unified_tts_service

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

async def tts_to_base64_wav(text: str, language: Language = Language.ENGLISH) -> str:
    """Convert text to speech using Google TTS with enhanced multilingual support"""
    if not text or not text.strip():
        return ""
    
    try:
        # Sanitize text for TTS
        sanitized_text = re.sub(r'[^\w\s\.,!?\-\u0A80-\u0AFF]', '', text.strip())  # Include Gujarati unicode range
        if not sanitized_text:
            if language == Language.GUJARATI:
                sanitized_text = "માફ કરશો, આ જવાબ માટે ઓડિયો બનાવવામાં મુશ્કેલી થઈ."
            else:
                sanitized_text = "I had trouble generating audio for that response."
        
        # Use unified TTS service with Google Cloud TTS and fallback
        audio_content = await unified_tts_service.synthesize_speech(
            text=sanitized_text,
            language=language,
            gender="NEUTRAL"
        )
        
        if audio_content:
            return unified_tts_service.to_base64_wav(audio_content)
        else:
            logger.warning(f"TTS generated empty audio for {language.value}")
            return ""
            
    except Exception as e:
        logger.error(f"Enhanced TTS generation failed for {language.value}: {e}")
        return ""

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    # Startup
    logger.info("🚀 Enhanced Form Agent starting up...")
    
    # Initialize LLM
    try:
        app.state.llm = GeminiLLM()
        logger.info("✅ LLM initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize LLM: {e}")
        raise
    
    # Test TTS with enhanced multilingual support
    try:
        test_audio = await tts_to_base64_wav("System ready", Language.ENGLISH)
        if test_audio:
            logger.info("✅ Enhanced TTS system initialized successfully")
        else:
            logger.warning("⚠️ Enhanced TTS system may have issues")
    except Exception as e:
        logger.warning(f"⚠️ Enhanced TTS initialization warning: {e}")
    
    # Initialize STT models
    try:
        warm_up_models()
        logger.info("✅ STT models warmed up successfully")
    except Exception as e:
        logger.warning(f"⚠️ STT model warm-up warning: {e}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Enhanced Form Agent shutting down...")
    logger.info("✅ Shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="Enhanced AI-Powered Form Builder",
    description="Professional conversational form filling with voice interaction and dynamic form building",
    version="3.0.0",
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

# Pydantic models
class DynamicChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=100)
    form_id: str = Field(..., min_length=1)
    message: str = Field("", max_length=1000)
    manual_form_data: Optional[Dict[str, Any]] = None  # For detecting manual field entries
    language: Optional[str] = "en"  # Language preference
    interruption_detected: Optional[bool] = False  # Voice interruption flag

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
    language: Optional[str] = "en"  # Response language
    greeting: Optional[str] = None  # Initial greeting if applicable
    interruption_handled: Optional[bool] = False  # Whether interruption was processed

class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)

class TTSResponse(BaseModel):
    audio: str
    success: bool = True

class SessionInfoResponse(BaseModel):
    session_id: str
    created_at: float
    last_activity: float
    completed: bool
    field_summary: Dict[str, Any]
    message_count: int
    context: Dict[str, Any]

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

class FormSubmissionRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    responses: Dict[str, Any]

# Enhanced normalization for speech-to-text input
def enhanced_normalize_speech(text: str) -> str:
    """Enhanced speech-to-text normalization with improved patterns"""
    if not text:
        return ""
    
    s = text.strip()
    
    # SUPER AGGRESSIVE email corrections for "at the rate" issue
    s = re.sub(r'\bat\s*the\s*rate\b', '@', s, flags=re.IGNORECASE)
    s = re.sub(r'\bat\s*rate\b', '@', s, flags=re.IGNORECASE)
    s = re.sub(r'\bthe\s*rate\b', '@', s, flags=re.IGNORECASE)
    s = re.sub(r'\brate\s*([a-zA-Z])', r'@\1', s, flags=re.IGNORECASE)
    
    # Handle cases where @ gets converted to "at" 
    s = re.sub(r'(\w+)\s*at\s*([a-zA-Z]+\.com)', r'\1@\2', s, flags=re.IGNORECASE)
    s = re.sub(r'(\w+)\s*(\d+)\s*at\s*([a-zA-Z]+\.com)', r'\1\2@\3', s, flags=re.IGNORECASE)
    
    # Enhanced dot handling
    s = re.sub(r'\bdot\s*com\b', '.com', s, flags=re.IGNORECASE)
    s = re.sub(r'\bdot\s*gmail\s*com\b', '.gmail.com', s, flags=re.IGNORECASE)
    s = re.sub(r'\bgmail\s*dot\s*com\b', 'gmail.com', s, flags=re.IGNORECASE)
    s = re.sub(r'\bdot\b', '.', s, flags=re.IGNORECASE)
    
    # ENHANCED PHONE NUMBER PARSING - Handle "X times Y" patterns
    def expand_phone_repeats(text):
        # Pattern: "3 times 5 4 times 3 2 times 1" -> "555333311"
        pattern = r'(\d+)\s*times?\s*(\d+)'
        def replace_repeat(match):
            digit = match.group(1)
            count = int(match.group(2))
            return digit * count
        return re.sub(pattern, replace_repeat, text)
    
    s = expand_phone_repeats(s)
    
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
        "version": "3.0.0"
    }

@app.get("/health/detailed")
async def detailed_health():
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
        
        # Test TTS with enhanced system
        tts_status = "healthy"
        try:
            test_audio = await tts_to_base64_wav("test", Language.ENGLISH)
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
            "Session reset - ready for dynamic form interaction"
        )
        # Clear form-specific context
        session.context = {k: v for k, v in session.context.items() if not k.startswith("form_")}
        
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

# STT endpoint for language-specific transcription
class TranscribeRequest(BaseModel):
    audio_b64: str = Field(..., description="Base64 encoded audio data")
    language: str = Field("en", description="Language code (en/gu)")

@app.post("/transcribe")
async def transcribe_audio(req: TranscribeRequest):
    """Transcribe audio with language-specific STT model"""
    try:
        lang = Language.GUJARATI if req.language == "gu" else Language.ENGLISH
        
        # Use language-specific STT model
        transcription = transcribe_b64(req.audio_b64, lang)
        
        if not transcription:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to transcribe audio"
            )
        
        return {
            "status": "success",
            "transcription": transcription,
            "language": req.language,
            "model_used": "vasista22/whisper-gujarati-medium" if lang == Language.GUJARATI else "whisper-english"
        }
        
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transcription service error"
        )

# Main dynamic chat endpoint
@app.post("/dynamic-chat", response_model=DynamicChatResponse)
async def dynamic_chat(req: DynamicChatRequest):
    """Enhanced dynamic chat endpoint with multilingual and voice interruption support"""
    session_id = req.session_id
    form_id = req.form_id
    
    try:
        # Get or create session
        session = memory_store.get_or_create_session(session_id)
        
        # Log session and form details for debugging
        logger.info(f"Dynamic chat request: session={session_id}, form={form_id}, message='{req.message}', language={req.language}")
        form = form_store.get_form(form_id)
        if not form:
            logger.error(f"Form {form_id} not found")
            raise HTTPException(status_code=404, detail="Form not found")
        
        # Create enhanced form-specific conversation handler
        conversation = EnhancedDynamicFormConversation(form_id, session)
        
        # Set language preference
        language = Language.GUJARATI if req.language == "gu" else Language.ENGLISH
        conversation.set_language(language)
        # The conversation object is the source of truth for the language, loaded from the session.
        language = conversation.current_language
        
        # Handle voice interruption if detected
        if req.interruption_detected and req.message:
            if voice_interruption_handler.should_stop_audio(req.message, language):
                stop_msg = language_support.get_ui_text("skip_audio", language)
                return DynamicChatResponse(
                    action="interrupt_stop",
                    reply=stop_msg,
                    ask=stop_msg,
                    language=language.value,
                    interruption_handled=True
                )
        
        # Normalize user input
        raw_message = req.message.strip()
        normalized_message = enhanced_normalize_speech(raw_message)
        
        # Add user message to session
        if normalized_message:
            session.add_message(MessageRole.USER, normalized_message)
        
        # MANUAL FORM FIELD DETECTION - Check if user manually filled any fields
        if req.manual_form_data:
            logger.info(f"Detecting manual form data: {req.manual_form_data}")
            for field_name, field_value in req.manual_form_data.items():
                if field_value and str(field_value).strip():
                    # Update field state to mark as manually filled
                    field_key = conversation._get_field_key(field_name)
                    session.update_field(field_key, str(field_value).strip(), FieldStatus.COLLECTED)
                    logger.info(f"✅ Manual field update: {field_name} = {field_value}")
        
        # Get conversation response
        llm_response = conversation.process_user_input(normalized_message)
        
        # Generate audio for response with enhanced multilingual support
        audio_b64 = ""
        reply_text = llm_response.get("reply", llm_response.get("ask", ""))
        if reply_text:
            try:
                # Use language-aware TTS generation
                audio_b64 = await tts_to_base64_wav(reply_text, language)
            except Exception as e:
                logger.warning(f"Enhanced TTS generation failed: {e}")
        
        # Add agent response to session
        if reply_text:
            session.add_message(MessageRole.AGENT, reply_text)
        
        # Get form summary and completion status
        form_summary = conversation.get_form_summary()
        completion_status = conversation.get_completion_status()
        
        # Handle form submission if action is "submit"
        if llm_response.get("action") == "submit":
            try:
                # Prepare form data from session
                form_data = {}
                form_context_key = f"form_{form_id}"
                
                for field in form.fields:
                    field_key = f"{form_context_key}_{field.name}"
                    field_info = session.fields.get(field_key)
                    if field_info and field_info.value:
                        form_data[field.name] = field_info.value
                
                # Submit form
                response_data = {
                    "form_id": form_id,
                    "session_id": session_id,
                    "responses": form_data
                }
                
                form_response = form_store.submit_response(response_data)
                
                # Log successful submission
                logger.info(f"Form {form_id} submitted successfully by session {session_id}")
                
                # Update LLM response to include submission confirmation
                confirmation_msg = f"✅ {form.confirmation_message}"
                llm_response["ask"] = confirmation_msg
                llm_response["reply"] = confirmation_msg
                
            except Exception as e:
                logger.error(f"Form submission failed: {e}")
                error_msg = "ફોર્મ સબમિટ કરવામાં સમસ્યા થઈ." if language == Language.GUJARATI else "Failed to submit form."
                llm_response["ask"] = error_msg
                llm_response["reply"] = error_msg
                llm_response["action"] = "error"
        
        # Log response details
        logger.info(f"Dynamic chat response: action={llm_response.get('action')}, ask='{llm_response.get('ask')}', field_focus={llm_response.get('field_focus')}, language={language.value}")
        
        # Build enhanced response
        response = DynamicChatResponse(
            action=llm_response.get("action", "ask"),
            reply=reply_text,
            ask=llm_response.get("ask"),
            updates=llm_response.get("updates", {}),
            audio_b64=audio_b64,
            form_summary=form_summary,
            completion_status=completion_status,
            field_focus=llm_response.get("field_focus"),
            tone=llm_response.get("tone", "friendly"),
            language=language.value,
            greeting=llm_response.get("greeting"),
            interruption_handled=req.interruption_detected
        )
        
        logger.info(f"Dynamic chat processed for session {session_id}, form {form_id}: action={response.action}, language={language.value}")
        return response
        
    except Exception as e:
        logger.error(f"Dynamic chat processing failed for session {session_id}, form {form_id}: {e}\n{traceback.format_exc()}")
        
        # Return graceful error response in appropriate language
        language = Language.GUJARATI if req.language == "gu" else Language.ENGLISH
        error_reply = ("માફ કરશો, તકનીકી સમસ્યા છે. કૃપા કરીને ફરીથી પ્રયાસ કરો." 
                      if language == Language.GUJARATI else 
                      "I'm having a technical issue. Could you please try again?")
        
        error_audio = ""
        try:
            error_audio = await tts_to_base64_wav(error_reply, language)
        except Exception:
            pass
        
        return DynamicChatResponse(
            action="error",
            reply=error_reply,
            audio_b64=error_audio,
            form_summary=None,
            completion_status=None,
            language=language.value
        )

# Enhanced silence management endpoint with question repetition
@app.post("/silence-prompt")
async def silence_prompt(session_id: str = Query(...), language: str = Query("en")):
    """Handle silence prompts with enhanced question repetition system"""
    try:
        lang = Language.GUJARATI if language == "gu" else Language.ENGLISH
        
        # Check if session exists
        session = memory_store.get_or_create_session(session_id)
        
        # Get session from silence manager to check repetition count
        silence_session = silence_manager.sessions.get(session_id)
        
        if silence_session:
            repetition_count = silence_session.repetition_count
            
            # Generate appropriate silence prompt based on repetition count
            if repetition_count == 1:
                if lang == Language.GUJARATI:
                    prompt_text = "તમે ત્યાં છો?"
                else:
                    prompt_text = "Are you there?"
            elif repetition_count == 2:
                if lang == Language.GUJARATI:
                    prompt_text = "તમે હજી પણ ત્યાં છો? કૃપા કરીને જવાબ આપો."
                else:
                    prompt_text = "Are you still there? Please respond."
            else:
                if lang == Language.GUJARATI:
                    prompt_text = "હેલો? હું તમારા જવાબની રાહ જોઈ રહ્યો છું. શું આપણે આગળ વધીએ?"
                else:
                    prompt_text = "Hello? I'm waiting for your answer. Should we continue?"
        else:
            # Fallback if no silence session
            if lang == Language.GUJARATI:
                prompt_text = "તમે ત્યાં છો? કૃપા કરીને જવાબ આપો."
            else:
                prompt_text = "Are you there? Please respond."
        
        # Generate audio with enhanced multilingual TTS
        audio_b64 = ""
        try:
            audio_b64 = await tts_to_base64_wav(prompt_text, lang)
        except Exception as e:
            logger.warning(f"Enhanced TTS generation failed for silence prompt: {e}")
        
        # Add system message
        session.add_message(MessageRole.SYSTEM, f"Silence prompt: {prompt_text}")
        
        return {
            "status": "success",
            "message": prompt_text,
            "audio_b64": audio_b64,
            "language": language,
            "repetition_count": silence_session.repetition_count if silence_session else 0
        }
        
    except Exception as e:
        logger.error(f"Silence prompt failed for session {session_id}: {e}")
        return {"status": "error", "message": "Failed to generate silence prompt"}

# Language support endpoints
@app.get("/ui-translations/{language}")
def get_ui_translations(language: str):
    """Get UI translations for specified language"""
    try:
        lang = Language.GUJARATI if language == "gu" else Language.ENGLISH
        translations = language_support.ui_translations.get(lang.value, {})
        
        return {
            "status": "success",
            "language": language,
            "translations": translations
        }
    except Exception as e:
        logger.error(f"Failed to get UI translations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve translations"
        )

@app.post("/transliterate")
def transliterate_text(text: str = Query(...)):
    """Transliterate English-written Gujarati to proper Gujarati script"""
    try:
        transliterated = language_support.transliterate_to_gujarati(text)
        
        return {
            "status": "success",
            "original": text,
            "transliterated": transliterated
        }
    except Exception as e:
        logger.error(f"Transliteration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transliteration failed"
        )

# Standalone TTS endpoint
@app.post("/tts", response_model=TTSResponse)
async def text_to_speech(req: TTSRequest):
    """Convert text to speech with enhanced multilingual support"""
    try:
        # Detect language from text content
        language = Language.GUJARATI if language_support._is_transliterated_gujarati(req.text) or any(ord(char) >= 0x0A80 and ord(char) <= 0x0AFF for char in req.text) else Language.ENGLISH
        
        audio_b64 = await tts_to_base64_wav(req.text, language)
        return TTSResponse(audio=audio_b64, success=bool(audio_b64))
        
    except Exception as e:
        logger.error(f"Enhanced TTS conversion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Text-to-speech conversion failed"
        )

# Form Builder Endpoints
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
                    "updated_at": form.updated_at,
                    "shareable_link": f"/forms/{form.id}/fill"
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
        # Validate field types including password
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
                "shareable_link": f"/forms/{form.id}/fill",
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
    """Delete a form"""
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

@app.post("/forms/{form_id}/submit")
def submit_form(form_id: str, req: FormSubmissionRequest):
    """Submit form responses"""
    try:
        form = form_store.get_form(form_id)
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Form not found"
            )
        
        # Create response record
        response_data = {
            "form_id": form_id,
            "session_id": req.session_id,
            "responses": req.responses
        }
        
        response = form_store.submit_response(response_data)
        
        logger.info(f"Form submitted: {form_id} by session {req.session_id}")
        
        return {
            "status": "success",
            "message": form.confirmation_message,
            "response_id": response.id,
            "submitted_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Form submission failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Form submission failed"
        )

# Form Templates
@app.get("/forms/templates/list")
def list_templates():
    """List available form templates"""
    try:
        templates = []
        for template_id, template_data in SAMPLE_FORMS.items():
            templates.append({
                "id": template_id,
                "title": template_data["title"],
                "description": template_data["description"],
                "field_count": len(template_data["fields"])
            })
        
        return {
            "status": "success",
            "templates": templates,
            "count": len(templates)
        }
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list templates"
        )

@app.post("/forms/templates/{template_id}")
def create_from_template(template_id: str, title_override: Optional[str] = Query(None)):
    """Create form from template"""
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
        logger.error(f"Error creating from template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create form from template"
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )