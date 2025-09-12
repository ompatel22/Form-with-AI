"""
Google Text-to-Speech Service for Enhanced Multilingual Support
Replaces pyttsx3 with cloud-based TTS for superior Gujarati language support
"""
import os
import asyncio
import base64
import tempfile
import logging
from typing import Optional, Dict, Any

# NOTE: These imports are based on your original file.
from .language_support import Language
from .config import settings
from google.api_core.exceptions import PermissionDenied
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import texttospeech
from google.cloud.texttospeech import AudioConfig, AudioEncoding, SynthesisInput, VoiceSelectionParams, SsmlVoiceGender

logger = logging.getLogger(__name__)

class GoogleTTSService:
    """Google Cloud Text-to-Speech service with Gujarati support"""
    
    def __init__(self, credentials_path: Optional[str] = None):
        """Initialize Google TTS client"""
        try:
            if credentials_path and os.path.exists(credentials_path):
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
            
            self.client = texttospeech.TextToSpeechClient()
            self.logger = logging.getLogger(__name__)
            self.logger.info("✅ Google TTS client initialized successfully")
            
            # --- START OF CHANGE ---
            # Re-introduced English with premium Studio voices and kept high-quality Gujarati WaveNet voices.
            self.voice_configs = {
                Language.ENGLISH: {
                    "language_code": "en-US",
                    "voices": {
                        "MALE": "en-US-Studio-M",
                        "FEMALE": "en-US-Studio-O",
                        "NEUTRAL": "en-US-Studio-O" # Default neutral to the female Studio voice
                    },
                    "voice_type": "Studio"
                },
                Language.GUJARATI: {
                    "language_code": "gu-IN",
                    "voices": {
                        "MALE": "gu-IN-Wavenet-B",
                        "FEMALE": "gu-IN-Wavenet-A",
                        "NEUTRAL": "gu-IN-Wavenet-A" # Default neutral to the female WaveNet voice
                    },
                    "voice_type": "WaveNet"
                }
            }
            # --- END OF CHANGE ---
            
        except DefaultCredentialsError as e:
            logger.error(f"❌ AUTHENTICATION FAILED: {e}")
            raise
        except PermissionDenied as e:
            logger.error(f"❌ PERMISSION DENIED: {e}")
            raise
        except Exception:
            logger.exception("❌ An unexpected error occurred while initializing the Google TTS client.")
            raise
    
    async def synthesize_speech(
        self, 
        text: str, 
        language: Language = Language.ENGLISH,
        gender: str = "NEUTRAL"
    ) -> bytes:
        """Synthesize speech with language-specific optimizations"""
        try:
            if not text or not text.strip():
                return b""
            
            # --- START OF CHANGE ---
            # Restored logic to handle both English and Gujarati
            config = self.voice_configs.get(language, self.voice_configs[Language.ENGLISH])
            language_code = config["language_code"]
            voice_name = config["voices"].get(gender.upper(), config["voices"]["NEUTRAL"])
            # --- END OF CHANGE ---
            
            synthesis_input = SynthesisInput(text=text.strip())
            
            voice_params_args = {
                "language_code": language_code,
                "name": voice_name
            }
            if gender.upper() in ["MALE", "FEMALE"]:
                voice_params_args["ssml_gender"] = getattr(SsmlVoiceGender, gender.upper())

            voice_params = VoiceSelectionParams(**voice_params_args)
            
            audio_config = AudioConfig(
                audio_encoding=AudioEncoding.MP3,
                sample_rate_hertz=24000
            )
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.synthesize_speech(
                    input=synthesis_input, voice=voice_params, audio_config=audio_config
                )
            )
            
            self.logger.info(f"✅ Successfully synthesized {len(text)} characters in {language.value}")
            return response.audio_content
            
        except Exception:
            self.logger.exception(f"❌ Google TTS synthesis failed for language '{language.value}'")
            return b""
    
    async def get_supported_voices(self, language: Optional[Language] = None) -> Dict[str, Any]:
        return self.voice_configs
    
    def to_base64_wav(self, audio_content: bytes) -> str:
        if not audio_content: return ""
        try: return base64.b64encode(audio_content).decode("utf-8")
        except Exception as e:
            self.logger.error(f"Failed to encode audio to base64: {e}")
            return ""
    
    async def test_synthesis(self) -> bool:
        try:
            # Restored test for both languages
            english_audio = await self.synthesize_speech("Hello, testing Google TTS.", Language.ENGLISH)
            english_ok = len(english_audio) > 0
            
            gujarati_audio = await self.synthesize_speech("નમસ્તે, ગૂગલ TTS ટેસ્ટ", Language.GUJARATI)
            gujarati_ok = len(gujarati_audio) > 0

            self.logger.info(f"TTS Test Results - English: {english_ok}, Gujarati: {gujarati_ok}")
            return english_ok and gujarati_ok
        except Exception as e:
            self.logger.error(f"TTS test failed: {e}")
            return False

