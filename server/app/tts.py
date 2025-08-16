import os
import time
from typing import Optional
from .config import settings
from .utils import get_logger

logger = get_logger(__name__)

# Optional backends
_TTS_ENGINE = None
_COQUI_TTS = None

def _init_pyttsx3():
    global _TTS_ENGINE
    if _TTS_ENGINE is None:
        import pyttsx3
        _TTS_ENGINE = pyttsx3.init()
        if settings.TTS_RATE:
            _TTS_ENGINE.setProperty("rate", _TTS_RATE_SAFE(settings.TTS_RATE))
        if settings.TTS_VOICE and settings.TTS_VOICE != "default":
            for v in _TTS_ENGINE.getProperty("voices"):
                if settings.TTS_VOICE.lower() in v.name.lower():
                    _TTS_ENGINE.setProperty("voice", v.id)
                    break
    return _TTS_ENGINE

def _TTS_RATE_SAFE(rate: int) -> int:
    # pyttsx3 default depends on engine; 0 means leave default
    return rate

def synth_to_file(text: str, session_id: str) -> Optional[str]:
    os.makedirs(settings.MEDIA_DIR, exist_ok=True)
    fname = f"{session_id}_{int(time.time()*1000)}.wav"
    out_path = os.path.join(settings.MEDIA_DIR, fname)

    if settings.TTS_BACKEND == "none":
        return None

    if settings.TTS_BACKEND == "pyttsx3":
        engine = _init_pyttsx3()
        engine.save_to_file(text, out_path)
        engine.runAndWait()
        return fname

    if settings.TTS_BACKEND == "coqui":
        # Lazy import to keep container light if not used
        global _COQUI_TTS
        if _COQUI_TTS is None:
            from TTS.api import TTS
            _COQUI_TTS = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")
        _COQUI_TTS.tts_to_file(text=text, file_path=out_path)
        return fname

    # fallback none
    return None
