"""
Enhanced Language Support System with Improved Gujarati Integration
Handles language detection, switching, and multilingual responses
"""
import json
import re
import logging
from enum import Enum
from typing import Dict, List, Any, Optional
import google.generativeai as genai

from .config import settings

logger = logging.getLogger(__name__)

class Language(Enum):
    ENGLISH = "en"
    GUJARATI = "gu"

class LanguageSupport:
    """Enhanced language support with improved Gujarati handling"""
    
    def __init__(self):
        # Configure Gemini
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=self._get_language_system_prompt()
        )
        
        # Enhanced UI translations
        self.ui_translations = {
            "en": {
                "chat_title": "AI Assistant",
                "send": "Send",
                "microphone": "Mic",
                "listening": "Listening...",
                "processing": "Processing...",
                "waiting": "Waiting...",
                "error": "Error",
                "reset": "Reset",
                "submit": "Submit",
                "back_to_forms": "← Back to Forms",
                "status_idle": "Idle",
                "status_listening": "Listening",
                "status_waiting": "Waiting...",
                "status_error": "Error",
                "language_switch": "Switch to Gujarati",
                "skip_audio": "Skip",
                "ai_speaking": "AI Speaking...",
                "type_message": "Type your answer...",
                "are_you_there": "Are you there? Please respond.",
                "session_timeout": "Session timeout. Please restart the conversation.",
                "voice_commands": {
                    "stop": ["stop", "pause", "wait", "hold"],
                    "yes": ["yes", "correct", "right", "true"],
                    "no": ["no", "wrong", "false", "incorrect"]
                }
            },
            "gu": {
                "chat_title": "AI સહાયક",
                "send": "મોકલો",
                "microphone": "માઇક",
                "listening": "સાંભળી રહ્યું છે...",
                "processing": "પ્રક્રિયા થઈ રહી છે...",
                "waiting": "રાહ જોઈ રહ્યું છે...",
                "error": "ભૂલ",
                "reset": "ફરીથી શરૂ કરો",
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
        3. Handle transliterated Gujarati (English-written Gujarati)
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
        """Enhanced language switching detection"""
        if not text:
            return None
        
        text_lower = text.lower().strip()
        
        # Enhanced English to Gujarati switching patterns
        english_to_gujarati = [
            # Direct commands
            "change to gujarati", "switch to gujarati", "gujarati", "gujarati language",
            "speak gujarati", "talk in gujarati", "use gujarati", "gujarati please",
            "gujarati mein bolo", "gujarati me baat karo",
            
            # Natural variations
            "i want gujarati", "can you speak gujarati", "do you know gujarati",
            "speak in gujarati", "talk gujarati", "gujarati bolna", "gujarati bol",
            
            # Mixed patterns
            "gujarati ma bolo", "gujarati maa", "gujarati ma kaho", 
            "change language gujarati", "switch language gujarati",
            
            # Script mixing
            "ગુજરાતી", "ગુજરાતી બોલો", "ગુજરાતી માં બોલો"
        ]
        
        # Enhanced Gujarati to English switching patterns  
        gujarati_to_english = [
            # Gujarati commands
            "અંગ્રેજી", "અંગ્રેજી બોલો", "અંગ્રેજીમાં બોલો", "અંગ્રેજી ભાષા",
            "english", "english bolo", "english mein bolo", "english ma bolo",
            "change to english", "switch to english", "english please",
            "speak english", "talk in english", "use english",
            
            # Natural variations & phonetic
            "સ્વીચ ટુ ઇંગ્લિશ",
            "અંગ્રેજીમાં કહો", "અંગ્રેજી ભાષામાં", "english kaho", "english ma kaho",
            "મને અંગ્રેજી જોઈએ", "i want english", "can you speak english"
        ]
        
        # Check for language switching commands
        if current_language == Language.ENGLISH:
            # Check if user wants to switch to Gujarati
            for pattern in english_to_gujarati:
                if pattern in text_lower:
                    logger.info(f"Detected English→Gujarati switch command: '{text}'")
                    return Language.GUJARATI
        
        elif current_language == Language.GUJARATI:
            # Check if user wants to switch to English
            for pattern in gujarati_to_english:
                if pattern in text_lower:
                    logger.info(f"Detected Gujarati→English switch command: '{text}'")
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
            
            Return only the response text, no JSON formatting.
            """
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "max_output_tokens": 512
                }
            )
            
            if response and response.text:
                response_text = response.text.strip()
                
                # Clean any JSON artifacts
                response_text = re.sub(r'\{.*?\}', '', response_text, flags=re.DOTALL)
                response_text = re.sub(r'```.*?```', '', response_text, flags=re.DOTALL)
                response_text = response_text.strip()
                
                return {
                    "response": response_text,
                    "language": target_language.value,
                    "transliteration": None
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
    
    def generate_initial_greeting(self, form_title: str, form_description: str, language: Language, form_fields: List = None) -> str:
        """Generate contextual initial greeting with form overview"""
        try:
            # Provide form context in the prompt
            fields_info = ""
            if form_fields:
                field_names = [f.label for f in form_fields[:5]]  # First 5 fields
                if language == Language.GUJARATI:
                    fields_info = f"આ ફોર્મમાં આ માહિતી ભરવાની છે: {', '.join(field_names)}"
                    if len(form_fields) > 5:
                        fields_info += f" અને બીજી {len(form_fields) - 5} માહિતી."
                else:
                    fields_info = f"This form will collect: {', '.join(field_names)}"
                    if len(form_fields) > 5:
                        fields_info += f" and {len(form_fields) - 5} other details."
            
            if language == Language.GUJARATI:
                prompt = f"""
                એક ગુજરાતી ફોર્મ ભરવાનો સહાયક તરીકે, "{form_title}" નામના ફોર્મ માટે આવકારદાયક સંદેશ બનાવો.
                
                ફોર્મનું વર્ણન: {form_description}
                {fields_info}
                
                આવશ્યકતાઓ:
                - ગુજરાતીમાં ગરમજોશીથી સ્વાગત કરો
                - ફોર્મનો હેતુ સમજાવો
                - કેવી રીતે હું મદદ કરીશ તે જણાવો
                - સંક્ષિપ્ત અને મિત્રતાપૂર્ણ રાખો
                - કોઈ મેટા ટેક્સટ નહીં
                - સીધું શુભેચ્છા સંદેશથી શરૂ કરો
                
                માત્ર આવકારદાયક સંદેશ આપો, કોઈ વધારાનું નહીં.
                """
            else:
                prompt = f"""
                Create a welcoming greeting for the form "{form_title}" as a helpful form assistant.
                
                Form description: {form_description}
                {fields_info}
                
                Requirements:
                - Be warm and welcoming
                - Explain what the form is for
                - Explain how I'll help them fill it out
                - Keep it concise and friendly
                - NO meta text or references to "greeting message"
                - Start directly with the greeting
                
                Only provide the greeting message, nothing extra.
                """
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.5,
                    "top_p": 0.8,
                    "max_output_tokens": 150
                }
            )
            
            if response and response.text:
                greeting = response.text.strip()
                
                # Aggressive cleaning of JSON and meta text
                greeting = re.sub(r'\{.*?\}', '', greeting, flags=re.DOTALL).strip()
                greeting = re.sub(r'```.*?```', '', greeting, flags=re.DOTALL).strip()
                greeting = re.sub(r'^.*?[:।]\s*', '', greeting).strip()
                
                # Remove any remaining JSON-like patterns
                if greeting.startswith('{') or greeting.endswith('}'):
                    greeting = re.sub(r'[{}]', '', greeting).strip()
                
                return greeting if greeting else self._get_fallback_greeting(language, form_title)
            
        except Exception as e:
            logger.error(f"Failed to generate enhanced {language.value} greeting: {e}")
        
        return self._get_fallback_greeting(language, form_title)
    
    def _get_fallback_greeting(self, language: Language, form_title: str) -> str:
        """Get fallback greeting when generation fails"""
        if language == Language.GUJARATI:
            return f"નમસ્તે! હું તમારો AI સહાયક છું. હું તમને '{form_title}' ફોર્મ ભરવામાં મદદ કરીશ. મને પૂછો અને હું તમને આ ફોર્મ સરળતાથી ભરવામાં માર્ગદર્શન આપીશ. ચાલો શરૂ કરીએ!"
        else:
            return f"Hello! I'm your AI assistant here to help you fill out the '{form_title}' form. I'll guide you through each step and make it easy for you. Let's get started!"

# Global language support instance
language_support = LanguageSupport()