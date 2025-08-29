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
from .memory import memory_store, FieldStatus, MessageRole
from .form_builder import FormSchema, FormField, FieldType, FormResponse, form_store, SAMPLE_FORMS
from .dynamic_chat import EnhancedDynamicFormConversation

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
    logger.info("🚀 Enhanced Form Agent starting up...")
    
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

# Main dynamic chat endpoint
@app.post("/dynamic-chat", response_model=DynamicChatResponse)
async def dynamic_chat(req: DynamicChatRequest):
    """Enhanced dynamic chat endpoint with improved context handling"""
    session_id = req.session_id
    form_id = req.form_id
    
    try:
        # Get or create session
        session = memory_store.get_or_create_session(session_id)
        
        # Log session and form details for debugging
        logger.info(f"Dynamic chat request: session={session_id}, form={form_id}, message='{req.message}'")
        form = form_store.get_form(form_id)
        if not form:
            logger.error(f"Form {form_id} not found")
            raise HTTPException(status_code=404, detail="Form not found")
        logger.info(f"Form fields: {[f.name for f in form.fields]}")
        
        # Create form-specific conversation handler
        conversation = EnhancedDynamicFormConversation(form_id, session)
        
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
        
        # Generate audio for response
        audio_b64 = ""
        reply_text = llm_response.get("reply", llm_response.get("ask", ""))
        if reply_text:
            try:
                audio_b64 = tts_to_base64_wav(reply_text)
            except Exception as e:
                logger.warning(f"TTS generation failed: {e}")
        
        # Add agent response to session
        if reply_text:
            session.add_message(MessageRole.AGENT, reply_text)
        
        # Get form summary and completion status
        form_summary = conversation.get_form_summary()
        completion_status = conversation.get_completion_status()
        
        # Log response details
        logger.info(f"Dynamic chat response: action={llm_response.get('action')}, ask='{llm_response.get('ask')}', field_focus={llm_response.get('field_focus')}")
        
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
            tone=llm_response.get("tone", "friendly")
        )
        
        logger.info(f"Dynamic chat processed for session {session_id}, form {form_id}: action={response.action}")
        return response
        
    except Exception as e:
        logger.error(f"Dynamic chat processing failed for session {session_id}, form {form_id}: {e}\n{traceback.format_exc()}")
        
        # Return graceful error response
        error_reply = "I'm having a technical issue. Could you please try again?"
        error_audio = ""
        try:
            error_audio = tts_to_base64_wav(error_reply)
        except Exception:
            pass
        
        return DynamicChatResponse(
            action="error",
            reply=error_reply,
            audio_b64=error_audio,
            form_summary=None,
            completion_status=None
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