# Fallback TTS using pyttsx3 for when Google TTS is unavailable
class FallbackTTSService:
    """Fallback TTS service using pyttsx3"""
    
    def __init__(self):
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", 150)
            self.engine.setProperty("volume", 0.9)
            self.available = True
            logger.info("✅ Fallback pyttsx3 TTS initialized")
        except Exception as e:
            logger.warning(f"⚠️ Fallback TTS not available: {e}")
            self.available = False
    
    async def synthesize_speech(
        self, 
        text: str, 
        language: Language = Language.ENGLISH,
        gender: str = "NEUTRAL"
    ) -> bytes:
        if not self.available or not text or not text.strip(): return b""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                temp_path = temp_file.name
            await asyncio.get_event_loop().run_in_executor(None, self._generate_speech, text.strip(), temp_path)
            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                with open(temp_path, "rb") as f: audio_data = f.read()
                os.remove(temp_path)
                logger.info(f"✅ Fallback TTS generated {len(audio_data)} bytes")
                return audio_data
            else:
                logger.warning("Fallback TTS generated empty file")
                return b""
        except Exception as e:
            logger.error(f"Fallback TTS synthesis failed: {e}")
            return b""
    
    def _generate_speech(self, text: str, output_path: str):
        try:
            self.engine.save_to_file(text, output_path)
            self.engine.runAndWait()
        except Exception as e:
            logger.error(f"pyttsx3 generation failed: {e}")

# Unified TTS Service with Google Cloud primary and pyttsx3 fallback
class UnifiedTTSService:
    """Unified TTS service with Google Cloud TTS and pyttsx3 fallback"""
    
    def __init__(self, google_credentials_path: Optional[str] = None):
        self.google_tts = None
        self.fallback_tts = None
        
        try:
            self.google_tts = GoogleTTSService(google_credentials_path)
            logger.info("✅ Google TTS service available")
        except Exception as e:
            logger.warning(f"⚠️ Google TTS not available. Reason: {e}")
        
        try:
            self.fallback_tts = FallbackTTSService()
        except Exception as e:
            logger.warning(f"⚠️ Fallback TTS initialization failed: {e}")
    
    async def synthesize_speech(
        self, 
        text: str, 
        language: Language = Language.ENGLISH,
        gender: str = "NEUTRAL"
    ) -> bytes:
        if not text or not text.strip(): return b""
        if self.google_tts:
            try:
                audio_content = await self.google_tts.synthesize_speech(text, language, gender)
                if audio_content:
                    logger.info(f"✅ Used Google TTS for {language.value}")
                    return audio_content
            except Exception as e:
                logger.warning(f"Google TTS failed, trying fallback: {e}")
        
        if self.fallback_tts and self.fallback_tts.available:
            try:
                audio_content = await self.fallback_tts.synthesize_speech(text, language, gender)
                if audio_content:
                    logger.info(f"✅ Used fallback TTS for {language.value}")
                    return audio_content
            except Exception as e:
                logger.error(f"Fallback TTS also failed: {e}")
        
        logger.error("❌ All TTS services failed")
        return b""
    
    def to_base64_wav(self, audio_content: bytes) -> str:
        if not audio_content: return ""
        try: return base64.b64encode(audio_content).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to encode audio to base64: {e}")
            return ""
    
    async def health_check(self) -> Dict[str, Any]:
        health_status = {"google_tts_available": False, "fallback_tts_available": False, "overall_status": "unhealthy"}
        if self.google_tts:
            try:
                health_status["google_tts_available"] = await self.google_tts.test_synthesis()
            except Exception as e:
                logger.error(f"Google TTS health check failed: {e}")
        if self.fallback_tts and self.fallback_tts.available:
            try:
                test_audio = await self.fallback_tts.synthesize_speech("Health check")
                health_status["fallback_tts_available"] = len(test_audio) > 0
            except Exception as e:
                logger.error(f"Fallback TTS health check failed: {e}")
        if health_status["google_tts_available"] or health_status["fallback_tts_available"]:
            health_status["overall_status"] = "healthy"
        return health_status

# Global unified TTS service instance
unified_tts_service = UnifiedTTSService()