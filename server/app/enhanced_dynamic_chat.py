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
        
        CORRECTION DETECTION RULES:
        - Look for correction phrases: "મારું નામ ખોટું છે", "wrong name", "correction", "change my", "મારા નામમાં ભૂલ છે"
        - When user repeats field info for already filled fields, treat as correction
        - Always prioritize recent input over previous values
        - Ask for confirmation before updating critical fields
        
        CONDITIONAL FIELD RULES:
        - When user selects radio option that triggers conditional fields, immediately queue those fields
        - Ask conditional fields right after the triggering field is completed
        - Maintain order: main field → conditional fields → next main field
        - Show which conditional path was selected for clarity
        
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
    
    def _detect_field_correction(self, user_text: str) -> Optional[str]:
        """Detect if user is trying to correct a previously filled field"""
        correction_patterns = {
            Language.ENGLISH: [
                r"my (.+?) is wrong", r"wrong (.+?)", r"change my (.+?)", r"correct my (.+?)",
                r"my (.+?) should be", r"actually my (.+?) is", r"mistake in (.+?)",
                r"error in (.+?)", r"fix my (.+?)", r"update my (.+?)"
            ],
            Language.GUJARATI: [
                r"મારું (.+?) ખોટું છે", r"મારા (.+?)માં ભૂલ છે", r"મારું (.+?) બદલો",
                r"મારું (.+?) સુધારો", r"મારું (.+?) ખરાબ છે", r"ભૂલ છે (.+?)માં"
            ]
        }
        
        patterns = correction_patterns.get(self.current_language, correction_patterns[Language.ENGLISH])
        
        for pattern in patterns:
            match = re.search(pattern, user_text, re.IGNORECASE)
            if match:
                field_mention = match.group(1).lower()
                
                # Check if mentioned field exists and is already filled
                for field in self.form_schema.fields:
                    if (field_mention in field.name.lower() or 
                        field_mention in field.label.lower() or
                        (field_mention == "name" and "name" in field.name.lower()) or
                        (field_mention == "નામ" and "name" in field.name.lower()) or
                        (field_mention == "email" and field.type == FieldType.EMAIL) or
                        (field_mention == "ઈમેઇલ" and field.type == FieldType.EMAIL)):
                        
                        field_key = self._get_field_key(field.name)
                        field_state = self.session.fields.get(field_key)
                        
                        if field_state and field_state.status == FieldStatus.COLLECTED:
                            return field.name
        
        # Also check if user is providing info for already filled fields
        for field in self.form_schema.fields:
            field_key = self._get_field_key(field.name)
            field_state = self.session.fields.get(field_key)
            
            if field_state and field_state.status == FieldStatus.COLLECTED:
                # Check for field-specific patterns
                if field.type == FieldType.SHORT_ANSWER and "name" in field.name.lower():
                    name_patterns = [r"મારું નામ (.+?) છે", r"my name is (.+?)"]
                    for pattern in name_patterns:
                        if re.search(pattern, user_text, re.IGNORECASE):
                            return field.name
                elif field.type == FieldType.EMAIL:
                    email_patterns = [r"મારું ઈમેઇલ (.+?) છે", r"my email is (.+?)"]
                    for pattern in email_patterns:
                        if re.search(pattern, user_text, re.IGNORECASE):
                            return field.name
        
        return None

    def _get_conditional_fields_for_value(self, parent_field: FormField, selected_value: str) -> List[Dict[str, Any]]:
        """Get conditional fields that should appear for a selected value"""
        if not parent_field.conditional_fields:
            return []
        
        conditional_fields = parent_field.conditional_fields.get(selected_value, [])
        
        # Convert to proper format for processing
        fields_to_add = []
        for cf in conditional_fields:
            fields_to_add.append({
                "name": cf.name,
                "type": cf.type,
                "label": cf.label,
                "description": cf.description,
                "validation": cf.validation.__dict__ if hasattr(cf.validation, '__dict__') else {"required": cf.validation.required if hasattr(cf.validation, 'required') else False},
                "order": cf.order,
                "parent_field": parent_field.name,
                "parent_value": selected_value
            })
        
        return fields_to_add

    def _initialize_conditional_fields(self, parent_field_name: str, selected_value: str):
        """Initialize conditional fields in session when triggered"""
        parent_field = next((f for f in self.form_schema.fields if f.name == parent_field_name), None)
        if not parent_field or not parent_field.conditional_fields:
            return
        
        conditional_fields = parent_field.conditional_fields.get(selected_value, [])
        form_context_key = self._get_form_context_key()
        
        # Clear any previously triggered conditional fields from this parent
        for value, cf_list in parent_field.conditional_fields.items():
            if value != selected_value:  # Clear fields from other values
                for cf in cf_list:
                    field_key = f"{form_context_key}_{cf.name}"
                    if field_key in self.session.fields:
                        del self.session.fields[field_key]
                        logger.info(f"Cleared conditional field: {cf.name} (was for {parent_field_name}={value})")
        
        # Initialize new conditional fields
        for cf in conditional_fields:
            field_key = f"{form_context_key}_{cf.name}"
            # Always reset conditional fields to ensure fresh start
            self.session.update_field(field_key, None, FieldStatus.PENDING)
            logger.info(f"Initialized conditional field: {cf.name} (triggered by {parent_field_name}={selected_value})")

    def get_next_field(self) -> Optional[FormField]:
        """Get the next field that needs to be filled, including conditional fields"""
        form_context_key = self._get_form_context_key()
        
        # First, check main form fields in order
        sorted_fields = sorted(self.form_schema.fields, key=lambda f: f.order)
        
        for field in sorted_fields:
            field_key = self._get_field_key(field.name)
            field_info = self.session.fields.get(field_key, None)
            
            if not field_info or field_info.status in [FieldStatus.PENDING, FieldStatus.INVALID]:
                return field
            
            # If this field has conditional fields, check if we need to ask them
            if (field.conditional_fields and 
                field_info.status == FieldStatus.COLLECTED and 
                field_info.value):
                
                conditional_fields = field.conditional_fields.get(field_info.value, [])
                
                for cf in conditional_fields:
                    cf_field_key = f"{form_context_key}_{cf.name}"
                    cf_field_info = self.session.fields.get(cf_field_key, None)
                    
                    if not cf_field_info or cf_field_info.status in [FieldStatus.PENDING, FieldStatus.INVALID]:
                        # Return conditional field as next field to ask
                        # Create a temporary FormField object for conditional field
                        temp_field = FormField(
                            id=cf.id,
                            name=cf.name,
                            type=cf.type,
                            label=cf.label,
                            description=cf.description,
                            validation=cf.validation,
                            order=cf.order
                        )
                        return temp_field
        
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
                self.current_language,
                self.form_schema.fields
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
            # First check if this is a field correction
            correction_field = self._detect_field_correction(user_text)
            
            if correction_field:
                logger.info(f"Field correction detected for: {correction_field}")
                
                # Build context specifically for correction
                context = self._build_correction_context(user_text, correction_field)
                
                # Get LLM response for correction
                self._rate_limit()
                response = self.model.generate_content(
                    json.dumps(context, indent=2),
                    generation_config={
                        "temperature": 0.2,  # Lower temperature for corrections
                        "top_p": 0.8,
                        "max_output_tokens": 1024
                    }
                )
                
                if response and response.text:
                    llm_response = self._parse_llm_response(response.text)
                    llm_response["correction_detected"] = True
                    
                    # Process the correction
                    return self._process_field_correction(llm_response, correction_field, user_text)
            
            # Normal processing
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
                "field_focus": current_field.name if 'current_field' in locals() and current_field else None,
                "tone": "apologetic",
                "language": self.current_language.value,
                "reply": error_msg
            }

    def _build_correction_context(self, user_input: str, field_name: str) -> Dict[str, Any]:
        """Build context specifically for field correction"""
        form_context_key = self._get_form_context_key()
        
        # Get the field being corrected
        target_field = next((f for f in self.form_schema.fields if f.name == field_name), None)
        if not target_field:
            return self._build_llm_context(user_input, None)
        
        field_key = self._get_field_key(field_name)
        current_value = self.session.fields.get(field_key, {}).value if field_key in self.session.fields else None
        
        return {
            "correction_mode": True,
            "target_field": {
                "name": target_field.name,
                "type": target_field.type.value,
                "label": target_field.label,
                "current_value": current_value
            },
            "user_correction": user_input,
            "language": self.current_language.value,
            "form_info": {
                "title": self.form_schema.title,
                "description": self.form_schema.description
            },
            "instructions": f"User is correcting the field '{field_name}'. Extract the new correct value from their input and update it. Acknowledge the correction politely."
        }

    def _process_field_correction(self, llm_response: Dict[str, Any], field_name: str, user_text: str) -> Dict[str, Any]:
        """Process a field correction"""
        try:
            # Extract new value from user input using field-specific logic
            field_schema = next((f for f in self.form_schema.fields if f.name == field_name), None)
            if not field_schema:
                return llm_response
            
            # Try to extract the corrected value
            corrected_value = self._extract_corrected_value(user_text, field_schema)
            
            if corrected_value:
                # Validate the corrected value
                validation_result = self._validate_field_value(field_schema, corrected_value)
                
                if validation_result.is_valid:
                    # Update the field
                    field_key = self._get_field_key(field_name)
                    self.session.update_field(field_key, validation_result.cleaned_value, FieldStatus.COLLECTED)
                    
                    # Generate confirmation message
                    if self.current_language == Language.GUJARATI:
                        confirmation = f"સુધાર્યું! તમારું {field_schema.label} હવે '{validation_result.cleaned_value}' તરીકે નોંધાયું છે."
                    else:
                        confirmation = f"Corrected! Your {field_schema.label} is now recorded as '{validation_result.cleaned_value}'."
                    
                    # Continue with next field
                    next_field = self.get_next_field()
                    if next_field:
                        next_question = self._generate_field_question_text(next_field)
                        full_message = f"{confirmation} {next_question}"
                        
                        return {
                            "action": "correct",
                            "updates": {field_name: validation_result.cleaned_value},
                            "ask": full_message,
                            "field_focus": next_field.name,
                            "tone": "confirmation",
                            "language": self.current_language.value,
                            "reply": full_message,
                            "correction_detected": True
                        }
                    else:
                        done_msg = f"{confirmation} બધું પૂર્ણ!" if self.current_language == Language.GUJARATI else f"{confirmation} All done!"
                        return {
                            "action": "done",
                            "updates": {field_name: validation_result.cleaned_value},
                            "ask": done_msg,
                            "field_focus": None,
                            "tone": "success",
                            "language": self.current_language.value,
                            "reply": done_msg,
                            "correction_detected": True
                        }
                else:
                    # Validation failed
                    error_msg = f"{validation_result.error_message} {validation_result.suggestion}"
                    return {
                        "action": "ask",
                        "updates": {},
                        "ask": error_msg,
                        "field_focus": field_name,
                        "tone": "helpful",
                        "language": self.current_language.value,
                        "reply": error_msg,
                        "correction_detected": True
                    }
            
            # If we couldn't extract the value, ask for clarification
            clarify_msg = "માફ કરશો, મને સાચી માહિતી સમજાઈ નથી. કૃપા કરીને ફરીથી કહો." if self.current_language == Language.GUJARATI else "Sorry, I didn't understand the correct information. Please tell me again."
            
            return {
                "action": "clarify",
                "updates": {},
                "ask": clarify_msg,
                "field_focus": field_name,
                "tone": "apologetic",
                "language": self.current_language.value,
                "reply": clarify_msg,
                "correction_detected": True
            }
            
        except Exception as e:
            logger.error(f"Field correction processing failed: {e}")
            return llm_response

    def _extract_corrected_value(self, user_text: str, field: FormField) -> Optional[str]:
        """Extract corrected value from user input based on field type"""
        if field.type == FieldType.SHORT_ANSWER and "name" in field.name.lower():
            # Extract name patterns
            patterns = [
                r"મારું નામ (.+?) છે",
                r"my name is (.+?)$",
                r"call me (.+?)$",
                r"નામ (.+?) છે",
                r"name (.+?)$"
            ]
            
            for pattern in patterns:
                match = re.search(pattern, user_text, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
        
        elif field.type == FieldType.EMAIL:
            # Extract email patterns  
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            match = re.search(email_pattern, user_text)
            if match:
                return match.group(0)
        
        elif field.type == FieldType.PHONE:
            # Extract phone patterns - digits only
            digits = re.findall(r'\d+', user_text)
            if digits:
                return ''.join(digits)
        
        elif field.type in [FieldType.MULTIPLE_CHOICE, FieldType.DROPDOWN]:
            # Try to match with available options
            if field.options:
                for option in field.options:
                    if option.lower() in user_text.lower():
                        return option
        
        return None
    
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
        conditional_fields_triggered = []
        
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
                        
                        # Check if this field triggers conditional fields
                        if (field_schema.conditional_fields and 
                            validation_result.cleaned_value in field_schema.conditional_fields):
                            
                            # Initialize conditional fields
                            self._initialize_conditional_fields(field_name, validation_result.cleaned_value)
                            
                            # Get conditional field names for response
                            conditional_fields = field_schema.conditional_fields[validation_result.cleaned_value]
                            conditional_fields_triggered = [cf.name for cf in conditional_fields]
                            
                            logger.info(f"Conditional fields triggered by {field_name}={validation_result.cleaned_value}: {conditional_fields_triggered}")
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
        
        if conditional_fields_triggered:
            llm_response["conditional_fields_triggered"] = conditional_fields_triggered
        
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
            
        elif validated_updates:
            # FIXED: Always move to next field when we have updates, regardless of LLM action
            llm_response["action"] = "ask"  # Ensure we continue asking
            llm_response["field_focus"] = next_field.name if next_field else None
            
            if next_field:
                # Check if this is a conditional field that was just triggered
                is_conditional_field = next_field.name in conditional_fields_triggered
                
                if is_conditional_field:
                    # This is a conditional field - provide clear context
                    if self.current_language == Language.GUJARATI:
                        conditional_intro = f"સારું! હવે '{next_field.label}' વિશે પૂછવા દો:"
                    else:
                        conditional_intro = f"Great! Now let me ask about '{next_field.label}':"
                    
                    field_question = self._generate_field_question_text(next_field)
                    llm_response["ask"] = f"{conditional_intro} {field_question}"
                else:
                    # Regular next field
                    field_question = self._generate_field_question_text(next_field)
                    if self.current_language == Language.GUJARATI:
                        transition = "આગળ, "
                    else:
                        transition = "Next, "
                    llm_response["ask"] = f"{transition}{field_question}"
                
                llm_response["reply"] = llm_response["ask"]
                llm_response["tone"] = "friendly"
                
                # Update silence manager with new field context
                silence_manager.start_silence_detection(
                    self.session.session_id,
                    self._silence_callback,
                    llm_response["ask"],
                    context={
                        "field_name": next_field.name,
                        "field_type": next_field.type.value,
                        "awaiting_field_response": True,
                        "is_conditional": is_conditional_field
                    }
                )
        
        # Ensure reply is set
        if not llm_response.get("reply"):
            llm_response["reply"] = llm_response.get("ask", "")
        
        return llm_response
    
    def _validate_field_value(self, field: FormField, value: str) -> ValidationResult:
        """Validate field value using enhanced validators with Gujarati to English conversion"""
        
        # If user spoke in Gujarati but field needs English value, translate first
        english_value = value
        if self.current_language == Language.GUJARATI and self._contains_gujarati_text(value):
            try:
                english_value = self._translate_gujarati_to_english(value)
                logger.info(f"Translated Gujarati '{value}' to English '{english_value}' for form field")
            except Exception as e:
                logger.warning(f"Failed to translate Gujarati to English: {e}")
                # Continue with original value if translation fails
        
        if field.type == FieldType.SHORT_ANSWER and 'name' in field.name.lower():
            return self.validator.validate_full_name(english_value, self.current_language)
        elif field.type == FieldType.EMAIL:
            return self.validator.validate_email(english_value, self.current_language)
        elif field.type == FieldType.PHONE:
            return self.validator.validate_phone(english_value, self.current_language)
        elif field.type == FieldType.DATE:
            return self.validator.validate_date(english_value, self.current_language)
        elif field.type in [FieldType.MULTIPLE_CHOICE, FieldType.DROPDOWN]:
            # For choice fields, try to match English options even if user spoke in Gujarati
            if field.options:
                # First try exact match with cleaned value
                cleaned_value = english_value.strip()
                if cleaned_value in field.options:
                    return ValidationResult(True, cleaned_value, "", "")
                
                # Try case-insensitive match
                for option in field.options:
                    if cleaned_value.lower() == option.lower():
                        return ValidationResult(True, option, "", "")
                
                # If no exact match and we have Gujarati input, try intelligent mapping
                if self.current_language == Language.GUJARATI:
                    mapped_option = self._intelligent_option_mapping(value, field.options)
                    if mapped_option:
                        logger.info(f"Mapped Gujarati '{value}' to English option '{mapped_option}'")
                        return ValidationResult(True, mapped_option, "", "")
                
                # Try partial matching for common cases
                cleaned_lower = cleaned_value.lower()
                for option in field.options:
                    option_lower = option.lower()
                    if (cleaned_lower in option_lower or option_lower in cleaned_lower or
                        self._fuzzy_match(cleaned_lower, option_lower)):
                        logger.info(f"Fuzzy matched '{value}' to option '{option}'")
                        return ValidationResult(True, option, "", "")
                
                error_msg = "કૃપા કરીને ઉપલબ્ધ વિકલ્પોમાંથી પસંદ કરો" if self.current_language == Language.GUJARATI else "Please choose from the available options"
                suggestion = f"ઉપલબ્ધ વિકલ્પો: {', '.join(field.options)}" if self.current_language == Language.GUJARATI else f"Available options: {', '.join(field.options)}"
                return ValidationResult(False, "", error_msg, suggestion)
        elif field.type == FieldType.CHECKBOXES:
            # Handle multiple selections with strict validation
            if field.options:
                selected = english_value.split(',') if isinstance(english_value, str) else [english_value]
                valid_selections = []
                invalid_options = []
                
                for opt in selected:
                    opt = opt.strip()
                    if opt in field.options:
                        valid_selections.append(opt)
                    elif self.current_language == Language.GUJARATI and self._contains_gujarati_text(opt):
                        # Try to map Gujarati option to English
                        mapped_option = self._intelligent_option_mapping(opt, field.options)
                        if mapped_option:
                            valid_selections.append(mapped_option)
                        else:
                            invalid_options.append(opt)
                    else:
                        invalid_options.append(opt)
                
                if invalid_options:
                    error_msg = f"અમાન્ય વિકલ્પો: {', '.join(invalid_options)}" if self.current_language == Language.GUJARATI else f"Invalid options: {', '.join(invalid_options)}"
                    suggestion = f"ઉપલબ્ધ વિકલ્પો: {', '.join(field.options)}" if self.current_language == Language.GUJARATI else f"Available options: {', '.join(field.options)}"
                    return ValidationResult(False, "", error_msg, suggestion)
                
                # Return comma-separated valid selections in English
                return ValidationResult(True, ', '.join(valid_selections), "", "")
        
        return ValidationResult(True, english_value, "", "")

    def _fuzzy_match(self, text1: str, text2: str) -> bool:
        """Simple fuzzy matching for option selection"""
        # Check if either text contains the other (partial match)
        return (text1 in text2 or text2 in text1) and len(text1) > 2 and len(text2) > 2

    def _intelligent_option_mapping(self, gujarati_input: str, english_options: List[str]) -> Optional[str]:
        """Intelligent mapping of Gujarati input to English options with domain knowledge"""
        
        # Common patient type mappings
        gujarati_mappings = {
            # Patient type mappings
            "નવા દર્દી": "New Patient",
            "નવો દર્દી": "New Patient", 
            "નવા": "New Patient",
            "નવો": "New Patient",
            "નવું": "New Patient",
            "જૂના દર્દી": "Existing Patient",
            "જૂનો દર્દી": "Existing Patient",
            "જૂના": "Existing Patient", 
            "જૂનો": "Existing Patient",
            "જૂનું": "Existing Patient",
            "પહેલાના": "Existing Patient",
            "પુરાના": "Existing Patient",
            
            # Yes/No mappings
            "હા": "Yes",
            "હાં": "Yes", 
            "ના": "No",
            "નહીં": "No",
            
            # Common response mappings
            "ઉત્તમ": "Excellent",
            "સારું": "Good",
            "સામાન્ય": "Average",
            "ખરાબ": "Poor"
        }
        
        # Clean input text
        cleaned_input = gujarati_input.strip().lower()
        
        # Check direct mappings first
        for gujarati_phrase, english_equivalent in gujarati_mappings.items():
            if gujarati_phrase.lower() in cleaned_input:
                # Check if the English equivalent is in available options
                for option in english_options:
                    if english_equivalent.lower() == option.lower():
                        return option
        
        # Check for keywords in input
        input_words = cleaned_input.split()
        for word in input_words:
            for gujarati_phrase, english_equivalent in gujarati_mappings.items():
                if word in gujarati_phrase.lower():
                    for option in english_options:
                        if english_equivalent.lower() == option.lower():
                            return option
        
        # If no direct mapping, try AI-based translation
        return self._map_gujarati_to_english_option(gujarati_input, english_options)

    def _contains_gujarati_text(self, text: str) -> bool:
        """Check if text contains Gujarati characters"""
        return any('\u0A80' <= char <= '\u0AFF' for char in text)
    
    def _translate_gujarati_to_english(self, gujarati_text: str) -> str:
        """Translate Gujarati text to English for form storage"""
        try:
            prompt = f"""
            Translate the following Gujarati text to English. This is for form field storage, so provide a clean, natural English translation.
            
            Gujarati text: {gujarati_text}
            
            Return only the English translation, no explanations or additional text.
            """
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,
                    "top_p": 0.8,
                    "max_output_tokens": 200
                }
            )
            
            if response and response.text:
                translation = response.text.strip()
                # Clean up any artifacts
                translation = re.sub(r'^Translation:\s*', '', translation, flags=re.IGNORECASE)
                translation = re.sub(r'^English:\s*', '', translation, flags=re.IGNORECASE)
                return translation
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
        
        return gujarati_text  # Return original if translation fails
    
    def _map_gujarati_to_english_option(self, gujarati_option: str, english_options: List[str]) -> Optional[str]:
        """Map a Gujarati option to the closest English option from the available choices"""
        try:
            prompt = f"""
            Match the Gujarati option to the most appropriate English option from the list.
            
            Gujarati option: {gujarati_option}
            Available English options: {', '.join(english_options)}
            
            Return only the exact matching English option from the list, or "NO_MATCH" if none match appropriately.
            """
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,
                    "top_p": 0.8,
                    "max_output_tokens": 50
                }
            )
            
            if response and response.text:
                match = response.text.strip()
                if match in english_options:
                    return match
                    
        except Exception as e:
            logger.error(f"Option mapping failed: {e}")
        
        return None
    
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
        """Callback for silence manager prompts - repeats questions after timeout"""
        logger.info(f"🔄 Silence prompt for {session_id}: {prompt_message}")
        
        # Add system message for silence prompt  
        self.session.add_message(MessageRole.SYSTEM, f"Silence prompt: {prompt_message}")
        
        # This callback is triggered by the silence manager when user doesn't respond
        # The silence manager should be integrated with the main chat flow to repeat questions
        # For now, log the prompt - the frontend will handle the actual TTS via the /silence-prompt endpoint
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