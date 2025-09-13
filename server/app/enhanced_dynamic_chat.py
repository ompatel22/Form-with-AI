"""
Enhanced Dynamic Conversational Form Handler with Multilingual Support
Integrates all new features: Gujarati support, enhanced date parsing, 
voice interruption, and silence management
"""
import json
import re
import time
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import google.generativeai as genai
import logging

from .form_builder import FormSchema, FormField, FieldType, form_store
from .validators import validate_value, clean_speech_input
from .memory import SessionState, FieldStatus, MessageRole
from .config import settings
from .language_support import Language, language_support
from .enhanced_date_parser import enhanced_date_parser
from .silence_manager import silence_manager
from .voice_interruption import voice_interruption_handler, InterruptionType

logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)

class ValidationResult:
    """Structured validation result"""
    def __init__(self, is_valid: bool, cleaned_value: str, error_message: str = "", suggestion: str = ""):
        self.is_valid = is_valid
        self.cleaned_value = cleaned_value
        self.error_message = error_message
        self.suggestion = suggestion

class EnhancedValidator:
    """Enhanced field validation with multilingual support and better date parsing"""
    
    @staticmethod
    def validate_full_name(value: str, language: Language = Language.ENGLISH) -> ValidationResult:
        if not value or not value.strip():
            error_msg = "નામ ખાલી હોઈ શકતું નથી" if language == Language.GUJARATI else "Name cannot be empty"
            suggestion = "કૃપા કરીને તમારું પૂરું નામ કહો" if language == Language.GUJARATI else "Please tell me your full name"
            return ValidationResult(False, "", error_msg, suggestion)
        
        # Enhanced name extraction and cleaning
        cleaned = value.strip()
        
        # Remove common speech-to-text artifacts
        artifacts = ["my name is", "i am", "call me", "it's"] if language == Language.ENGLISH else ["મારું નામ", "હું છું", "મને કહો"]
        for artifact in artifacts:
            cleaned = re.sub(rf'{re.escape(artifact)}\s*', '', cleaned, flags=re.IGNORECASE)
        
        # Extract name pattern - allow letters, spaces, hyphens, apostrophes, and unicode characters
        name_match = re.search(r"[A-Za-z\u0A80-\u0AFF](?:[A-Za-z\u0A80-\u0AFF\s\-\'\.])*[A-Za-z\u0A80-\u0AFF]", cleaned)
        if name_match:
            cleaned = name_match.group(0).strip()
            cleaned = re.sub(r'\s+', ' ', cleaned)
            
            if len(cleaned) >= 2:
                # Proper case formatting for English, keep original for Gujarati
                if language == Language.ENGLISH and not re.search(r'[\u0A80-\u0AFF]', cleaned):
                    cleaned = ' '.join(word.capitalize() for word in cleaned.split())
                return ValidationResult(True, cleaned, "", "")
        
        error_msg = "કૃપા કરીને માન્ય નામ આપો" if language == Language.GUJARATI else "Please provide a valid name"
        suggestion = "માત્ર અક્ષરો, જગ્યાઓ અને હાઇફનનો ઉપયોગ કરો" if language == Language.GUJARATI else "Use only letters, spaces, and hyphens"
        return ValidationResult(False, "", error_msg, suggestion)
    
    @staticmethod
    def validate_email(value: str, language: Language = Language.ENGLISH) -> ValidationResult:
        if not value or not value.strip():
            error_msg = "ઈમેઇલ ખાલી હોઈ શકતું નથી" if language == Language.GUJARATI else "Email cannot be empty"
            suggestion = "કૃપા કરીને તમારું ઈમેઇલ એડ્રેસ આપો" if language == Language.GUJARATI else "Please provide your email address"
            return ValidationResult(False, "", error_msg, suggestion)
        
        # SUPER AGGRESSIVE email cleaning for speech-to-text
        cleaned = value.lower().strip()
        
        # Handle "at the rate" patterns aggressively
        cleaned = re.sub(r'\bat\s*the\s*rate\b', '@', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bat\s*rate\b', '@', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bthe\s*rate\b', '@', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'rate\s*([a-zA-Z])', r'@\1', cleaned, flags=re.IGNORECASE)
        
        # Handle various speech patterns
        cleaned = re.sub(r'(\w+)\s*at\s*([a-zA-Z]+\.com)', r'\1@\2', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'(\w+)\s*(\d+)\s*at\s*([a-zA-Z]+\.com)', r'\1\2@\3', cleaned, flags=re.IGNORECASE)
        
        # Handle dot patterns
        cleaned = re.sub(r'\bdot\s*com\b', '.com', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bdot\s*gmail\s*com\b', '.gmail.com', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bgmail\s*dot\s*com\b', 'gmail.com', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bdot\b', '.', cleaned, flags=re.IGNORECASE)
        
        # Handle concatenated patterns without @
        if '@' not in cleaned:
            patterns = [
                (r'(\w+\d*)gmail', r'\1@gmail'),
                (r'(\w+\d*)yahoo', r'\1@yahoo'),
                (r'(\w+\d*)hotmail', r'\1@hotmail'),
                (r'(\w+\d*)outlook', r'\1@outlook'),
            ]
            for pattern, replacement in patterns:
                cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        
        # Fix domain completions
        cleaned = re.sub(r'@gmail(?!\.com)', '@gmail.com', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'@yahoo(?!\.com)', '@yahoo.com', cleaned, flags=re.IGNORECASE)
        
        # Remove spaces
        cleaned = re.sub(r'\s+', '', cleaned)
        
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, cleaned):
            if '@' not in cleaned:
                error_msg = "ઈમેઇલમાં @ હોવું જ જોઈએ" if language == Language.GUJARATI else "Email must contain @ symbol"
                suggestion = "કૃપા કરીને સંપૂર્ણ ઈમેઇલ આપો જેવું કે: name@gmail.com" if language == Language.GUJARATI else "Please provide complete email like: name@gmail.com"
            elif '.' not in cleaned.split('@')[1] if '@' in cleaned else False:
                error_msg = "ઈમેઇલમાં ડોમેઇન હોવું જ જોઈએ" if language == Language.GUJARATI else "Email must contain domain"
                suggestion = "આ ફોર્મેટ વાપરો: name@example.com" if language == Language.GUJARATI else "Please use format: name@example.com"
            else:
                error_msg = "અમાન્ય ઈમેઇલ ફોર્મેટ" if language == Language.GUJARATI else "Invalid email format"
                suggestion = "આ ફોર્મેટ વાપરો: name@example.com" if language == Language.GUJARATI else "Please use format: name@example.com"
            return ValidationResult(False, "", error_msg, suggestion)
        
        return ValidationResult(True, cleaned, "", "")
    
    @staticmethod
    def validate_phone(value: str, language: Language = Language.ENGLISH) -> ValidationResult:
        if not value or not value.strip():
            error_msg = "ફોન નમ્બર ખાલી હોઈ શકતું નથી" if language == Language.GUJARATI else "Phone number cannot be empty"
            suggestion = "કૃપા કરીને તમારો ફોન નમ્બર આપો" if language == Language.GUJARATI else "Please provide your phone number"
            return ValidationResult(False, "", error_msg, suggestion)
        
        # Handle "3 times 5" -> "555", "2 times 3" -> "33"
        cleaned = value.strip()
        repeat_pattern = r'(\d+)\s*times?\s*(\d+)'
        def expand_repeats(match):
            num = match.group(1)
            times = int(match.group(2))
            return num * times
        
        cleaned = re.sub(repeat_pattern, expand_repeats, cleaned)
        
        # Extract digits only
        digits = re.sub(r'\D', '', cleaned)
        
        if len(digits) < 7:
            error_msg = "ફોન નમ્બર ખૂબ ટૂંકો છે" if language == Language.GUJARATI else "Phone number too short"
            suggestion = "કૃપા કરીને ઓછામાં ઓછા 7 અંકો આપો" if language == Language.GUJARATI else "Please provide at least 7 digits"
            return ValidationResult(False, "", error_msg, suggestion)
        
        if len(digits) > 15:
            error_msg = "ફોન નમ્બર ખૂબ લાંબો છે" if language == Language.GUJARATI else "Phone number too long"
            suggestion = "કૃપા કરીને માન્ય ફોન નમ્બર આપો" if language == Language.GUJARATI else "Please provide a valid phone number"
            return ValidationResult(False, "", error_msg, suggestion)
        
        # Format for display
        if len(digits) == 10:
            formatted = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            formatted = f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        else:
            formatted = f"+{digits}"
        
        return ValidationResult(True, formatted, "", "")
    
    @staticmethod
    def validate_date(value: str, language: Language = Language.ENGLISH) -> ValidationResult:
        """Enhanced date validation using the new date parser"""
        if not value or not value.strip():
            error_msg = "તારીખ ખાલી હોઈ શકતી નથી" if language == Language.GUJARATI else "Date cannot be empty"
            suggestion = "કૃપા કરીને તારીખ આપો, જેમ કે 'જાન્યુઆરી 1, 2000' અથવા '01/01/2000'" if language == Language.GUJARATI else "Please provide the date, e.g., 'January 1, 2000' or '01/01/2000'"
            return ValidationResult(False, "", error_msg, suggestion)
        
        # Use enhanced date parser
        formatted_date = enhanced_date_parser.parse_and_format(value.strip())
        
        if formatted_date:
            return ValidationResult(True, formatted_date, "", "")
        else:
            error_msg = "અમાન્ય તારીખ ફોર્મેટ" if language == Language.GUJARATI else "Invalid date format"
            suggestion = ("કૃપા કરીને આ ફોર્મેટ વાપરો: 'જાન્યુઆરી 1, 2000', '01/01/2000', અથવા '22મી ડિસેમ્બર 2004'" 
                         if language == Language.GUJARATI else 
                         "Please use a format like 'January 1, 2000', '01/01/2000', 'Jan 1 2000', or '22nd December 2004'")
            return ValidationResult(False, "", error_msg, suggestion)

