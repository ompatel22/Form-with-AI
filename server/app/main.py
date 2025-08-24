import re
import json
import base64
import tempfile
import os
from typing import Dict, Any, Optional
from fastapi.middleware.cors import CORSMiddleware
import pyttsx3
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import logging

from .llm import GeminiLLM

app = FastAPI(title="Conversational Form Agent (LLM-driven, Gemini)")

# Allow frontend origins during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ordered form schema sent to LLM
FORM_FIELDS = [
    {"name": "full_name", "type": "string", "required": True},
    {"name": "email", "type": "email", "required": True},
    {"name": "phone", "type": "string", "required": True},
    {"name": "dob", "type": "date", "required": True},
]

# In-memory session store
SESSIONS: Dict[str, Dict[str, Any]] = {}

def tts_to_base64_wav(text: str) -> str:
    engine = pyttsx3.init()
    engine.setProperty("rate", 150)
    engine.setProperty("volume", 1.0)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tf:
        temp_path = tf.name
    try:
        engine.save_to_file(text, temp_path)
        engine.runAndWait()
        with open(temp_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode("utf-8")
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass

# Pydantic models
class ChatRequest(BaseModel):
    session_id: str
    message: str = ""

class ChatResponse(BaseModel):
    action: str
    reply: str
    ask: Optional[str] = None
    updates: Optional[Dict[str, Any]] = None
    audio_b64: Optional[str] = None

class TTSRequest(BaseModel):
    text: str

class TTSResponse(BaseModel):
    audio: str

class SubmitRequest(BaseModel):
    full_name: str
    email: str
    phone: str
    dob: str

logger = logging.getLogger(__name__)

def init_session(session_id: str):
    SESSIONS[session_id] = {
        "form": {},
        "messages": [],
        "completed": False,
    }

def get_session(session_id: str) -> Dict[str, Any]:
    if session_id not in SESSIONS:
        init_session(session_id)
    return SESSIONS[session_id]

def normalize_user_text(text: str) -> str:
    s = text or ""
    s = re.sub(r"\bat\s+the\s+rate\b", "@", s, flags=re.IGNORECASE)
    s = re.sub(r"\bdot\s+com\b", ".com", s, flags=re.IGNORECASE)
    def collapse_spelled(m):
        letters = re.findall(r"[A-Za-z]", m.group(0))
        return "".join(letters)
    s = re.sub(r'(?:\b[A-Za-z]\b(?:\s+)){2,}\b[A-Za-z]\b', lambda m: collapse_spelled(m), s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

llm = GeminiLLM()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/reset")
def reset(session_id: str = Query("session1")):
    init_session(session_id)
    return {"status": "reset", "session_id": session_id}

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    sid = req.session_id
    session = get_session(sid)

    raw_user = (req.message or "").strip()
    normalized = normalize_user_text(raw_user)
    session["messages"].append({"role": "user", "content": normalized})

    llm_out = llm.infer(FORM_FIELDS, session["form"], normalized)

    if not isinstance(llm_out, dict):
        reply_text = str(llm_out)
        audio = tts_to_base64_wav(reply_text)
        session["messages"].append({"role": "agent", "content": reply_text})
        return ChatResponse(
            action="error",
            reply=reply_text,
            ask=None,
            updates=session["form"],
            audio_b64=audio,
        )

    action = llm_out.get("action", "error")
    updates = llm_out.get("updates") or {}
    ask_text = llm_out.get("ask") or ""

    # Apply updates directly (trust LLM for validation)
    if updates:
        session["form"].update(updates)

    # Respond based on action
    reply = ask_text or {
        "ask": "Could you clarify?",
        "set": "Okay, I've noted that.",
        "done": f"All fields captured. Summary: {json.dumps(session['form'])}",
        "error": "Sorry, I didn't understand. Please rephrase.",
    }.get(action, "Sorry, I didn’t understand. Please rephrase.")

    audio = tts_to_base64_wav(reply)
    session["messages"].append({"role": "agent", "content": reply})

    if action == "done":
        session["completed"] = True

    return ChatResponse(
        action=action,
        reply=reply,
        ask=ask_text if action in ["ask", "set"] else None,
        updates=session["form"],
        audio_b64=audio,
    )

@app.post("/tts", response_model=TTSResponse)
def tts(req: TTSRequest):
    try:
        audio_b64 = tts_to_base64_wav(req.text)
        return TTSResponse(audio=audio_b64)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/submit")
async def submit_form(req: SubmitRequest):
    logger.info(f"Form submitted: {req.dict()}")
    return {"status": "ok", "data": req.dict()}
