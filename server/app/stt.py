import os
import tempfile
import base64
import logging
import re
from io import BytesIO
from fastapi import UploadFile
from faster_whisper import WhisperModel
from .config import settings
from .language_support import Language

logger = logging.getLogger(__name__)

_model_cache = {}

def _get_model_for_language(language: Language = Language.ENGLISH):
    """Get appropriate Whisper model based on language"""
    global _model_cache
    
    if language == Language.GUJARATI:
        # Try multiple Gujarati models in order of preference
        gujarati_models = [
            "openai/whisper-small",  # Fallback to standard Whisper with Gujarati language setting
            "openai/whisper-base"    # Another fallback option
        ]
        cache_key = f"gujarati_fallback"
    else:
        # Default English model
        model_name = settings.WHISPER_MODEL_SIZE
        cache_key = f"english_{model_name}"
    
    # Return cached model if available
    if cache_key in _model_cache:
        logger.info(f"Using cached {language.value} model: {cache_key}")
        return _model_cache[cache_key]
    
    try:
        logger.info(f"Loading {language.value} STT model")
        
        if language == Language.GUJARATI:
            # Use standard Whisper model but specify Gujarati language during transcription
            model = WhisperModel(settings.WHISPER_MODEL_SIZE, device=settings.WHISPER_DEVICE)
            logger.info(f"✅ Gujarati STT model loaded (using standard Whisper with gu language setting)")
        else:
            # Load standard Whisper model
            model = WhisperModel(settings.WHISPER_MODEL_SIZE, device=settings.WHISPER_DEVICE)
            logger.info(f"✅ English STT model loaded successfully: {settings.WHISPER_MODEL_SIZE}")
        
        _model_cache[cache_key] = model
        return model
        
    except Exception as e:
        logger.error(f"Failed to load {language.value} STT model: {e}")
        
        # Final fallback to basic model
        try:
            fallback_model = WhisperModel("base", device=settings.WHISPER_DEVICE)
            _model_cache[cache_key] = fallback_model
            logger.warning(f"Using fallback base model for {language.value}")
            return fallback_model
        except Exception as fallback_error:
            logger.error(f"Even fallback model failed: {fallback_error}")
            raise fallback_error

def transcribe_file(file: UploadFile, language: Language = Language.ENGLISH) -> str:
    """Transcribe uploaded file with language-specific model"""
    model = _get_model_for_language(language)
    
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(file.file.read())
        path = tmp.name
    
    try:
        # Set language for transcription
        if language == Language.GUJARATI:
            segments, info = model.transcribe(path, vad_filter=True, language="gu")
        else:
            segments, info = model.transcribe(path, vad_filter=True, language="en")
        
        text = " ".join([s.text.strip() for s in segments]).strip()
        logger.info(f"Transcribed ({language.value}): {text[:100]}...")
        return text
        
    except Exception as e:
        logger.error(f"Transcription failed for {language.value}: {e}")
        return ""
    finally:
        try:
            os.remove(path)
        except Exception:
            pass

def transcribe_b64(audio_b64: str, language: Language = Language.ENGLISH) -> str:
    """Transcribe base64 audio with language-specific model"""
    model = _get_model_for_language(language)
    
    try:
        audio_bytes = base64.b64decode(audio_b64)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_bytes)
            path = tmp.name
        
        try:
            # Set language and better parameters for transcription
            if language == Language.GUJARATI:
                # Use Gujarati language code and better parameters for Gujarati
                segments, info = model.transcribe(
                    path, 
                    vad_filter=True, 
                    language="gu",
                    temperature=0.0,  # More deterministic
                    beam_size=5,      # Better accuracy
                    best_of=5         # Multiple candidates
                )
            else:
                segments, info = model.transcribe(
                    path, 
                    vad_filter=True, 
                    language="en",
                    temperature=0.0,
                    beam_size=5,
                    best_of=5
                )
            
            text = " ".join([s.text.strip() for s in segments]).strip()
            
            # Enhanced post-processing for Gujarati
            if language == Language.GUJARATI and text:
                # Clean up common Gujarati transcription issues
                text = clean_gujarati_transcription(text)
            
            logger.info(f"Transcribed ({language.value}): {text[:100]}...")
            return text
            
        except Exception as e:
            logger.error(f"Transcription failed for {language.value}: {e}")
            return ""
        finally:
            try:
                os.remove(path)
            except Exception:
                pass
                
    except Exception as e:
        logger.error(f"Base64 decode failed: {e}")
        return ""

def clean_gujarati_transcription(text: str) -> str:
    """Clean up common issues in Gujarati transcription"""
    if not text:
        return text
    
    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Fix common transcription patterns
    # Add more cleaning rules as needed based on testing
    
    return text

def warm_up_models():
    """Pre-load both English and Gujarati models for faster response"""
    try:
        logger.info("Warming up STT models...")
        _get_model_for_language(Language.ENGLISH)
        _get_model_for_language(Language.GUJARATI)
        logger.info("✅ STT models warmed up successfully")
    except Exception as e:
        logger.warning(f"Model warm-up failed: {e}")

def clear_model_cache():
    """Clear model cache to free memory"""
    global _model_cache
    _model_cache.clear()
    logger.info("STT model cache cleared")