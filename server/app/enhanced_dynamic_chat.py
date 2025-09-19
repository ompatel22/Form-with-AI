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

class GenericFieldValidator:
    """Generic field validator that works with any field type dynamically"""
    
    @staticmethod
    def validate_field(field: FormField, value: str, language: Language = Language.ENGLISH) -> ValidationResult:
        """Generic validation that adapts based on field type and constraints"""
        if not value or not value.strip():
            if field.validation.required:
                error_msg = "આ ફીલ્ડ આવશ્યક છે" if language == Language.GUJARATI else "This field is required"
                suggestion = f"કૃપા કરીને {field.label} આપો" if language == Language.GUJARATI else f"Please provide {field.label}"
                return ValidationResult(False, "", error_msg, suggestion)
            else:
                return ValidationResult(True, "", "", "")  # Optional field, empty is okay
        
        # Use Gemini to dynamically validate based on field context
        try:
            validation_prompt = f"""
            Validate this user input for a form field:
            
            Field Information:
            - Name: {field.name}
            - Type: {field.type.value}
            - Label: {field.label}
            - Description: {field.description or "None"}
            - Required: {field.validation.required}
            - Options: {field.options if field.options else "None"}
            - Min Length: {field.validation.min_length or "None"}
            - Max Length: {field.validation.max_length or "None"}
            - Pattern: {field.validation.pattern or "None"}
            
            User Input: "{value}"
            Language: {language.value}
            
            Instructions:
            1. Clean and format the input appropriately for the field type
            2. For choice fields (multiple_choice, dropdown, checkboxes), match user input to available options intelligently
            3. For checkboxes, parse multiple selections and return as comma-separated string
            4. For email/phone, apply intelligent speech-to-text corrections
            5. For dates, parse natural language dates
            6. Return ONLY valid JSON with no additional text
            
            Response format:
            {{
              "is_valid": true/false,
              "cleaned_value": "cleaned and formatted value",
              "error_message": "error message in {language.value}",
              "suggestion": "helpful suggestion in {language.value}"
            }}
            """
            
            model = genai.GenerativeModel(model_name=settings.GEMINI_MODEL)
            response = model.generate_content(
                validation_prompt,
                generation_config={
                    "temperature": 0.1,
                    "max_output_tokens": 1024
                }
            )
            
            if response and response.text:
                try:
                    result = json.loads(response.text.strip())
                    return ValidationResult(
                        result.get("is_valid", False),
                        result.get("cleaned_value", ""),
                        result.get("error_message", ""),
                        result.get("suggestion", "")
                    )
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse Gemini validation response: {response.text}")
                    
        except Exception as e:
            logger.error(f"Gemini validation failed: {e}")
        
        # Fallback to basic validation
        return GenericFieldValidator._basic_validation(field, value, language)
    
    @staticmethod
    def _basic_validation(field: FormField, value: str, language: Language) -> ValidationResult:
        """Fallback basic validation when Gemini is not available"""
        cleaned = value.strip()
        
        # Basic length validation
        if field.validation.min_length and len(cleaned) < field.validation.min_length:
            error_msg = f"ઓછામાં ઓછા {field.validation.min_length} અક્ષરો હોવા જોઈએ" if language == Language.GUJARATI else f"Minimum {field.validation.min_length} characters required"
            return ValidationResult(False, "", error_msg, "")
        
        if field.validation.max_length and len(cleaned) > field.validation.max_length:
            error_msg = f"વધુમાં વધુ {field.validation.max_length} અક્ષરો હોવા જોઈએ" if language == Language.GUJARATI else f"Maximum {field.validation.max_length} characters allowed"
            return ValidationResult(False, "", error_msg, "")
        
        # Basic type-specific validation
        if field.type == FieldType.EMAIL and '@' not in cleaned:
            error_msg = "માન્ય ઈમેઇલ આપો" if language == Language.GUJARATI else "Please provide a valid email"
            return ValidationResult(False, "", error_msg, "")
        elif field.type == FieldType.PHONE and not re.search(r'\d{7,}', cleaned):
            error_msg = "માન્ય ફોન નમ્બર આપો" if language == Language.GUJARATI else "Please provide a valid phone number"
            return ValidationResult(False, "", error_msg, "")
        elif field.type in [FieldType.MULTIPLE_CHOICE, FieldType.DROPDOWN] and field.options:
            # Try to find a match in options
            for option in field.options:
                if cleaned.lower() == option.lower():
                    return ValidationResult(True, option, "", "")
            error_msg = "ઉપલબ્ધ વિકલ્પોમાંથી પસંદ કરો" if language == Language.GUJARATI else "Please choose from available options"
            return ValidationResult(False, "", error_msg, f"Available: {', '.join(field.options)}")
        elif field.type == FieldType.CHECKBOXES and field.options:
            # Basic checkbox parsing
            items = [item.strip() for item in re.split(r'[,\s]+and\s+|[,\s]+અને\s+|,', cleaned, flags=re.IGNORECASE)]
            valid_items = []
            for item in items:
                for option in field.options:
                    if item.lower() == option.lower():
                        valid_items.append(option)
                        break
            if valid_items:
                return ValidationResult(True, ', '.join(valid_items), "", "")
            error_msg = "ઉપલબ્ધ વિકલ્પોમાંથી પસંદ કરો" if language == Language.GUJARATI else "Please choose from available options"
            return ValidationResult(False, "", error_msg, f"Available: {', '.join(field.options)}")
        
        return ValidationResult(True, cleaned, "", "")

