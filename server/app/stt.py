import os
import tempfile
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