class EnhancedDynamicFormConversation:
    """Enhanced conversational form handler with multilingual support"""
    
    def __init__(self, form_id: str, session_state: SessionState):
        self.form_id = form_id
        self.session = session_state
        self.form_schema = form_store.get_form(form_id)
        
        if not self.form_schema:
            raise ValueError(f"Form {form_id} not found")
        
        # Enhanced session management
        self._initialize_form_session()
        
        # Language state - Load from session to be authoritative
        form_context_key = self._get_form_context_key()
        session_lang_code = self.session.context.get(form_context_key, {}).get("language", "en")
        self.current_language = Language(session_lang_code)
        
        # Initialize LLM with enhanced system prompt
        self.model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=self._get_enhanced_system_prompt()
        )
        
        self.validator = EnhancedValidator()
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.5
        
        # Initialize silence monitoring
        silence_manager.start_session(
            session_state.session_id, 
            self.current_language,
            None
        )
    
    def _initialize_form_session(self):
        """Initialize form-specific session context"""
        form_context_key = f"form_{self.form_id}"
        
        if form_context_key not in self.session.context:
            self.session.context[form_context_key] = {
                "form_id": self.form_id,
                "form_title": self.form_schema.title,
                "conversation_started": False,
                "fields_initialized": False,
                "current_field_index": 0,
                "user_name": None,
                "conversation_style": "friendly",
                "language": "en",
                "greeting_sent": False
            }
        
        # Initialize form fields if not done
        if not self.session.context[form_context_key].get("fields_initialized"):
            for field in self.form_schema.fields:
                field_key = f"{form_context_key}_{field.name}"
                if field_key not in self.session.fields:
                    self.session.update_field(field_key, None, FieldStatus.PENDING)
            self.session.context[form_context_key]["fields_initialized"] = True
    
    def _get_form_context_key(self) -> str:
        return f"form_{self.form_id}"
    
    def _get_field_key(self, field_name: str) -> str:
        return f"{self._get_form_context_key()}_{field_name}"
    
    def _get_enhanced_system_prompt(self) -> str:
        """Get enhanced multilingual system prompt"""
        fields_info = []
        for field in self.form_schema.fields:
            field_info = f"- {field.name} ({field.type.value}): {field.label}"
            if field.validation.required:
                field_info += " [REQUIRED]"
            if field.description:
                field_info += f" - {field.description}"
            if field.options:
                field_info += f" - Options: {', '.join(field.options)}"
            fields_info.append(field_info)
        
        return f"""
        You are an intelligent, multilingual conversational assistant helping users fill out the form: "{self.form_schema.title}".
        
        SUPPORTED LANGUAGES: English and Gujarati
        
        FORM FIELDS TO COLLECT:
        {chr(10).join(fields_info)}
        
        PERSONALITY & STYLE:
        - Natural, conversational, and personable (not robotic)
        - Adapt to user's preferred language (English or Gujarati)
        - Use culturally appropriate expressions for each language
        - Show empathy and understanding
        - Keep responses concise but warm
        - Celebrate progress and completion
        
        MULTILINGUAL CAPABILITIES:
        - Detect language preference from user input
        - Generate responses in requested language
        - Handle transliterated Gujarati (English-written Gujarati)
        - Switch languages seamlessly when requested
        - Maintain conversation context across language switches
        
        FIELD PROCESSING RULES:
        1. ENHANCED DATE PARSING: Accept natural formats like "22nd December 2004", "December 22nd 2004"
        2. STRICT CHECKBOX VALIDATION: Only allow exact matches from provided options
        3. VOICE INTERRUPTION: Respect voice commands like "stop", "pause", "બંધ કરો", "રોકો"
        4. MULTILINGUAL VALIDATION: Provide error messages in user's preferred language
        5. **FORM DATA MUST ALWAYS BE IN ENGLISH, EVEN IF USER SPEAKS GUJARATI**
        
        CONVERSATION MANAGEMENT:
        - Start with contextual greeting explaining the form
        - Ask for ONE field at a time
        - Handle corrections and language switches immediately
        - Support both required and optional fields
        - Provide helpful error messages in appropriate language
        
        RESPONSE FORMAT (JSON ONLY):
        {{
          "action": "ask" | "set" | "done" | "clarify" | "correct" | "remove" | "language_switch",
          "updates": {{"field_name": "cleaned_value or null if removed"}},
          "ask": "Your natural response in appropriate language",
          "field_focus": "current_field_name",
          "tone": "friendly" | "encouraging" | "apologetic" | "professional",
          "language": "en" | "gu",
          "greeting": "Initial greeting if starting conversation"
        }}
        
        Remember: Be conversational, culturally aware, and make the form-filling experience pleasant in both languages!
        """
    
    def set_language(self, language: Language):
        """Set conversation language"""
        self.current_language = language
        form_context_key = self._get_form_context_key()
        if form_context_key in self.session.context:
            self.session.context[form_context_key]["language"] = language.value
        
        # Update silence manager language
        silence_manager.update_language(self.session.session_id, language)
        
        logger.info(f"Language set to {language.value} for session {self.session.session_id}")
    
    def get_next_field(self) -> Optional[FormField]:
        """Get the next field that needs to be filled"""
        sorted_fields = sorted(self.form_schema.fields, key=lambda f: f.order)
        
        for field in sorted_fields:
            field_key = self._get_field_key(field.name)
            field_info = self.session.fields.get(field_key, None)
            
            if not field_info or field_info.status in [FieldStatus.PENDING, FieldStatus.INVALID]:
                return field
        
        return None
    
    def get_next_required_field(self) -> Optional[FormField]:
        """Get the next required field that needs to be filled"""
        sorted_fields = sorted(self.form_schema.fields, key=lambda f: f.order)
        
        for field in sorted_fields:
            if field.validation.required:
                field_key = self._get_field_key(field.name)
                field_info = self.session.fields.get(field_key, None)
                
                if not field_info or field_info.status in [FieldStatus.PENDING, FieldStatus.INVALID]:
                    return field
        
        return None
    
    def process_user_input(self, user_text: str) -> Dict[str, Any]:
        """Enhanced user input processing with multilingual support"""
        form_context_key = self._get_form_context_key()
        
        # Update activity for silence manager
        silence_manager.update_activity(self.session.session_id)
        
        # Check for language switch command first with improved detection
        new_language = language_support.detect_language_switch_command(user_text, self.current_language)
        if new_language:
            self.set_language(new_language)
            
            # Generate appropriate language switch confirmation
            if new_language == Language.GUJARATI:
                switch_message = "હા! હવે હું ગુજરાતીમાં વાત કરીશ. ચાલો આગળ વધીએ."
            else:
                switch_message = "Yes! I'll now speak in English. Let's continue."
            
            return {
                "action": "language_switch",
                "updates": {},
                "ask": switch_message,
                "field_focus": None,
                "tone": "friendly",
                "language": new_language.value,
                "reply": switch_message
            }
        
        # Check for voice interruption commands
        if voice_interruption_handler.is_interruption_command(user_text, self.current_language):
            interruption_type = voice_interruption_handler.detect_interruption(user_text, self.current_language)
            
            if interruption_type == InterruptionType.STOP:
                stop_msg = "બંધ કર્યું" if self.current_language == Language.GUJARATI else "Stopped"
                return {
                    "action": "interrupt_stop",
                    "updates": {},
                    "ask": stop_msg,
                    "field_focus": None,
                    "tone": "neutral",
                    "language": self.current_language.value,
                    "reply": stop_msg
                }
            elif interruption_type == InterruptionType.SKIP:
                current_field = self.get_next_field()
                if current_field and not current_field.validation.required:
                    # Skip the field
                    field_key = self._get_field_key(current_field.name)
                    self.session.update_field(field_key, None, FieldStatus.COLLECTED)
                    
                    next_field = self.get_next_field()
                    if next_field:
                        skip_msg = f"છોડ્યું. {self._generate_field_question_text(next_field)}" if self.current_language == Language.GUJARATI else f"Skipped. {self._generate_field_question_text(next_field)}"
                        return {
                            "action": "ask",
                            "updates": {},
                            "ask": skip_msg,
                            "field_focus": next_field.name,
                            "tone": "friendly",
                            "language": self.current_language.value,
                            "reply": skip_msg
                        }
                    else:
                        done_msg = f"પૂર્ણ! {self.form_schema.confirmation_message}" if self.current_language == Language.GUJARATI else f"Complete! {self.form_schema.confirmation_message}"
                        return {
                            "action": "done",
                            "updates": {},
                            "ask": done_msg,
                            "field_focus": None,
                            "tone": "success",
                            "language": self.current_language.value,
                            "reply": done_msg
                        }
        
        # Check for form submission commands
        submission_commands = {
            Language.ENGLISH: ["submit", "submit form", "submit the form", "submit this form", "submit karo", "submit kar", "send form", "send it"],
            Language.GUJARATI: ["પ્રસ્તુત કરો", "સબમિટ કરો", "ફોર્મ સબમિટ કરો", "ફોર્મ પ્રસ્તુત કરો", "મોકલો", "મોકલી દો"]
        }
        
        user_text_lower = user_text.lower().strip()
        is_submission_command = False
        
        for lang, commands in submission_commands.items():
            for command in commands:
                if command.lower() in user_text_lower:
                    is_submission_command = True
                    break
            if is_submission_command:
                break
        
        if is_submission_command:
            # Check if form is complete enough to submit (all required fields)
            completion_status = self.get_completion_status()
            if completion_status.get("is_complete", False):
                # Form is complete, trigger submission
                submit_msg = "ફોર્મ સબમિટ કરી દીધું! ધન્યવાદ." if self.current_language == Language.GUJARATI else "Form submitted successfully! Thank you."
                return {
                    "action": "submit",
                    "updates": {},
                    "ask": submit_msg,
                    "field_focus": None,
                    "tone": "success",
                    "language": self.current_language.value,
                    "reply": submit_msg
                }
            else:
                # Form not complete, inform user about required fields
                next_required_field = self.get_next_required_field()
                if next_required_field:
                    pending_msg = f"હજી આ આવશ્યક છે: {self._generate_field_question_text(next_required_field)}" if self.current_language == Language.GUJARATI else f"Please complete this required field: {self._generate_field_question_text(next_required_field)}"
                else:
                    # No required fields left, allow submission
                    submit_msg = "ફોર્મ સબમિટ કરી દીધું! ધન્યવાદ." if self.current_language == Language.GUJARATI else "Form submitted successfully! Thank you."
                    return {
                        "action": "submit",
                        "updates": {},
                        "ask": submit_msg,
                        "field_focus": None,
                        "tone": "success",
                        "language": self.current_language.value,
                        "reply": submit_msg
                    }
                return {
                    "action": "ask",
                    "updates": {},
                    "ask": pending_msg,
                    "field_focus": current_field.name,
                    "tone": "helpful",
                    "language": self.current_language.value,
                    "reply": pending_msg
                }
        
        # Check if conversation needs to start with greeting (fix initial JSON formatting)
        if not self.session.context[form_context_key].get("greeting_sent"):
            self.session.context[form_context_key]["greeting_sent"] = True
            
            # Generate initial greeting WITHOUT JSON meta text
            greeting = language_support.generate_initial_greeting(
                self.form_schema.title,
                self.form_schema.description or "",
                self.current_language
            )
            
            first_field = self.get_next_field()
            if first_field:
                field_question = self._generate_field_question_text(first_field)
                
                # Clean response - no JSON formatting in the message
                clean_greeting = greeting.strip()
                clean_question = field_question.strip()
                full_message = f"{clean_greeting}\n\n{clean_question}"
                
                # Start enhanced silence detection with intelligent context
                silence_manager.start_silence_detection(
                    self.session.session_id,
                    self._silence_callback,
                    clean_question,
                    context={
                        "field_name": first_field.name,
                        "field_type": first_field.type.value,
                        "awaiting_field_response": True
                    }
                )
                
                return {
                    "action": "ask",
                    "updates": {},
                    "ask": full_message,
                    "field_focus": first_field.name,
                    "tone": "friendly",
                    "language": self.current_language.value,
                    "greeting": clean_greeting,
                    "reply": full_message
                }
        
        # Process normal input
        return self._process_normal_input(user_text)
    
    def _process_normal_input(self, user_text: str) -> Dict[str, Any]:
        """Process normal conversational input"""
        try:
            current_field = self.get_next_field()
            
            # Build context for LLM
            context = self._build_llm_context(user_text, current_field)
            
            # Get LLM response
            self._rate_limit()
            response = self.model.generate_content(
                json.dumps(context, indent=2),
                generation_config={
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "max_output_tokens": 2048
                }
            )
            
            if not response or not response.text:
                raise Exception("Empty response from LLM")
            
            # Parse LLM response
            llm_response = self._parse_llm_response(response.text)
            
            # Process field updates with enhanced validation
            return self._process_field_updates(llm_response, current_field)
            
        except Exception as e:
            logger.error(f"Input processing error: {e}")
            error_msg = "માફ કરશો, તકનીકી સમસ્યા છે. કૃપા કરીને ફરીથી પ્રયાસ કરો." if self.current_language == Language.GUJARATI else "Sorry, I'm having a technical issue. Please try again."
            return {
                "action": "error",
                "updates": {},
                "ask": error_msg,
                "field_focus": current_field.name if current_field else None,
                "tone": "apologetic",
                "language": self.current_language.value,
                "reply": error_msg
            }
    
    def _build_llm_context(self, user_input: str, current_field: Optional[FormField]) -> Dict[str, Any]:
        """Build comprehensive context for LLM"""
        form_context_key = self._get_form_context_key()
        
        # Get current field states
        field_states = {}
        for field in self.form_schema.fields:
            field_key = self._get_field_key(field.name)
            field_state = self.session.fields.get(field_key)
            
            field_states[field.name] = {
                "type": field.type.value,
                "label": field.label,
                "required": field.validation.required,
                "options": field.options or [],
                "description": field.description,
                "current_value": field_state.value if field_state else None,
                "status": field_state.status.value if field_state else "pending",
                "attempts": field_state.attempt_count if field_state else 0
            }
        
        return {
            "form_info": {
                "title": self.form_schema.title,
                "description": self.form_schema.description
            },
            "field_states": field_states,
            "current_field": current_field.name if current_field else None,
            "user_input": user_input,
            "conversation_history": self.session.get_conversation_context(10),
            "form_context": self.session.context.get(form_context_key, {}),
            "completion_status": self.get_completion_status(),
            "language": self.current_language.value,
            "current_language": self.current_language.value
        }
    
    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """Parse LLM JSON response with fallback handling"""
        try:
            return json.loads(response_text.strip())
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON in the text
        json_patterns = [r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', r'\{.*\}']
        
        for pattern in json_patterns:
            matches = re.findall(pattern, response_text, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
        
        # Fallback response
        logger.warning(f"Failed to parse LLM response: {response_text[:200]}...")
        fallback_text = language_support.get_ui_text("are_you_there", self.current_language)
        return {
            "action": "ask",
            "updates": {},
            "ask": fallback_text,
            "field_focus": None,
            "tone": "apologetic",
            "language": self.current_language.value,
            "reply": fallback_text
        }
    
    def _process_field_updates(self, llm_response: Dict[str, Any], current_field: Optional[FormField]) -> Dict[str, Any]:
        """Process and validate field updates from LLM response"""
        updates = llm_response.get("updates", {})
        validated_updates = {}
        validation_errors = {}
        
        # Validate each field update
        for field_name, value in updates.items():
            if value is not None and str(value).strip():
                field_schema = next((f for f in self.form_schema.fields if f.name == field_name), None)
                
                if field_schema:
                    validation_result = self._validate_field_value(field_schema, str(value))
                    
                    if validation_result.is_valid:
                        validated_updates[field_name] = validation_result.cleaned_value
                        field_key = self._get_field_key(field_name)
                        self.session.update_field(field_key, validation_result.cleaned_value, FieldStatus.COLLECTED)
                    else:
                        validation_errors[field_name] = {
                            "error": validation_result.error_message,
                            "suggestion": validation_result.suggestion
                        }
        
        # Handle validation errors
        if validation_errors:
            field_name = list(validation_errors.keys())[0]
            error_info = validation_errors[field_name]
            
            return {
                "action": "ask",
                "updates": {},
                "ask": f"{error_info['error']}. {error_info['suggestion']}",
                "field_focus": field_name,
                "tone": "helpful",
                "language": self.current_language.value,
                "reply": f"{error_info['error']}. {error_info['suggestion']}"
            }
        
        # Update response with validated data
        llm_response["updates"] = validated_updates
        llm_response["language"] = self.current_language.value
        
        # Check if form is complete
        next_field = self.get_next_field()
        if next_field is None:
            done_msg = f"પરફેક્ટ! મેં બધી માહિતી એકત્રિત કરી છે. {self.form_schema.confirmation_message}" if self.current_language == Language.GUJARATI else f"Perfect! I've collected all the information. {self.form_schema.confirmation_message}"
            llm_response.update({
                "action": "done",
                "ask": done_msg,
                "field_focus": None,
                "tone": "success",
                "reply": done_msg
            })
            
            # Stop silence monitoring
            silence_manager.stop_session(self.session.session_id)
            
        elif llm_response.get("action") == "set" and validated_updates:
            # Move to next field with intelligent context
            llm_response["field_focus"] = next_field.name
            if not llm_response.get("ask"):
                llm_response["ask"] = self._generate_field_question_text(next_field)
                llm_response["reply"] = llm_response["ask"]
                
            # Update silence manager with new field context
            silence_manager.start_silence_detection(
                self.session.session_id,
                self._silence_callback,
                llm_response["ask"],
                context={
                    "field_name": next_field.name,
                    "field_type": next_field.type.value,
                    "awaiting_field_response": True
                }
            )
        
        # Ensure reply is set
        if not llm_response.get("reply"):
            llm_response["reply"] = llm_response.get("ask", "")
        
        return llm_response
    
    def _validate_field_value(self, field: FormField, value: str) -> ValidationResult:
        """Validate field value using enhanced validators"""
        if field.type == FieldType.SHORT_ANSWER and 'name' in field.name.lower():
            return self.validator.validate_full_name(value, self.current_language)
        elif field.type == FieldType.EMAIL:
            return self.validator.validate_email(value, self.current_language)
        elif field.type == FieldType.PHONE:
            return self.validator.validate_phone(value, self.current_language)
        elif field.type == FieldType.DATE:
            return self.validator.validate_date(value, self.current_language)
        elif field.type in [FieldType.MULTIPLE_CHOICE, FieldType.DROPDOWN]:
            # Strict option matching for checkboxes/dropdowns
            if field.options and value not in field.options:
                error_msg = "કૃપા કરીને ઉપલબ્ધ વિકલ્પોમાંથી પસંદ કરો" if self.current_language == Language.GUJARATI else "Please choose from the available options"
                suggestion = f"ઉપલબ્ધ વિકલ્પો: {', '.join(field.options)}" if self.current_language == Language.GUJARATI else f"Available options: {', '.join(field.options)}"
                return ValidationResult(False, "", error_msg, suggestion)
        elif field.type == FieldType.CHECKBOXES:
            # Handle multiple selections with strict validation
            if field.options:
                selected = value.split(',') if isinstance(value, str) else [value]
                invalid_options = [opt.strip() for opt in selected if opt.strip() not in field.options]
                if invalid_options:
                    error_msg = f"અમાન્ય વિકલ્પો: {', '.join(invalid_options)}" if self.current_language == Language.GUJARATI else f"Invalid options: {', '.join(invalid_options)}"
                    suggestion = f"ઉપલબ્ધ વિકલ્પો: {', '.join(field.options)}" if self.current_language == Language.GUJARATI else f"Available options: {', '.join(field.options)}"
                    return ValidationResult(False, "", error_msg, suggestion)
        
        return ValidationResult(True, value, "", "")
    
    def _generate_field_question_text(self, field: FormField) -> str:
        """Generate natural question text for a field in appropriate language"""
        if self.current_language == Language.GUJARATI:
            return self._generate_gujarati_field_question(field)
        else:
            return self._generate_english_field_question(field)
    
    def _generate_english_field_question(self, field: FormField) -> str:
        """Generate English field question"""
        base_question = field.label
        if not base_question.endswith('?'):
            base_question = f"What's your {base_question.lower()}?"
        
        if field.type == FieldType.MULTIPLE_CHOICE and field.options:
            options_text = ", ".join(field.options)
            return f"{base_question} Please choose from: {options_text}"
        elif field.type == FieldType.CHECKBOXES and field.options:
            options_text = ", ".join(field.options)
            return f"{base_question} You can select multiple from: {options_text}"
        elif field.type == FieldType.DATE:
            return f"{base_question} You can say it naturally like 'January 1st, 2000' or '22nd December 2004'"
        elif field.type == FieldType.EMAIL:
            return f"What's your email address? You can speak it naturally and I'll understand"
        elif field.type == FieldType.PHONE:
            return f"What's your phone number? Just say it naturally"
        
        if not field.validation.required:
            return f"This field is optional, but {base_question.lower()}"
        
        return base_question
    
    def _generate_gujarati_field_question(self, field: FormField) -> str:
        """Generate Gujarati field question"""
        # Use language support to generate contextual Gujarati questions
        try:
            gujarati_response = language_support.generate_language_specific_response(
                "",
                {"field": field.name, "label": field.label, "type": field.type.value},
                Language.GUJARATI,
                {
                    "name": field.name,
                    "label": field.label,
                    "type": field.type.value,
                    "required": field.validation.required,
                    "options": field.options
                }
            )
            
            if gujarati_response.get("field_question"):
                return gujarati_response["field_question"]
            elif gujarati_response.get("response"):
                return gujarati_response["response"]
        except Exception as e:
            logger.warning(f"Failed to generate Gujarati question: {e}")
        
        # Fallback Gujarati questions
        field_translations = {
            "full_name": "તમારું પૂરું નામ શું છે?",
            "email": "તમારું ઈમેઇલ એડ્રેસ શું છે?",
            "phone": "તમારો ફોન નમ્બર શું છે?",
            "dob": "તમારી જન્મતારીખ શું છે?",
            "date": "તારીખ શું છે?"
        }
        
        return field_translations.get(field.name, f"{field.label} શું છે?")
    
    def _silence_callback(self, session_id: str, prompt_message: str, language: Language):
        """Callback for silence manager prompts"""
        # This would typically trigger TTS or send message to frontend
        logger.info(f"Silence prompt for {session_id}: {prompt_message}")
        
        # Add system message for silence prompt
        self.session.add_message(MessageRole.SYSTEM, f"Silence prompt: {prompt_message}")
    
    def _rate_limit(self):
        """Simple rate limiting"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()
    
    def get_form_summary(self) -> Dict[str, Any]:
        """Get current form state summary"""
        field_summary = {}
        
        for field in self.form_schema.fields:
            field_key = self._get_field_key(field.name)
            field_state = self.session.fields.get(field_key)
            
            if field_state:
                field_summary[field.name] = {
                    "value": field_state.value,
                    "status": field_state.status.value,
                    "attempts": field_state.attempt_count
                }
            else:
                field_summary[field.name] = {
                    "value": None,
                    "status": "pending",
                    "attempts": 0
                }
        
        return {
            "form_id": self.form_id,
            "form_title": self.form_schema.title,
            "fields": field_summary,
            "completion_status": self.get_completion_status(),
            "next_field": self.get_next_field().name if self.get_next_field() else None,
            "language": self.current_language.value
        }
    
    def get_completion_status(self) -> Dict[str, Any]:
        """Get form completion status"""
        total_required = sum(1 for f in self.form_schema.fields if f.validation.required)
        completed_required = 0
        
        for field in self.form_schema.fields:
            if field.validation.required:
                field_key = self._get_field_key(field.name)
                field_state = self.session.fields.get(field_key)
                if field_state and field_state.status == FieldStatus.COLLECTED:
                    completed_required += 1
        
        total_fields = len(self.form_schema.fields)
        completed_fields = sum(
            1 for field in self.form_schema.fields 
            if self.session.fields.get(self._get_field_key(field.name), {}).status == FieldStatus.COLLECTED
        )
        
        return {
            "total_fields": total_fields,
            "completed_fields": completed_fields,
            "total_required": total_required,
            "completed_required": completed_required,
            "is_complete": completed_required >= total_required,
            "progress_percentage": (completed_fields / total_fields) * 100 if total_fields > 0 else 0
        }

# Alias for backward compatibility
DynamicFormConversation = EnhancedDynamicFormConversation