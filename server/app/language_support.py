"""
Gujarati Language Support Module
Handles bilingual conversation, transliteration, and UI text translation
"""
import re
import json
import logging
from typing import Dict, Any, Optional, List
from enum import Enum
import google.generativeai as genai
from .config import settings

logger = logging.getLogger(__name__)

# Configure Gemini for language support
genai.configure(api_key=settings.GEMINI_API_KEY)

class Language(str, Enum):
    ENGLISH = "en"
    GUJARATI = "gu"

class LanguageSupport:
    """Handles bilingual support for English and Gujarati"""
    
    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=self._get_language_system_prompt()
        )
        
        # UI translations
        self.ui_translations = {
            "en": {
                "form_title": "Form",
                "chat_title": "AI Assistant",
                "send": "Send",
                "microphone": "🎙️ Mic",
                "reset": "Reset Chat",
                "submit": "Submit",
                "back_to_forms": "← Back to Forms",
                "status_idle": "idle",
                "status_listening": "listening",
                "status_waiting": "waiting...",
                "status_error": "error",
                "language_switch": "Switch to Gujarati",
                "skip_audio": "Skip",
                "ai_speaking": "AI Speaking...",
                "type_message": "Type your answer...",
                "are_you_there": "Are you there? Please respond.",
                "session_timeout": "Session timeout. Please restart the conversation.",
                "voice_commands": {
                    "stop": ["stop", "pause", "wait", "hold"],
                    "yes": ["yes", "yeah", "yep", "correct", "right"],
                    "no": ["no", "nope", "wrong", "incorrect"]
                }
            },
            "gu": {
                "form_title": "ફોર્મ",
                "chat_title": "AI સહાયક",
                "send": "મોકલો",
                "microphone": "🎙️ માઇક",
                "reset": "ચેટ રીસેટ કરો",
                "submit": "સબમિટ કરો",
                "back_to_forms": "← ફોર્મ પર પાછા",
                "status_idle": "નિષ્ક્રિય",
                "status_listening": "સાંભળી રહ્યું છે",
                "status_waiting": "રાહ જોઈ રહ્યું છે...",
                "status_error": "ભૂલ",
                "language_switch": "અંગ્રેજીમાં બદલો",
                "skip_audio": "છોડો",
                "ai_speaking": "AI બોલી રહ્યું છે...",
                "type_message": "તમારો જવાબ લખો...",
                "are_you_there": "તમે ત્યાં છો? કૃપા કરીને જવાબ આપો.",
                "session_timeout": "સત્ર સમાપ્ત. કૃપા કરીને વાતચીત ફરીથી શરૂ કરો.",
                "voice_commands": {
                    "stop": ["બંધ કરો", "રોકો", "થોભો", "રાહ"],
                    "yes": ["હા", "બરાબર", "સાચું", "યોગ્ય"],
                    "no": ["ના", "ખોટું", "ખરાબ", "અયોગ્ય"]
                }
            }
        }
    
    def _get_language_system_prompt(self) -> str:
        """Get system prompt for language-aware AI"""
        return """
        You are a bilingual AI assistant that can communicate in both English and Gujarati.
        
        LANGUAGE CAPABILITIES:
        1. Generate responses in the requested language (English or Gujarati)
        2. Translate between English and Gujarati
        3. Handle transliteration (English-written Gujarati to proper Gujarati)
        4. Maintain conversation context across language switches
        
        TRANSLITERATION RULES:
        - Convert English-written Gujarati to proper Gujarati script
        - Examples: "Tamara naam shu che?" → "તમારું નામ શું છે?"
        - Handle common patterns and phonetic mappings
        
        RESPONSE GUIDELINES:
        1. Always respond in the language requested
        2. Keep responses natural and conversational
        3. Maintain cultural context appropriate for the language
        4. For form fields, ask questions naturally in the target language
        
        RESPONSE FORMAT (JSON):
        {
          "response": "Your response in requested language",
          "language": "en" | "gu",
          "transliteration": "Original transliterated if applicable",
          "field_question": "Natural field question in target language"
        }
        """
    
    def get_ui_text(self, key: str, language: Language = Language.ENGLISH) -> str:
        """Get UI text in specified language"""
        return self.ui_translations.get(language.value, {}).get(key, key)
    
    def get_voice_commands(self, language: Language = Language.ENGLISH) -> Dict[str, List[str]]:
        """Get voice commands for specified language"""
        return self.ui_translations.get(language.value, {}).get("voice_commands", {})
    
    def detect_language_switch_command(self, text: str, current_language: Language) -> Optional[Language]:
        """Detect if user wants to switch language"""
        text_lower = text.lower().strip()
        
        if current_language == Language.ENGLISH:
            gujarati_triggers = ["gujarati", "switch to gujarati", "change to gujarati", "gujaratima"]
            if any(trigger in text_lower for trigger in gujarati_triggers):
                return Language.GUJARATI
        else:
            english_triggers = ["english", "switch to english", "change to english", "angreji", "અંગ્રેજી"]
            if any(trigger in text_lower for trigger in english_triggers):
                return Language.ENGLISH
        
        return None
    
    def transliterate_to_gujarati(self, english_text: str) -> str:
        """Convert English-written Gujarati to proper Gujarati script"""
        try:
            prompt = f"""
            Convert the following English-written Gujarati text to proper Gujarati script.
            Handle common transliteration patterns and phonetic mappings.
            
            Input: {english_text}
            
            Only return the Gujarati text, no explanations.
            """
            
            response = self.model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
            return english_text
        except Exception as e:
            logger.error(f"Transliteration failed: {e}")
            return english_text
    
    def generate_language_specific_response(self, 
                                         user_input: str, 
                                         context: Dict[str, Any], 
                                         target_language: Language,
                                         field_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate AI response in specified language"""
        try:
            # Handle transliteration if needed
            processed_input = user_input
            if target_language == Language.GUJARATI and self._is_transliterated_gujarati(user_input):
                processed_input = self.transliterate_to_gujarati(user_input)
            
            prompt = f"""
            Generate a natural conversational response in {target_language.value} language.
            
            User input: {user_input}
            Processed input: {processed_input}
            Context: {json.dumps(context, indent=2)}
            Current field: {json.dumps(field_info, indent=2) if field_info else "None"}
            Target language: {"Gujarati" if target_language == Language.GUJARATI else "English"}
            
            Guidelines:
            1. Respond naturally in the target language
            2. If asking about a form field, phrase it conversationally
            3. Maintain friendly, helpful tone
            4. Use culturally appropriate expressions
            5. For Gujarati, use proper script and common phrases
            
            Return JSON format with the response.
            """
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "max_output_tokens": 1024
                }
            )
            
            if response and response.text:
                try:
                    parsed = json.loads(response.text.strip())
                    return parsed
                except json.JSONDecodeError:
                    # Fallback if JSON parsing fails
                    return {
                        "response": response.text.strip(),
                        "language": target_language.value,
                        "transliteration": processed_input if processed_input != user_input else None
                    }
            
            # Fallback response
            fallback_text = self.get_ui_text("are_you_there", target_language)
            return {
                "response": fallback_text,
                "language": target_language.value,
                "transliteration": None
            }
            
        except Exception as e:
            logger.error(f"Language response generation failed: {e}")
            fallback_text = self.get_ui_text("are_you_there", target_language)
            return {
                "response": fallback_text,
                "language": target_language.value,
                "error": str(e)
            }
    
    def _is_transliterated_gujarati(self, text: str) -> bool:
        """Detect if text is likely English-written Gujarati"""
        # Common Gujarati words written in English
        gujarati_indicators = [
            "naam", "shu", "che", "tamara", "mara", "aa", "ke", "ma", "ne",
            "hoya", "chho", "karva", "java", "avva", "pela", "pachhi",
            "sathe", "vina", "mate", "thi", "ni", "no", "na", "pan"
        ]
        
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in gujarati_indicators)
    
    def generate_initial_greeting(self, 
                                form_title: str, 
                                form_description: str, 
                                language: Language = Language.ENGLISH) -> str:
        """Generate initial greeting with form context"""
        try:
            language_name = "Gujarati" if language == Language.GUJARATI else "English"
            
            prompt = f"""
            Generate a warm, welcoming greeting message in {language_name} for a voice-enabled form filling experience.
            
            Form Title: {form_title}
            Form Description: {form_description}
            
            The greeting should:
            1. Welcome the user warmly
            2. Explain this is a voice-enabled form assistant
            3. Mention they can speak naturally or type
            4. Briefly explain the form's purpose
            5. Mention they can switch languages anytime
            6. Be encouraging and helpful
            7. End by asking for the first piece of information
            
            Keep it conversational and friendly, not robotic.
            {"Use proper Gujarati script and cultural expressions" if language == Language.GUJARATI else "Use natural English expressions"}
            
            Return only the greeting text, no JSON.
            """
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.4,
                    "top_p": 0.9,
                    "max_output_tokens": 512
                }
            )
            
            if response and response.text:
                return response.text.strip()
            
            # Fallback greeting
            if language == Language.GUJARATI:
                return f"નમસ્તે! આ {form_title} માટે AI સહાયક છે. તમે બોલી શકો છો અથવા લખી શકો છો. ચાલો શરૂ કરીએ!"
            else:
                return f"Hello! I'm your AI assistant for {form_title}. You can speak naturally or type your responses. Let's get started!"
                
        except Exception as e:
            logger.error(f"Greeting generation failed: {e}")
            if language == Language.GUJARATI:
                return f"નમસ્તે! {form_title} માટે AI સહાયક. ચાલો શરૂ કરીએ!"
            else:
                return f"Hello! Welcome to {form_title}. Let's begin!"

# Global language support instance
language_support = LanguageSupport()