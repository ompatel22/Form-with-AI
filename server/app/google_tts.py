import logging
import os
import asyncio
import base64
from typing import Optional, Dict, Any
from google.cloud import texttospeech
from google.cloud.texttospeech import AudioConfig, AudioEncoding, SynthesisInput, VoiceSelectionParams, SsmlVoiceGender
from .language_support import Language
from .config import settings

# Initialize logger before the class definition
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)  # Set default logging level

class GoogleTTSService:
    """Google Cloud Text-to-Speech service with Gujarati support"""
    
    def __init__(self, credentials_path: Optional[str] = None):
        """Initialize Google TTS client"""
        try:
            # Set credentials if provided
            if credentials_path and os.path.exists(credentials_path):
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
            
            self.client = texttospeech.TextToSpeechClient()
            
            # Now logging works because logger is initialized before client creation
            logger.info("✅ Google TTS client initialized successfully")
            
            # Language-specific voice configurations
            self.voice_configs = {
                Language.ENGLISH: {
                    "language_code": "en-US",
                    "voices": {
                        "MALE": "en-US-Neural2-D",
                        "FEMALE": "en-US-Neural2-F", 
                        "NEUTRAL": "en-US-Neural2-C"
                    },
                    "voice_type": "Neural2"
                },
                Language.GUJARATI: {
                    "language_code": "gu-IN",
                    "voices": {
                        "MALE": "gu-IN-Standard-B",
                        "FEMALE": "gu-IN-Standard-A",
                        "NEUTRAL": "gu-IN-Standard-A"
                    },
                    "voice_type": "Standard"
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Google TTS client: {e}")
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
            
            # Get language configuration
            config = self.voice_configs.get(language, self.voice_configs[Language.ENGLISH])
            language_code = config["language_code"]
            voice_name = config["voices"].get(gender.upper(), config["voices"]["NEUTRAL"])
            
            # Create synthesis input
            synthesis_input = SynthesisInput(text=text.strip())
            
            # Configure voice parameters
            voice_params = VoiceSelectionParams(
                language_code=language_code,
                name=voice_name,
                ssml_gender=getattr(SsmlVoiceGender, gender.upper())
            )
            
            # Configure audio output - optimized for web delivery
            audio_config = AudioConfig(
                audio_encoding=AudioEncoding.MP3,
                sample_rate_hertz=24000,
                speaking_rate=1.0,  # Normal speed
                pitch=0.0,          # Normal pitch
                volume_gain_db=0.0  # Normal volume
            )
            
            # Perform synthesis asynchronously
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                self.client.synthesize_speech,
                synthesis_input,
                voice_params,
                audio_config
            )
            
            logger.info(f"✅ Successfully synthesized {len(text)} characters in {language.value}")
            return response.audio_content
            
        except Exception as e:
            logger.error(f"❌ Google TTS synthesis failed for {language.value}: {e}")
            # Return empty bytes instead of raising exception to prevent breaking the flow
            return b""
    
    async def get_supported_voices(self, language: Optional[Language] = None) -> Dict[str, Any]:
        """Get supported voices for language(s)"""
        try:
            if language:
                config = self.voice_configs.get(language)
                if config:
                    return {
                        "language": language.value,
                        "language_code": config["language_code"],
                        "voices": config["voices"],
                        "voice_type": config["voice_type"]
                    }
            else:
                # Return all supported languages
                return {
                    "supported_languages": {
                        lang.value: {
                            "language_code": config["language_code"],
                            "voices": config["voices"],
                            "voice_type": config["voice_type"]
                        }
                        for lang, config in self.voice_configs.items()
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get supported voices: {e}")
            return {}
    
    def to_base64_wav(self, audio_content: bytes) -> str:
        """Convert MP3 audio content to base64 string"""
        if not audio_content:
            return ""
        
        try:
            return base64.b64encode(audio_content).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to encode audio to base64: {e}")
            return ""
    
    async def test_synthesis(self) -> bool:
        """Test TTS functionality with both languages"""
        try:
            # Test English
            english_audio = await self.synthesize_speech("Hello, testing Google TTS", Language.ENGLISH)
            english_ok = len(english_audio) > 0
            
            # Test Gujarati
            gujarati_audio = await self.synthesize_speech("નમસ્તે, ગૂગલ TTS ટેસ્ટ", Language.GUJARATI)
            gujarati_ok = len(gujarati_audio) > 0
            
            logger.info(f"TTS Test Results - English: {english_ok}, Gujarati: {gujarati_ok}")
            return english_ok and gujarati_ok
            
        except Exception as e:
            logger.error(f"TTS test failed: {e}")
            return False