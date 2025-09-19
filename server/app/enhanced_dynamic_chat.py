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
        6. **FIELD CORRECTION DETECTION**: Detect when user is correcting previously filled fields
        7. **CONDITIONAL FIELD HANDLING**: When radio buttons change, ask about new conditional fields
        8. **SMART FIELD TRACKING**: Always update fields when user provides corrections
        
        CONVERSATION MANAGEMENT:
        - Start with contextual greeting explaining the form purpose and fields to be collected
        - Ask for ONE field at a time
        - Handle corrections and language switches immediately
        - Support both required and optional fields
        - Provide helpful error messages in appropriate language
        - Detect field corrections and update immediately
        - Handle conditional fields appearing based on selections
        
        RESPONSE FORMAT (JSON ONLY):
        {{
          "action": "ask" | "set" | "done" | "clarify" | "correct" | "remove" | "language_switch" | "conditional_trigger",
          "updates": {{"field_name": "cleaned_value or null if removed"}},
          "ask": "Your natural response in appropriate language",
          "field_focus": "current_field_name",
          "tone": "friendly" | "encouraging" | "apologetic" | "professional" | "confirmation",
          "language": "en" | "gu",
          "greeting": "Initial greeting if starting conversation",
          "correction_detected": "Boolean if user is correcting a field",
          "conditional_fields_triggered": "List of new conditional field names if any"
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
        """Get the next field that needs to be filled, including conditional fields"""
        form_context_key = self._get_form_context_key()
        
        # Check main form fields in order
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
    
    def get_form_summary(self) -> Dict[str, Any]:
        """Get current form state summary"""
        form_context_key = self._get_form_context_key()
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
        
        completion_status = self.get_completion_status()
        
        return {
            "form_id": self.form_id,
            "form_title": self.form_schema.title,
            "fields": field_summary,
            "completion_status": completion_status,
            "next_field": self.get_next_field().name if self.get_next_field() else None
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
    
    def _rate_limit(self):
        """Simple rate limiting"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()
    
    def _generate_field_question_text(self, field: FormField) -> str:
        """Generate natural question text for a field"""
        
        # Extract user's name from session if available
        form_context_key = self._get_form_context_key()
        user_name = self.session.context.get(form_context_key, {}).get("user_name", "")
        
        # Personalize if we have the user's name
        greeting = f"Hi {user_name}! " if user_name else ""
        
        base_question = field.label
        if not base_question.endswith('?'):
            base_question = f"What's your {base_question.lower()}?"
        
        # Add field-specific context
        if field.type == FieldType.MULTIPLE_CHOICE and field.options:
            options_text = ", ".join(field.options)
            return f"{greeting}{base_question} Please choose from: {options_text}"
        
        elif field.type == FieldType.CHECKBOXES and field.options:
            options_text = ", ".join(field.options)
            return f"{greeting}{base_question} You can select multiple from: {options_text}"
        
        elif field.type == FieldType.LINEAR_SCALE:
            return f"{greeting}{base_question} Please rate from {field.scale_min} ({field.scale_min_label or 'lowest'}) to {field.scale_max} ({field.scale_max_label or 'highest'})"
        
        elif field.type == FieldType.DATE:
            return f"{greeting}{base_question} You can say it naturally like 'January 1st, 2000' or '01/01/2000'"
        
        elif field.type == FieldType.EMAIL:
            return f"{greeting}What's your email address? You can speak it naturally and I'll understand"
        
        elif field.type == FieldType.PHONE:
            return f"{greeting}What's your phone number? Just say it naturally"
        
        elif field.type == FieldType.PASSWORD:
            required_text = "" if field.validation.required else "This field is optional, but "
            return f"{greeting}{required_text}Please provide your password. Note: You should type this manually for security rather than speaking it aloud"
        
        # Handle non-required fields with appropriate messaging
        if not field.validation.required:
            if field.description:
                return f"{greeting}This field is optional: {base_question} {field.description}"
            else:
                return f"{greeting}This field is optional, but {base_question.lower()}"
        
        # Add description if available
        if field.description:
            return f"{greeting}{base_question} {field.description}"
        
        return f"{greeting}{base_question}"
    
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

            # After switching, ask the next question
            next_field = self.get_next_field()
            next_question = ""
            field_focus = None
            if next_field:
                next_question = self._generate_field_question_text(next_field)
                field_focus = next_field.name

            full_message = f"{switch_message} {next_question}".strip()

            return {
                "action": "language_switch",
                "updates": {},
                "ask": full_message,
                "field_focus": field_focus,
                "tone": "friendly",
                "language": new_language.value,
                "reply": full_message
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
        
        # Check if conversation needs to start with greeting (fix initial JSON formatting)
        if not self.session.context[form_context_key].get("greeting_sent"):
            self.session.context[form_context_key]["greeting_sent"] = True
            
            # Generate initial greeting WITHOUT JSON meta text
            greeting = language_support.generate_initial_greeting(
                self.form_schema.title,
                self.form_schema.description or "",
                self.current_language,
                self.form_schema.fields
            )
            
            first_field = self.get_next_field()
            if first_field:
                field_question = self._generate_field_question_text(first_field)
                
                # Clean response - no JSON formatting in the message
                clean_greeting = greeting.strip()
                clean_question = field_question.strip()
                
                # Remove any JSON artifacts from greeting
                clean_greeting = re.sub(r'\{.*?\}', '', clean_greeting, flags=re.DOTALL)
                clean_greeting = re.sub(r'```.*?```', '', clean_greeting, flags=re.DOTALL)
                clean_greeting = clean_greeting.strip()
                
                full_message = f"{clean_greeting}\n\n{clean_question}"
                
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
            # Get current field and build context
            current_field = self.get_next_field()
            context = self._build_llm_context(user_text, current_field)
            
            # Get LLM response
            self._rate_limit()
            response = self.model.generate_content(
                json.dumps(context, indent=2),
                generation_config={
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "max_output_tokens": 1024
                }
            )
            
            if not response or not response.text:
                raise Exception("Empty response from LLM")
            
            # Parse and clean LLM response
            llm_response = self._parse_llm_response(response.text)
            
            # Process the field updates
            return self._process_field_updates(llm_response, current_field)
            
        except Exception as e:
            logger.error(f"LLM processing error: {e}")
            return {
                "action": "error",
                "updates": {},
                "ask": "I'm having a technical issue. Could you please repeat that?",
                "field_focus": current_field.name if current_field else None,
                "tone": "apologetic",
                "reply": "I'm having a technical issue. Could you please repeat that?"
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
        
        # Get conversation history
        conversation_history = self.session.get_conversation_context(5)
        
        return {
            "form_info": {
                "title": self.form_schema.title,
                "description": self.form_schema.description
            },
            "field_states": field_states,
            "current_field": current_field.name if current_field else None,
            "user_input": user_input,
            "conversation_history": conversation_history,
            "form_context": self.session.context.get(form_context_key, {}),
            "completion_status": self.get_completion_status()
        }
    
    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """Parse LLM JSON response with aggressive cleaning to prevent JSON artifacts in user messages"""
        
        # First, try to clean the response text
        cleaned_text = response_text.strip()
        
        # Remove markdown code blocks
        cleaned_text = re.sub(r'```json\s*', '', cleaned_text)
        cleaned_text = re.sub(r'```\s*', '', cleaned_text)
        
        try:
            parsed = json.loads(cleaned_text)
            return self._clean_json_artifacts_from_response(parsed)
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON in the text
        json_patterns = [
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
            r'\{.*\}',
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, cleaned_text, re.DOTALL)
            for match in matches:
                try:
                    parsed = json.loads(match)
                    return self._clean_json_artifacts_from_response(parsed)
                except json.JSONDecodeError:
                    continue
        
        # If no JSON found, try to extract clean text from the response
        clean_text = response_text.strip()
        clean_text = re.sub(r'\{.*?\}', '', clean_text, flags=re.DOTALL).strip()
        clean_text = re.sub(r'```.*?```', '', clean_text, flags=re.DOTALL).strip()
        clean_text = re.sub(r'["{}\[\]]', '', clean_text).strip()
        
        if clean_text and len(clean_text) > 10:
            return {
                "action": "ask",
                "updates": {},
                "ask": clean_text,
                "field_focus": None,
                "tone": "friendly",
                "reply": clean_text
            }
        
        # Final fallback response
        logger.warning(f"Failed to parse LLM response: {response_text[:200]}...")
        return {
            "action": "ask",
            "updates": {},
            "ask": "I had trouble understanding. Could you please rephrase that?",
            "field_focus": None,
            "tone": "apologetic",
            "reply": "I had trouble understanding. Could you please rephrase that?"
        }
    
    def _clean_json_artifacts_from_response(self, parsed_response: Dict[str, Any]) -> Dict[str, Any]:
        """Aggressively clean JSON artifacts from all text fields in response"""
        
        # Clean text fields that might contain JSON artifacts
        text_fields = ['ask', 'reply', 'greeting']
        
        for field in text_fields:
            if field in parsed_response and isinstance(parsed_response[field], str):
                original_text = parsed_response[field]
                
                # Remove JSON objects/arrays from text
                cleaned = re.sub(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', '', original_text, flags=re.DOTALL)
                cleaned = re.sub(r'\[.*?\]', '', cleaned, flags=re.DOTALL)
                
                # Remove markdown code blocks
                cleaned = re.sub(r'```.*?```', '', cleaned, flags=re.DOTALL)
                
                # Remove common JSON artifacts
                cleaned = re.sub(r'"[^"]*":', '', cleaned)  # Remove "key": patterns
                cleaned = re.sub(r'["{}\[\],]', '', cleaned)  # Remove JSON punctuation
                
                # Clean up whitespace and newlines
                cleaned = re.sub(r'\s+', ' ', cleaned).strip()
                
                # Remove empty lines and fix sentence structure
                sentences = [s.strip() for s in cleaned.split('.') if s.strip()]
                if sentences:
                    cleaned = '. '.join(sentences)
                    if not cleaned.endswith('.') and not cleaned.endswith('?') and not cleaned.endswith('!'):
                        cleaned += '.'
                
                parsed_response[field] = cleaned if cleaned else original_text
        
        return parsed_response
    
    def _process_field_updates(self, llm_response: Dict[str, Any], current_field: Optional[FormField]) -> Dict[str, Any]:
        """Process and validate field updates from LLM response"""
        updates = llm_response.get("updates", {})
        validated_updates = {}
        validation_errors = {}
        
        # Validate each field update
        for field_name, value in updates.items():
            if value is not None and str(value).strip():
                # Find the field schema
                field_schema = next((f for f in self.form_schema.fields if f.name == field_name), None)
                
                if field_schema:
                    validation_result = self._validate_field_value(field_schema, str(value))
                    
                    if validation_result.is_valid:
                        validated_updates[field_name] = validation_result.cleaned_value
                        # Update session
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
                "reply": f"{error_info['error']}. {error_info['suggestion']}"
            }
        
        # Update response with validated data
        llm_response["updates"] = validated_updates
        
        # Check if form is complete
        next_field = self.get_next_field()
        if next_field is None:
            llm_response.update({
                "action": "done",
                "ask": f"Perfect! I've collected all the information. {self.form_schema.confirmation_message}",
                "field_focus": None,
                "tone": "success",
                "reply": f"Perfect! I've collected all the information. {self.form_schema.confirmation_message}"
            })
        elif llm_response.get("action") == "set" and validated_updates:
            # Move to next field
            llm_response["field_focus"] = next_field.name
            if not llm_response.get("ask"):
                llm_response["ask"] = self._generate_field_question_text(next_field)
                llm_response["reply"] = llm_response["ask"]
        
        return llm_response
    
    def _validate_field_value(self, field: FormField, value: str) -> ValidationResult:
        """Validate field value using appropriate validator"""
        
        if field.type == FieldType.SHORT_ANSWER and 'name' in field.name.lower():
            return self.validator.validate_full_name(value, self.current_language)
        elif field.type == FieldType.EMAIL:
            return self.validator.validate_email(value, self.current_language)
        elif field.type == FieldType.PHONE:
            return self.validator.validate_phone(value, self.current_language)
        elif field.type == FieldType.DATE:
            return self.validator.validate_date(value, self.current_language)
        elif field.type in [FieldType.MULTIPLE_CHOICE, FieldType.DROPDOWN]:
            # Strict option matching
            if field.options and value not in field.options:
                error_msg = "કૃપા કરીને ઉપલબ્ધ વિકલ્પોમાંથી પસંદ કરો" if self.current_language == Language.GUJARATI else "Please choose from the available options"
                suggestion = f"ઉપલબ્ધ વિકલ્પો: {', '.join(field.options)}" if self.current_language == Language.GUJARATI else f"Available options: {', '.join(field.options)}"
                return ValidationResult(False, "", error_msg, suggestion)
        elif field.type == FieldType.CHECKBOXES:
            # Handle multiple selections
            if field.options:
                selected = value.split(',') if isinstance(value, str) else [value]
                invalid_options = [opt.strip() for opt in selected if opt.strip() not in field.options]
                if invalid_options:
                    error_msg = f"અમાન્ય વિકલ્પો: {', '.join(invalid_options)}" if self.current_language == Language.GUJARATI else f"Invalid options: {', '.join(invalid_options)}"
                    suggestion = f"ઉપલબ્ધ વિકલ્પો: {', '.join(field.options)}" if self.current_language == Language.GUJARATI else f"Available options: {', '.join(field.options)}"
                    return ValidationResult(False, "", error_msg, suggestion)
        
        # Default validation using existing validator
        field_dict = {
            "name": field.name,
            "required": field.validation.required,
            "pattern": field.validation.pattern,
            "min": field.validation.min_value,
            "max": field.validation.max_value,
            "options": field.options or []
        }
        
        error_message = validate_value(field.type.value, value, field_dict)
        
        if error_message:
            return ValidationResult(False, "", error_message, "Please try again with the correct format")
        
        return ValidationResult(True, value, "", "")

def _silence_callback(session_id: str, language: Language, context: Dict[str, Any]):
    """Callback for silence detection"""
    logger.info(f"Silence callback triggered for session {session_id}")

# Alias for backward compatibility
DynamicFormConversation = EnhancedDynamicFormConversation