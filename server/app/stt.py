import os
import tempfile
import base64
from io import BytesIO
from fastapi import UploadFile
from faster_whisper import WhisperModel
from .config import settings

_model = None

def _ensure_model():
    global _model
    if _model is None:
        _model = WhisperModel(settings.WHISPER_MODEL_SIZE, device=settings.WHISPER_DEVICE)

def transcribe_file(file: UploadFile) -> str:
    _ensure_model()
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(file.file.read())
        path = tmp.name
    segments, info = _model.transcribe(path, vad_filter=True)
    text = " ".join([s.text.strip() for s in segments]).strip()
    try:
        os.remove(path)
    except Exception:
        pass
    return text

def transcribe_b64(audio_b64: str) -> str:
    _ensure_model()
    audio_bytes = base64.b64decode(audio_b64)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_bytes)
        path = tmp.name
    segments, info = _model.transcribe(path, vad_filter=True)
    text = " ".join([s.text.strip() for s in segments]).strip()
    try:
        os.remove(path)
    except Exception:
        pass
    return text