class EnhancedDynamicFormConversation:
    """Enhanced conversational form handler with multilingual support and full dynamic capabilities"""
    
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
        
        self.validator = GenericFieldValidator()
        
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
        """Get enhanced multilingual system prompt with dynamic form adaptation"""
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
        
        CURRENT FORM FIELDS:
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
        - Start with contextual greeting explaining the form purpose
        - Ask for ONE field at a time unless user provides multiple fields
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
        
        Remember: Be conversational, culturally aware, and make the form-filling experience pleasant while being completely adaptive to any form structure!
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
        """Enhanced user input processing with full dynamic capabilities"""
        form_context_key = self._get_form_context_key()
        
        # Update activity for silence manager
        silence_manager.update_activity(self.session.session_id)
        
        # Check for language switch command first
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
            
            greeting = language_support.generate_initial_greeting(
                self.form_schema.title,
                self.form_schema.description or "",
                self.current_language,
                self.form_schema.fields
            )
            
            first_field = self.get_next_field()
            if first_field:
                field_question = self._generate_field_question_text(first_field)
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
        
        # Process with Gemini for intelligent field mapping and processing
        return self._process_with_gemini(user_text)
    
    def _process_with_gemini(self, user_text: str) -> Dict[str, Any]:
        """Use Gemini to intelligently process user input and map to form fields"""
        try:
            # Build context for Gemini
            context = self._build_llm_context(user_text, self.get_next_field())
            
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
            return self._process_field_updates(llm_response, self.get_next_field())
            
        except Exception as e:
            logger.error(f"Gemini processing error: {e}")
            error_msg = "માફ કરશો, તકનીકી સમસ્યા છે. કૃપા કરીને ફરીથી પ્રયાસ કરો." if self.current_language == Language.GUJARATI else "Sorry, I'm having a technical issue. Please try again."
            return {
                "action": "error",
                "updates": {},
                "ask": error_msg,
                "field_focus": None,
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
    
    def _find_field_schema(self, field_name: str) -> Optional[FormField]:
        """Find field schema including conditional fields"""
        # First check main form fields
        for field in self.form_schema.fields:
            if field.name == field_name:
                return field
        
        # Then check conditional fields
        for field in self.form_schema.fields:
            if field.conditional_fields:
                for value, conditional_fields in field.conditional_fields.items():
                    for cf in conditional_fields:
                        if cf.name == field_name:
                            # Return a FormField object for the conditional field
                            return FormField(
                                id=cf.id,
                                name=cf.name,
                                type=cf.type,
                                label=cf.label,
                                description=cf.description,
                                validation=cf.validation,
                                order=cf.order,
                                options=getattr(cf, 'options', None)
                            )
        
        return None

    def _build_llm_context(self, user_input: str, current_field: Optional[FormField]) -> Dict[str, Any]:
        """Build comprehensive context for LLM including all form information"""
        form_context_key = self._get_form_context_key()
        
        # Get current field states
        field_states = {}
        
        # Process all form fields
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
                "attempts": field_state.attempt_count if field_state else 0,
                "validation": {
                    "min_length": field.validation.min_length,
                    "max_length": field.validation.max_length,
                    "pattern": field.validation.pattern,
                    "custom_error_message": field.validation.custom_error_message
                }
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
            "instructions": {
                "checkbox_format": "For checkboxes, return comma-separated string like 'Option1, Option2'",
                "validation": "Use generic validation based on field type and constraints",
                "field_mapping": "Intelligently map user responses to appropriate fields based on context"
            }
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
        """Process and validate field updates from LLM response using generic validation"""
        updates = llm_response.get("updates", {})
        validated_updates = {}
        validation_errors = {}
        
        # Validate each field update using generic validator
        for field_name, value in updates.items():
            if value is not None and str(value).strip():
                field_schema = self._find_field_schema(field_name)
                
                if field_schema:
                    validation_result = self.validator.validate_field(field_schema, str(value), self.current_language)
                    
                    if validation_result.is_valid:
                        validated_updates[field_name] = validation_result.cleaned_value
                        field_key = self._get_field_key(field_name)
                        self.session.update_field(field_key, validation_result.cleaned_value, FieldStatus.COLLECTED)
                        logger.info(f"✅ Field '{field_name}' updated to: '{validation_result.cleaned_value}'")
                    else:
                        validation_errors[field_name] = {
                            "error": validation_result.error_message,
                            "suggestion": validation_result.suggestion
                        }
                        logger.warning(f"❌ Validation failed for '{field_name}': {validation_result.error_message}")
                else:
                    logger.warning(f"Field schema not found for field: {field_name}")
        
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
            
        elif validated_updates:
            # Always move to next field when we have updates
            llm_response["action"] = "ask"
            llm_response["field_focus"] = next_field.name if next_field else None
            
            if next_field:
                field_question = self._generate_field_question_text(next_field)
                if self.current_language == Language.GUJARATI:
                    transition = "આગળ, "
                else:
                    transition = "Next, "
                llm_response["ask"] = f"{transition}{field_question}"
                llm_response["reply"] = llm_response["ask"]
                llm_response["tone"] = "friendly"
        
        # Ensure reply is set
        if not llm_response.get("reply"):
            llm_response["reply"] = llm_response.get("ask", "")
        
        return llm_response
    
    def _find_field_schema(self, field_name: str) -> Optional[FormField]:
        """Find field schema including conditional fields"""
        # First check main form fields
        for field in self.form_schema.fields:
            if field.name == field_name:
                return field
        
        # Then check conditional fields
        for field in self.form_schema.fields:
            if field.conditional_fields:
                for value, conditional_fields in field.conditional_fields.items():
                    for cf in conditional_fields:
                        if cf.name == field_name:
                            return FormField(
                                id=cf.id,
                                name=cf.name,
                                type=cf.type,
                                label=cf.label,
                                description=cf.description,
                                validation=cf.validation,
                                order=cf.order,
                                options=getattr(cf, 'options', None)
                            )
        
        return None
    
    def _generate_field_question_text(self, field: FormField) -> str:
        """Generate appropriate question text for a field"""
        if self.current_language == Language.GUJARATI:
            base_question = f"કૃપા કરીને તમારું {field.label} આપો"
        else:
            base_question = f"Please provide your {field.label}"
        
        if field.type == FieldType.MULTIPLE_CHOICE and field.options:
            options_text = ", ".join(field.options)
            return f"{base_question} Please choose from: {options_text}"
        elif field.type == FieldType.CHECKBOXES and field.options:
            options_text = ", ".join(field.options)
            return f"{base_question} You can select multiple from: {options_text}"
        elif field.type == FieldType.DATE:
            return f"{base_question} (you can say it naturally like 'January 1st, 2000')"
        
        return base_question
    
    def get_completion_status(self) -> Dict[str, Any]:
        """Get form completion status"""
        total_fields = len(self.form_schema.fields)
        completed_fields = 0
        required_fields = 0
        completed_required = 0
        
        for field in self.form_schema.fields:
            field_key = self._get_field_key(field.name)
            field_state = self.session.fields.get(field_key)
            
            if field.validation.required:
                required_fields += 1
                if field_state and field_state.status == FieldStatus.COLLECTED:
                    completed_required += 1
            
            if field_state and field_state.status == FieldStatus.COLLECTED:
                completed_fields += 1
        
        is_complete = completed_required == required_fields
        
        return {
            "total_fields": total_fields,
            "completed_fields": completed_fields,
            "required_fields": required_fields,
            "completed_required": completed_required,
            "is_complete": is_complete,
            "completion_percentage": (completed_fields / total_fields) * 100 if total_fields > 0 else 0,
            "required_completion_percentage": (completed_required / required_fields) * 100 if required_fields > 0 else 100
        }
    
    def get_form_summary(self) -> Dict[str, Any]:
        """Get comprehensive form summary"""
        fields = {}
        
        for field in self.form_schema.fields:
            field_key = self._get_field_key(field.name)
            field_state = self.session.fields.get(field_key)
            
            fields[field.name] = {
                "label": field.label,
                "type": field.type.value,
                "required": field.validation.required,
                "value": field_state.value if field_state else None,
                "status": field_state.status.value if field_state else "pending",
                "attempts": field_state.attempt_count if field_state else 0
            }
        
        return {
            "form_id": self.form_id,
            "form_title": self.form_schema.title,
            "fields": fields,
            "completion_status": self.get_completion_status()
        }
    
    def _rate_limit(self):
        """Simple rate limiting"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()
    
    def _silence_callback(self, context: Dict[str, Any]):
        """Handle silence timeout callback"""
        logger.info(f"Silence detected for session {self.session.session_id}")
        return {
            "action": "silence_prompt",
            "ask": "Are you there? Please respond.",
            "field_focus": context.get("field_name"),
            "tone": "prompt",
            "language": self.current_language.value
        }