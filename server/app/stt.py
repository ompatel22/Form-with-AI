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

# CRITICAL: Define minimum model sizes for reliable language detection
MIN_MODEL_FOR_GUJARATI = "small"  # Never use tiny/base for Gujarati
FALLBACK_MODEL = "small"  # Safe fallback that works for both languages

def _get_model_for_language(language: Language = Language.ENGLISH):
    """Get appropriate Whisper model based on language with guaranteed Gujarati support"""
    global _model_cache
    
    if language == Language.GUJARATI:
        # FIXED: Only use models that can reliably handle Gujarati
        gujarati_models = [
            "small",   # Best accuracy for Gujarati
            "medium",    # Good balance, minimum acceptable
        ]
        cache_key = "gujarati_enhanced"
    else:
        # English can use configured model
        model_name = settings.WHISPER_MODEL_SIZE
        cache_key = f"english_{model_name}"
    
    # Return cached model if available
    if cache_key in _model_cache:
        logger.info(f"Using cached {language.value} model: {cache_key}")
        return _model_cache[cache_key]
    
    try:
        logger.info(f"Loading {language.value} STT model")
        
        if language == Language.GUJARATI:
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
                raise RuntimeError(
                    "CRITICAL: Cannot load any suitable model for Gujarati. "
                    "Models 'medium' and 'small' are required for reliable Gujarati transcription. "
                    "Please ensure these models are available."
                )
        else:
            # Load standard Whisper model for English
            model = WhisperModel(settings.WHISPER_MODEL_SIZE, device=settings.WHISPER_DEVICE)
            model_used = settings.WHISPER_MODEL_SIZE
            logger.info(f"✅ English STT model loaded successfully: {settings.WHISPER_MODEL_SIZE}")
        
        # FIXED: Always store as dict with consistent structure
        _model_cache[cache_key] = {
            'model': model,
            'model_name': model_used,
            'language': language,
            'loaded_at': os.path.getmtime('.')
        }
        
        return _model_cache[cache_key]
        
    except Exception as e:
        logger.error(f"Failed to load {language.value} STT model: {e}")
        raise e

