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
    """Get appropriate Whisper model based on language with improved Gujarati support"""
    global _model_cache
    
    if language == Language.GUJARATI:
        # Enhanced Gujarati model priority list with more reliable models
        gujarati_models = [
            "small",                            # Standard Whisper small works well with gu language setting
            "medium",                           # Better accuracy for Gujarati
            "base",                             # Basic fallback
            "tiny"                              # Emergency fallback
        ]
        cache_key = f"gujarati_enhanced"
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
            # Try Gujarati models in order of preference
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
                # Final fallback: try tiny model as last resort
                try:
                    model = WhisperModel("tiny", device="cpu")  # Force CPU as final fallback
                    model_used = "tiny_cpu_fallback"
                    logger.warning(f"Using final fallback model for Gujarati: {model_used}")
                except Exception as e:
                    logger.error(f"All Gujarati model loading failed: {e}")
                    raise e
        else:
            # Load standard Whisper model for English
            model = WhisperModel(settings.WHISPER_MODEL_SIZE, device=settings.WHISPER_DEVICE)
            logger.info(f"✅ English STT model loaded successfully: {settings.WHISPER_MODEL_SIZE}")
        
        # Store both model and metadata
        _model_cache[cache_key] = {
            'model': model,
            'model_name': model_used if language == Language.GUJARATI else settings.WHISPER_MODEL_SIZE,
            'language': language,
            'loaded_at': os.path.getmtime('.')  # timestamp
        }
        
        return model
        
    except Exception as e:
        logger.error(f"Failed to load {language.value} STT model: {e}")
        raise e

def transcribe_file(file: UploadFile, language: Language = Language.ENGLISH) -> str:
    """Transcribe uploaded file with language-specific model"""
    model_info = _get_model_for_language(language)
    model = model_info if not isinstance(model_info, dict) else model_info['model']
    
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(file.file.read())
        path = tmp.name
    
    try:
        # Enhanced transcription settings for better Gujarati support
        if language == Language.GUJARATI:
            segments, info = model.transcribe(
                path, 
                vad_filter=True, 
                language="gu",
                temperature=0.1,            # Slightly less deterministic for better results
                beam_size=3,                # Reduced for faster processing
                best_of=3,                  # Multiple candidates but fewer
                condition_on_previous_text=True,  # Use context for better results
                initial_prompt="આ ગુજરાતી ભાષામાં બોલાયેલું છે।"  # Gujarati context prompt
            )
        else:
            segments, info = model.transcribe(
                path, 
                vad_filter=True, 
                language="en",
                temperature=0.0,
                beam_size=3,
                best_of=3
            )
        
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
    """Transcribe base64 audio with enhanced Gujarati support"""
    model_info = _get_model_for_language(language)
    model = model_info if not isinstance(model_info, dict) else model_info['model']
    
    try:
        audio_bytes = base64.b64decode(audio_b64)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_bytes)
            path = tmp.name
        
        try:
            # Enhanced transcription with adaptive parameters
            if language == Language.GUJARATI:
                segments, info = model.transcribe(
                    path, 
                    vad_filter=True, 
                    language="gu",
                    temperature=0.1,                    # Slightly less deterministic
                    beam_size=3,                        # Balanced for speed/accuracy
                    best_of=3,                          # Multiple candidates
                    condition_on_previous_text=True,    # Use context
                    no_speech_threshold=0.5,            # More sensitive for Gujarati
                    logprob_threshold=-1.2,             # More permissive
                    compression_ratio_threshold=2.2,    # Adjust for Gujarati patterns
                    initial_prompt="આ ગુજરાતી ભાષામાં બોલાયેલું છે।"  # Context prompt
                )
            else:
                segments, info = model.transcribe(
                    path, 
                    vad_filter=True, 
                    language="en",
                    temperature=0.0,
                    beam_size=3,
                    best_of=3,
                    no_speech_threshold=0.6,
                    logprob_threshold=-1.0
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
            # Try fallback transcription with minimal settings
            try:
                logger.info(f"Attempting fallback transcription for {language.value}")
                segments, info = model.transcribe(
                    path, 
                    language="gu" if language == Language.GUJARATI else "en",
                    temperature=0.2,
                    beam_size=1
                )
                text = " ".join([s.text.strip() for s in segments]).strip()
                
                if language == Language.GUJARATI and text:
                    text = clean_gujarati_transcription(text)
                
                logger.info(f"✅ Fallback transcription successful: {text[:50]}...")
                return text
                
            except Exception as fallback_error:
                logger.error(f"Fallback transcription also failed: {fallback_error}")
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
    """Enhanced but careful cleaning for Gujarati transcription"""
    if not text:
        return text
    
    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Fix common Gujarati transcription patterns
    # Be more careful about corrections to avoid over-processing
    
    # Fix common word boundaries (only if clearly incorrect)
    text = re.sub(r'([ા-્])\s+([ા-્])', r'\1\2', text)  # Join broken Gujarati characters
    
    # Fix common mispronunciations (only clear cases)
    gujarati_corrections = {
        'તમારુ': 'તમારું',
        'શુ': 'શું',
        'કરો ': 'કરો ',
        'બોલો ': 'બોલો ',
        'જવાબ': 'જવાબ',
        'નામ ': 'નામ ',
        'છે ': 'છે '
    }
    
    for wrong, correct in gujarati_corrections.items():
        text = text.replace(wrong, correct)
    
    # Only remove obvious Latin noise (not mixed content)
    # Remove standalone English words that are clearly noise
    words = text.split()
    cleaned_words = []
    
    for word in words:
        # Keep word if it has any Gujarati characters
        if any('\u0A80' <= char <= '\u0AFF' for char in word):
            cleaned_words.append(word)
        # Keep short English words that might be intentional (names, etc.)
        elif len(word) <= 3:
            cleaned_words.append(word)
        # Keep longer English words if they're mixed in reasonably
        elif len([w for w in words if any('\u0A80' <= c <= '\u0AFF' for c in w)]) > len(words) * 0.3:
            cleaned_words.append(word)
        # Otherwise, it's likely transcription noise
        else:
            logger.debug(f"Removing likely noise word: {word}")
    
    text = ' '.join(cleaned_words)
    
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
        logger.error(f"Model warm-up failed: {e}")
        # Continue anyway - models will load on first use

def clear_model_cache():
    """Clear model cache to free memory"""
    global _model_cache
    _model_cache.clear()
    logger.info("STT model cache cleared")

def get_model_info(language: Language = Language.ENGLISH) -> dict:
    """Get information about the loaded model"""
    cache_key = f"gujarati_enhanced" if language == Language.GUJARATI else f"english_{settings.WHISPER_MODEL_SIZE}"
    
    model_info = _model_cache.get(cache_key)
    if model_info and isinstance(model_info, dict):
        return {
            "language": language.value,
            "cache_key": cache_key,
            "model_loaded": True,
            "model_name": model_info.get('model_name', 'unknown'),
            "loaded_at": model_info.get('loaded_at', 'unknown')
        }
    else:
        return {
            "language": language.value,
            "cache_key": cache_key,
            "model_loaded": cache_key in _model_cache,
            "recommended_model": "enhanced_gujarati" if language == Language.GUJARATI else settings.WHISPER_MODEL_SIZE
        }