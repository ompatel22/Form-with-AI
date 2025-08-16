import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .config import settings
from .schemas import (
    STTResponse, StartFormRequest, StartFormResponse,
    TurnRequest, TurnResponse, ResetRequest
)
from .stt import transcribe_file
from .tts import synth_to_file
from .llm import OpenAILLM   # ⬅️ changed from GroqLLM
from .memory import MemoryStore
from .dialog_dynamic import DynamicDialog
from .utils import get_logger

logger = get_logger(__name__)
app = FastAPI(title="Voice Conversational Form Agent", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static for synthesized audio
os.makedirs(settings.MEDIA_DIR, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.MEDIA_DIR), name="media")

# Singletons
memory = MemoryStore()
llm = OpenAILLM()   # ⬅️ changed from GroqLLM()

@app.get("/health")
def health():
    return {"status": "ok", "env": settings.ENV}

# ---------- STT ----------
@app.post("/v1/stt", response_model=STTResponse)
async def stt_endpoint(file: UploadFile = File(...)):
    try:
        text = transcribe_file(file)
        return STTResponse(text=text)
    except Exception as e:
        logger.exception("STT failed")
        raise HTTPException(status_code=500, detail=str(e))

# ---------- Start dynamic form ----------
@app.post("/v1/form/start", response_model=StartFormResponse)
async def start_form(req: StartFormRequest):
    # Validate basic schema shape
    fields = req.schema.get("fields", [])
    if not isinstance(fields, list) or not fields:
        raise HTTPException(status_code=400, detail="schema.fields must be a non-empty list")

    dialog = DynamicDialog(req.schema)
    state = {
        "schema": req.schema,
        "index": dialog.index,
        "form": dialog.form,
        "completed": dialog.completed,
    }
    memory.init_session(req.session_id, req.schema)
    # Persist dialog initial state
    s = memory.require(req.session_id)
    s["index"] = dialog.index
    s["form"] = dialog.form
    s["completed"] = dialog.completed
    memory.save(req.session_id, s)

    return StartFormResponse(
        session_id=req.session_id,
        next_question=dialog.next_question(),
        is_complete=dialog.is_complete()
    )

# ---------- Dialog turn (speech or text already pre-processed to text) ----------
@app.post("/v1/agent/turn", response_model=TurnResponse)
async def agent_turn(req: TurnRequest):
    try:
        s = memory.require(req.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found. Call /v1/form/start first.")

    schema = s["schema"]
    dialog = DynamicDialog(schema)
    dialog.index = s["index"]
    dialog.form = s["form"]
    dialog.completed = s["completed"]

    # Use LLM to determine intent/updates
    llm_out = llm.infer(schema["fields"], dialog.form, req.user_text)
    action = llm_out.get("action", "ask")
    updates = llm_out.get("updates", {}) or {}
    ask = llm_out.get("ask", "")

    # Try to apply updates with server-side validation
    error = None
    if updates:
        error = dialog.set_updates(updates)

    if error:
        reply_text = f"{error} Please try again. {dialog.next_question() or ''}".strip()
    else:
        # If not complete, either ask next question or continue asking provided by model
        if dialog.is_complete():
            reply_text = "All fields captured. Do you want to submit?"
            dialog.completed = True
        else:
            reply_text = ask or dialog.confirm_or_ask()

    # Persist session
    s["index"] = dialog.index
    s["form"] = dialog.form
    s["completed"] = dialog.completed
    memory.save(req.session_id, s)

    # TTS
    audio_file = synth_to_file(reply_text, req.session_id)
    audio_url = f"/media/{audio_file}" if audio_file else None

    return TurnResponse(
        agent_reply=reply_text,
        audio_url=audio_url,
        form_state=dialog.form,
        is_complete=dialog.completed
    )

# ---------- Reset ----------
@app.post("/v1/agent/reset")
async def agent_reset(req: ResetRequest):
    memory.reset(req.session_id)
    return {"ok": True}

# ---------- Inspect state ----------
@app.get("/v1/agent/state/{session_id}")
async def agent_state(session_id: str):
    try:
        return memory.get_state(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")