def transcribe_file(file: UploadFile, language: Language = Language.ENGLISH) -> str:
    """Transcribe uploaded file with language-specific model"""
    model_info = _get_model_for_language(language)
    model = model_info['model']  # FIXED: Always extract from dict
    
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(file.file.read())
        path = tmp.name
    
    try:
        if language == Language.GUJARATI:
            segments, info = model.transcribe(
                path, 
                vad_filter=True, 
                language="gu",
                temperature=0.0,            # FIXED: Use 0.0 for deterministic results
                beam_size=5,                # FIXED: Increased for better accuracy
                best_of=5,                  # FIXED: More candidates
                condition_on_previous_text=True,
                initial_prompt="આ ગુજરાતી ભાષામાં બોલાયેલું છે. સ્પષ્ટ અને શુદ્ધ ગુજરાતી."
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
    import datetime
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    
    logger.info(f"[LOG] [{timestamp}] Current language mode: {language.value}")
    
    model_info = _get_model_for_language(language)
    model = model_info['model']  # FIXED: Always extract from dict
    model_name = model_info['model_name']
    
    # VALIDATION: Check if model is suitable for the language
    if language == Language.GUJARATI:
        if model_name not in ['small', 'medium', 'large', 'large-v2', 'large-v3']:
            logger.error(f"[LOG] [{timestamp}] ❌ CRITICAL: Model '{model_name}' is NOT suitable for Gujarati!")
            logger.error(f"[LOG] [{timestamp}] Gujarati requires at least 'small' model. Current model will produce poor results.")
    
    try:
        audio_bytes = base64.b64decode(audio_b64)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_bytes)
            path = tmp.name
        
        try:
            if language == Language.GUJARATI:
                logger.info(f"[LOG] [{timestamp}] Forcing Whisper language to: gu (Gujarati)")
                logger.info(f"[LOG] [{timestamp}] Using model: {model_name}")
                
                # FIXED: Optimal settings for Gujarati
                segments, info = model.transcribe(
                    path, 
                    vad_filter=True, 
                    language="gu",                      # Force Gujarati
                    temperature=0.0,                    # Deterministic
                    beam_size=5,                        # Better search
                    best_of=5,                          # More candidates
                    condition_on_previous_text=True,    # Use context
                    no_speech_threshold=0.6,            # Standard threshold
                    logprob_threshold=-1.0,             # Standard threshold
                    compression_ratio_threshold=2.4,    # Slightly relaxed for Gujarati
                    initial_prompt="આ ગુજરાતી ભાષામાં બોલાયેલું છે. સ્પષ્ટ અને શુદ્ધ ગુજરાતી બોલો."
                )
            else:
                logger.info(f"[LOG] [{timestamp}] Forcing Whisper language to: en (English)")
                logger.info(f"[LOG] [{timestamp}] Using model: {model_name}")
                
                segments, info = model.transcribe(
                    path, 
                    vad_filter=True, 
                    language="en",
                    temperature=0.0,
                    beam_size=5,
                    best_of=5,
                    no_speech_threshold=0.6,
                    logprob_threshold=-1.0
                )
            
            # Log metadata
            detected_lang = getattr(info, 'language', 'unknown')
            lang_prob = getattr(info, 'language_probability', 0.0)
            duration = getattr(info, 'duration', 0.0)
            duration_after_vad = getattr(info, 'duration_after_vad', 0.0)
            
            logger.info(f"[LOG] [{timestamp}] ========== WHISPER METADATA ==========")
            logger.info(f"[LOG] [{timestamp}] Detected language: {detected_lang}")
            logger.info(f"[LOG] [{timestamp}] Language probability: {lang_prob:.4f}")
            logger.info(f"[LOG] [{timestamp}] Audio duration: {duration:.2f}s")
            logger.info(f"[LOG] [{timestamp}] Duration after VAD: {duration_after_vad:.2f}s")
            
            # VALIDATION: Check for language mismatch
            expected_lang = "gu" if language == Language.GUJARATI else "en"
            if detected_lang != expected_lang:
                logger.warning(
                    f"[LOG] [{timestamp}] ⚠️ LANGUAGE MISMATCH DETECTED!\n"
                    f"  Expected: {expected_lang}\n"
                    f"  Detected: {detected_lang} (confidence: {lang_prob:.4f})\n"
                    f"  Model: {model_name}\n"
                    f"  This indicates the audio may be in a different language than selected,\n"
                    f"  OR the model is too small to properly detect {expected_lang}."
                )
                
                # If Gujarati mode but detected English with high confidence
                if language == Language.GUJARATI and detected_lang == 'en' and lang_prob > 0.8:
                    logger.error(
                        f"[LOG] [{timestamp}] ❌ HIGH CONFIDENCE ENGLISH DETECTED IN GUJARATI MODE!\n"
                        f"  The user is likely speaking English, not Gujarati.\n"
                        f"  Consider prompting user to verify language selection."
                    )
            
            # Log top language probabilities
            all_lang_probs = getattr(info, 'all_language_probs', None)
            if all_lang_probs:
                sorted_probs = sorted(all_lang_probs, key=lambda x: x[1], reverse=True)[:5]
                logger.info(f"[LOG] [{timestamp}] Top 5 language probabilities:")
                for lang_code, prob in sorted_probs:
                    logger.info(f"[LOG] [{timestamp}]   - {lang_code}: {prob:.4f}")
            
            logger.info(f"[LOG] [{timestamp}] ======================================")
            
            segments_list = list(segments)
            logger.info(f"[LOG] [{timestamp}] Number of segments: {len(segments_list)}")
            
            # Log segment details
            for idx, segment in enumerate(segments_list):
                seg_text = segment.text.strip()
                seg_start = getattr(segment, 'start', 0.0)
                seg_end = getattr(segment, 'end', 0.0)
                seg_avg_logprob = getattr(segment, 'avg_logprob', 0.0)
                seg_no_speech_prob = getattr(segment, 'no_speech_prob', 0.0)
                
                logger.info(f"[LOG] [{timestamp}] Segment {idx+1}:")
                logger.info(f"[LOG] [{timestamp}]   Text: '{seg_text}'")
                logger.info(f"[LOG] [{timestamp}]   Time: {seg_start:.2f}s - {seg_end:.2f}s")
                logger.info(f"[LOG] [{timestamp}]   Avg log prob: {seg_avg_logprob:.4f}")
                logger.info(f"[LOG] [{timestamp}]   No speech prob: {seg_no_speech_prob:.4f}")
            
            text = " ".join([s.text.strip() for s in segments_list]).strip()
            
            logger.info(f"[LOG] [{timestamp}] Raw transcription: '{text[:100]}{'...' if len(text) > 100 else ''}'")
            
            # Post-processing
            if language == Language.GUJARATI and text:
                original_text = text
                text = clean_gujarati_transcription(text)
                if original_text != text:
                    logger.info(f"[LOG] [{timestamp}] Cleaned transcription: '{text[:100]}{'...' if len(text) > 100 else ''}'")
            
            logger.info(f"[LOG] [{timestamp}] ✅ Transcription complete")
            return text
            
        except Exception as e:
            logger.error(f"[LOG] [{timestamp}] ❌ Transcription failed: {e}")
            # Simplified fallback
            try:
                logger.info(f"[LOG] [{timestamp}] Attempting fallback transcription")
                forced_lang = "gu" if language == Language.GUJARATI else "en"
                
                segments, info = model.transcribe(
                    path, 
                    language=forced_lang,
                    temperature=0.2,
                    beam_size=3
                )
                
                text = " ".join([s.text.strip() for s in segments]).strip()
                
                if language == Language.GUJARATI and text:
                    text = clean_gujarati_transcription(text)
                
                logger.info(f"[LOG] [{timestamp}] ✅ Fallback successful")
                return text
                
            except Exception as fallback_error:
                logger.error(f"[LOG] [{timestamp}] ❌ Fallback failed: {fallback_error}")
                return ""
        finally:
            try:
                os.remove(path)
            except Exception:
                pass
                
    except Exception as e:
        logger.error(f"[LOG] [{timestamp}] ❌ Base64 decode failed: {e}")
        return ""

