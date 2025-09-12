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
    """Get appropriate Whisper model based on language with vasista22/whisper-gujarati-medium priority"""
    global _model_cache
    
    if language == Language.GUJARATI:
        # Priority 1: Try vasista22/whisper-gujarati-medium specifically
        gujarati_models = [
            "vasista22/whisper-gujarati-medium",  # First priority - specific model
            "openai/whisper-small",              # Fallback to standard Whisper with gu language
            "openai/whisper-base"                # Final fallback
        ]
        cache_key = f"gujarati_vasista22"
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
            # Try specific Gujarati models in order of preference
            model = None
            model_used = None
            
            for model_name in gujarati_models:
                try:
                    logger.info(f"Attempting to load Gujarati model: {model_name}")
                    model = WhisperModel(model_name, device=settings.WHISPER_DEVICE)
                    model_used = model_name
                    logger.info(f"✅ Successfully loaded Gujarati STT model: {model_name}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to load {model_name}: {e}")
                    continue
            
            if model is None:
                # Final fallback: use standard model with gujarati language setting
                model = WhisperModel(settings.WHISPER_MODEL_SIZE, device=settings.WHISPER_DEVICE)
                model_used = f"fallback_{settings.WHISPER_MODEL_SIZE}"
                logger.warning(f"Using fallback model for Gujarati: {model_used}")
        else:
            # Load standard Whisper model for English
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
            logger.warning(f"Using final fallback base model for {language.value}")
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
            segments, info = model.transcribe(
                path, 
                vad_filter=True, 
                language="gu",
                temperature=0.0,      # More deterministic for Gujarati
                beam_size=5,          # Better accuracy
                best_of=5,            # Multiple candidates
                condition_on_previous_text=False  # Better for Gujarati
            )
        else:
            segments, info = model.transcribe(path, vad_filter=True, language="en")
        
        text = " ".join([s.text.strip() for s in segments]).strip()
        
        # Enhanced post-processing for Gujarati
        if language == Language.GUJARATI and text:
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

def transcribe_b64(audio_b64: str, language: Language = Language.ENGLISH) -> str:
    """Transcribe base64 audio with enhanced Gujarati support using vasista22/whisper-gujarati-medium"""
    model = _get_model_for_language(language)
    
    try:
        audio_bytes = base64.b64decode(audio_b64)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_bytes)
            path = tmp.name
        
        try:
            # Enhanced Gujarati transcription with vasista22 model optimizations
            if language == Language.GUJARATI:
                segments, info = model.transcribe(
                    path, 
                    vad_filter=True, 
                    language="gu",
                    temperature=0.0,              # Deterministic output
                    beam_size=5,                  # Better accuracy for Gujarati
                    best_of=5,                    # Multiple candidates
                    condition_on_previous_text=False,  # Better for Gujarati context
                    no_speech_threshold=0.6,      # Adjust for Gujarati speech patterns
                    logprob_threshold=-1.0,       # More permissive for Gujarati
                    compression_ratio_threshold=2.4  # Adjust for Gujarati text patterns
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
                text = clean_gujarati_transcription(text)
                logger.info(f"✅ Gujarati transcription processed: {text[:50]}...")
            
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
    """Enhanced cleaning for Gujarati transcription from vasista22 model"""
    if not text:
        return text
    
    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Fix common Gujarati transcription patterns from vasista22 model
    # These patterns are based on common issues with the specific model
    
    # Fix common word boundaries
    text = re.sub(r'([ા-્])(\s+)([ક-હ])', r'\1\3', text)  # Remove unnecessary spaces in Gujarati words
    
    # Fix common mispronunciations
    gujarati_corrections = {
        'તમારુ': 'તમારું',
        'નામ': 'નામ',
        'શુ': 'શું',
        'છે': 'છે',
        'કરો': 'કરો',
        'બોલો': 'બોલો'
    }
    
    for wrong, correct in gujarati_corrections.items():
        text = text.replace(wrong, correct)
    
    # Remove any Latin characters that might have been incorrectly transcribed
    text = re.sub(r'[A-Za-z]+', '', text)
    
    # Clean up any double spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
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

def get_model_info(language: Language = Language.ENGLISH) -> dict:
    """Get information about the loaded model"""
    cache_key = f"gujarati_vasista22" if language == Language.GUJARATI else f"english_{settings.WHISPER_MODEL_SIZE}"
    
    return {
        "language": language.value,
        "cache_key": cache_key,
        "model_loaded": cache_key in _model_cache,
        "recommended_model": "vasista22/whisper-gujarati-medium" if language == Language.GUJARATI else settings.WHISPER_MODEL_SIZE
    }