def clean_gujarati_transcription(text: str) -> str:
    """Enhanced but careful cleaning for Gujarati transcription"""
    if not text:
        return text
    
    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Fix broken Gujarati characters
    text = re.sub(r'([ા-્])\s+([ા-્])', r'\1\2', text)
    
    # Common corrections (conservative)
    gujarati_corrections = {
        'તમારુ': 'તમારું',
        'શુ': 'શું',
    }
    
    for wrong, correct in gujarati_corrections.items():
        text = text.replace(wrong, correct)
    
    # Remove obvious Latin noise while preserving intentional English
    words = text.split()
    cleaned_words = []
    gujarati_word_count = sum(1 for w in words if any('\u0A80' <= c <= '\u0AFF' for c in w))
    total_words = len(words)
    
    # If mostly Gujarati (>50%), aggressively filter English
    is_mostly_gujarati = gujarati_word_count > total_words * 0.5
    
    for word in words:
        has_gujarati = any('\u0A80' <= char <= '\u0AFF' for char in word)
        
        if has_gujarati:
            cleaned_words.append(word)
        elif is_mostly_gujarati and len(word) > 4:
            # In mostly Gujarati context, long English words are likely noise
            logger.debug(f"Removing noise word: {word}")
        else:
            # Keep short words and words in mixed-language context
            cleaned_words.append(word)
    
    text = ' '.join(cleaned_words)
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def warm_up_models():
    """Pre-load both English and Gujarati models"""
    try:
        logger.info("Warming up STT models...")
        _get_model_for_language(Language.ENGLISH)
        _get_model_for_language(Language.GUJARATI)
        logger.info("✅ STT models warmed up successfully")
    except Exception as e:
        logger.error(f"Model warm-up failed: {e}")

def clear_model_cache():
    """Clear model cache to free memory"""
    global _model_cache
    _model_cache.clear()
    logger.info("STT model cache cleared")

def get_model_info(language: Language = Language.ENGLISH) -> dict:
    """Get information about the loaded model"""
    cache_key = "gujarati_enhanced" if language == Language.GUJARATI else f"english_{settings.WHISPER_MODEL_SIZE}"
    
    model_info = _model_cache.get(cache_key)
    if model_info:
        return {
            "language": language.value,
            "cache_key": cache_key,
            "model_loaded": True,
            "model_name": model_info['model_name'],
            "loaded_at": model_info['loaded_at']
        }
    else:
        return {
            "language": language.value,
            "cache_key": cache_key,
            "model_loaded": False,
            "recommended_model": "medium/small" if language == Language.GUJARATI else settings.WHISPER_MODEL_SIZE
        }