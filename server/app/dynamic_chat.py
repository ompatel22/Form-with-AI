"""
Enhanced Dynamic Conversational Form Handler with LLM Integration
"""
import json
import re
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import google.generativeai as genai
import logging

from .form_builder import FormSchema, FormField, FieldType, form_store
from .validators import validate_value, clean_speech_input
from .memory import SessionState, FieldStatus, MessageRole
from .config import settings

logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)

class IntentClassifier:
    """Classify user intent for better conversation flow"""
    
    def classify_intent(self, user_text: str, current_field: str = None) -> Dict[str, Any]:
        """Classify user intent from their message"""
        text_lower = user_text.lower()
        
        intent = {
            "type": "provide_info",
            "confidence": 0.8,
            "field_mentioned": None,
            "correction_requested": False,
            "skip_requested": False,
            "remove_requested": False
        }
        
        # Check for correction intents
        correction_patterns = [
            r'(fix|correct|change|update|modify|wrong)',
            r'(my \w+ is actually|my \w+ should be)',
            r'(no|not|incorrect)'
        ]
        
        for pattern in correction_patterns:
            if re.search(pattern, text_lower):
                intent["correction_requested"] = True
                intent["type"] = "correction"
                break
        
        # Check for skip requests
        skip_patterns = [r'skip', r'next', r'pass', r'leave (it )?blank']
        for pattern in skip_patterns:
            if re.search(pattern, text_lower):
                intent["skip_requested"] = True
                intent["type"] = "skip"
                break
        
        # Check for removal requests
        remove_patterns = [r'remove', r'delete', r'clear', r'get rid of']
        for pattern in remove_patterns:
            if re.search(pattern, text_lower):
                intent["remove_requested"] = True
                intent["type"] = "remove"
                break
        
        # Check for field mentions
        field_keywords = {
            'name': ['name', 'full name', 'first name', 'last name'],
            'email': ['email', 'e-mail', 'mail', 'address'],
            'phone': ['phone', 'number', 'contact', 'telephone'],
            'date': ['date', 'birth', 'birthday', 'dob'],
            'age': ['age', 'years old'],
            'address': ['address', 'location', 'street']
        }
        
        for field_type, keywords in field_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    intent["field_mentioned"] = field_type
                    break
        
        return intent

class ValidationResult:
    """Structured validation result"""
    def __init__(self, is_valid: bool, cleaned_value: str, error_message: str = "", suggestion: str = ""):
        self.is_valid = is_valid
        self.cleaned_value = cleaned_value
        self.error_message = error_message
        self.suggestion = suggestion

class AdvancedValidator:
    """Enhanced field validation with speech-to-text normalization"""
    
    @staticmethod
    def validate_full_name(value: str) -> ValidationResult:
        if not value or not value.strip():
            return ValidationResult(False, "", "Name cannot be empty", "Please tell me your full name")
        
        # Enhanced name extraction and cleaning
        cleaned = value.strip()
        
        # Remove common speech-to-text artifacts
        cleaned = re.sub(r'my name is\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'i am\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'call me\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'it\'s\s*', '', cleaned, flags=re.IGNORECASE)
        
        # Extract name pattern - allow letters, spaces, hyphens, apostrophes
        name_match = re.search(r"[A-Za-z](?:[A-Za-z\s\-\'\.])*[A-Za-z]", cleaned)
        if name_match:
            cleaned = name_match.group(0).strip()
            # Clean up multiple spaces
            cleaned = re.sub(r'\s+', ' ', cleaned)
            
            if len(cleaned) >= 2:
                # Proper case formatting
                cleaned = ' '.join(word.capitalize() for word in cleaned.split())
                return ValidationResult(True, cleaned, "", "")
        
        return ValidationResult(False, "", "Please provide a valid name", "Use only letters, spaces, and hyphens")
    
    @staticmethod
    def validate_email(value: str) -> ValidationResult:
        if not value or not value.strip():
            return ValidationResult(False, "", "Email cannot be empty", "Please provide your email address")
        
        # SUPER AGGRESSIVE email cleaning for speech-to-text
        cleaned = value.lower().strip()
        
        # Handle "at the rate" patterns aggressively
        cleaned = re.sub(r'\bat\s*the\s*rate\b', '@', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bat\s*rate\b', '@', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bthe\s*rate\b', '@', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'rate\s*([a-zA-Z])', r'@\1', cleaned, flags=re.IGNORECASE)
        
        # Handle cases where @ gets converted to "at" 
        cleaned = re.sub(r'(\w+)\s*at\s*([a-zA-Z]+\.com)', r'\1@\2', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'(\w+)\s*(\d+)\s*at\s*([a-zA-Z]+\.com)', r'\1\2@\3', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'(\w+)\s*(\d+)\s*at\s*the\s*rate\s*([a-zA-Z]+\.com)', r'\1\2@\3', cleaned, flags=re.IGNORECASE)
        
        # Handle "No no actually it is Nayan at the rate gmail.com"
        cleaned = re.sub(r'no\s+no\s+actually\s+it\s+is\s+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'actually\s+it\s+is\s+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'my\s+email\s+(is\s+|addresses?\s+)', '', cleaned, flags=re.IGNORECASE)
        
        # Handle dot patterns more aggressively
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
                return ValidationResult(False, "", "Email must contain @ symbol", "Please provide complete email like: name@gmail.com")
            elif '.' not in cleaned.split('@')[1] if '@' in cleaned else False:
                return ValidationResult(False, "", "Email must contain domain", "Please use format: name@example.com")
            else:
                return ValidationResult(False, "", "Invalid email format", "Please use format: name@example.com")
        
        return ValidationResult(True, cleaned, "", "")
    
    @staticmethod
    def validate_phone(value: str) -> ValidationResult:
        if not value or not value.strip():
            return ValidationResult(False, "", "Phone number cannot be empty", "Please provide your phone number")
        
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
            return ValidationResult(False, "", "Phone number too short", "Please provide at least 7 digits")
        
        if len(digits) > 15:
            return ValidationResult(False, "", "Phone number too long", "Please provide a valid phone number")
        
        # Format for US numbers
        if len(digits) == 10:
            formatted = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            formatted = f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        else:
            formatted = f"+{digits}"
        
        return ValidationResult(True, formatted, "", "")
    
    @staticmethod
    def validate_password(value: str) -> ValidationResult:
        if not value or not value.strip():
            return ValidationResult(False, "", "Password cannot be empty", "Please provide your password")
        
        cleaned = value.strip()
        
        # Basic password validation - can be enhanced based on requirements
        if len(cleaned) < 6:
            return ValidationResult(False, "", "Password too short", "Password must be at least 6 characters long")
        
        if len(cleaned) > 128:
            return ValidationResult(False, "", "Password too long", "Password must be less than 128 characters")
        
        # Note: For security, we should validate but not store passwords in plain text
        # This is just basic validation - actual password handling should be secure
        return ValidationResult(True, cleaned, "", "")
    
    @staticmethod
    def validate_date(value: str) -> ValidationResult:
        """Validate and parse date inputs in various formats"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Validating date input: '{value}'")

        if not value or not value.strip():
            return ValidationResult(False, "", "Date cannot be empty", "Please provide the date, e.g., 'January 1, 2000' or '01/01/2000'")

        cleaned = value.strip().lower()

        import calendar
        import datetime as dt

        # Month mappings
        month_names = {month.lower(): idx for idx, month in enumerate(calendar.month_name[1:], 1)}
        month_abbrev = {month.lower(): idx for idx, month in enumerate(calendar.month_abbr[1:], 1)}
        all_months = {**month_names, **month_abbrev}

        # Comprehensive date patterns
        date_patterns = [
            (r'(\d{1,2})(st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*,?\s*(\d{2,4})', 'day_month_year'),
            (r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2})(st|nd|rd|th)?\s*,?\s*(\d{2,4})', 'month_day_year'),
            (r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', 'numeric_slash'),
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', 'iso'),
            (r'(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*,?\s*(\d{2,4})', 'short_day_month_year'),
            (r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2})\s*,?\s*(\d{2,4})', 'short_month_day_year'),
        ]

        for pattern, pattern_type in date_patterns:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match:
                try:
                    groups = match.groups()
                    day, month, year = None, None, None

                    if pattern_type == 'day_month_year':
                        day = int(groups[0])
                        month = all_months[groups[2].lower()]
                        year = int(groups[3])
                    elif pattern_type == 'month_day_year':
                        month = all_months[groups[0].lower()]
                        day = int(groups[1])
                        year = int(groups[3])
                    elif pattern_type == 'numeric_slash':
                        month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                    elif pattern_type == 'iso':
                        year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                    elif pattern_type == 'short_day_month_year':
                        day = int(groups[0])
                        month = all_months[groups[1].lower()]
                        year = int(groups[2])
                    elif pattern_type == 'short_month_day_year':
                        month = all_months[groups[0].lower()]
                        day = int(groups[1])
                        year = int(groups[2])

                    # Handle two-digit years
                    if year < 100:
                        current_year = dt.datetime.now().year % 100
                        century = 2000 if year <= current_year + 10 else 1900
                        year += century

                    # Validate date
                    if month and day and year:
                        if not (1 <= month <= 12):
                            continue
                        if not (1 <= day <= 31):
                            continue
                        if not (1900 <= year <= dt.datetime.now().year + 10):
                            continue

                        try:
                            dt.date(year, month, day)
                            formatted_date = f"{month:02d}/{day:02d}/{year}"
                            logger.info(f"Validated date: '{value}' -> '{formatted_date}'")
                            return ValidationResult(True, formatted_date, "", "")
                        except ValueError:
                            logger.warning(f"Invalid date components: {year}-{month}-{day}")
                            return ValidationResult(
                                False,
                                "",
                                "Invalid date (e.g., February 30 is not valid)",
                                "Please provide a valid date like 'January 1, 2000' or '01/01/2000'"
                            )

                except (ValueError, IndexError, KeyError) as e:
                    logger.warning(f"Error parsing date '{value}': {e}")
                    continue

        logger.warning(f"Failed to parse date: '{value}'")
        return ValidationResult(
            False,
            "",
            "Invalid date format",
            "Please use a format like 'January 1, 2000', '01/01/2000', 'Jan 1 2000', or '2000-01-01'"
        )
        """Validate and parse date inputs in various formats"""
        if not value or not value.strip():
            return ValidationResult(False, "", "Date cannot be empty", "Please provide the date, e.g., 'January 1, 2000' or '01/01/2000'")

        cleaned = value.strip().lower()

        import calendar
        import datetime as dt

        # Month mappings
        month_names = {month.lower(): idx for idx, month in enumerate(calendar.month_name[1:], 1)}
        month_abbrev = {month.lower(): idx for idx, month in enumerate(calendar.month_abbr[1:], 1)}
        all_months = {**month_names, **month_abbrev}

        # Comprehensive date patterns
        date_patterns = [
            # Natural language: "January 1st 2004", "1 January 2004", "Jan 1, 2004"
            (r'(\d{1,2})(st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*,?\s*(\d{2,4})', 'day_month_year'),
            (r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2})(st|nd|rd|th)?\s*,?\s*(\d{2,4})', 'month_day_year'),
            # Numeric formats: "01/01/2004", "01-01-2004", "1/1/04"
            (r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', 'numeric_slash'),
            # ISO format: "2004-01-01"
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', 'iso'),
            # Short formats: "1 Jan 2004", "Jan 1 2004"
            (r'(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*,?\s*(\d{2,4})', 'short_day_month_year'),
            (r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2})\s*,?\s*(\d{2,4})', 'short_month_day_year'),
        ]

        for pattern, pattern_type in date_patterns:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match:
                try:
                    groups = match.groups()
                    day, month, year = None, None, None

                    if pattern_type == 'day_month_year':
                        day = int(groups[0])
                        month = all_months[groups[2].lower()]
                        year = int(groups[3])
                    elif pattern_type == 'month_day_year':
                        month = all_months[groups[0].lower()]
                        day = int(groups[1])
                        year = int(groups[3])
                    elif pattern_type == 'numeric_slash':
                        month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                    elif pattern_type == 'iso':
                        year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                    elif pattern_type == 'short_day_month_year':
                        day = int(groups[0])
                        month = all_months[groups[1].lower()]
                        year = int(groups[2])
                    elif pattern_type == 'short_month_day_year':
                        month = all_months[groups[0].lower()]
                        day = int(groups[1])
                        year = int(groups[2])

                    # Handle two-digit years
                    if year < 100:
                        current_year = dt.datetime.now().year % 100
                        century = 2000 if year <= current_year + 10 else 1900
                        year += century

                    # Validate date
                    if month and day and year:
                        if not (1 <= month <= 12):
                            continue
                        if not (1 <= day <= 31):
                            continue
                        if not (1900 <= year <= dt.datetime.now().year + 10):
                            continue

                        # Validate actual date
                        try:
                            dt.date(year, month, day)
                            formatted_date = f"{month:02d}/{day:02d}/{year}"
                            return ValidationResult(True, formatted_date, "", "")
                        except ValueError:
                            return ValidationResult(
                                False,
                                "",
                                "Invalid date (e.g., February 30 is not valid)",
                                "Please provide a valid date like 'January 1, 2000' or '01/01/2000'"
                            )

                except (ValueError, IndexError, KeyError):
                    continue

        # Fallback for partial dates or invalid formats
        return ValidationResult(
            False,
            "",
            "Invalid date format",
            "Please use a format like 'January 1, 2000', '01/01/2000', 'Jan 1 2000', or '2000-01-01'"
        )
        if not value or not value.strip():
            return ValidationResult(False, "", "Date cannot be empty", "Please provide the date")
        
        cleaned = value.strip()
        
        # Enhanced natural date parsing with better context awareness
        import calendar
        month_names = {month.lower(): idx for idx, month in enumerate(calendar.month_name[1:], 1)}
        month_abbrev = {month.lower(): idx for idx, month in enumerate(calendar.month_abbr[1:], 1)}
        all_months = {**month_names, **month_abbrev}
        
        # Enhanced date patterns with more comprehensive matching
        date_patterns = [
            # Natural language patterns like "22nd December 2004", "December 22nd 2004"
            (r'(\d{1,2})(st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*(\d{4})', 'day_month_year'),
            (r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2})(st|nd|rd|th)?\s*(\d{4})', 'month_day_year'),
            # Date with just day after month/year context: "December 2004" + "22"
            (r'(\d{1,2})(?:\s*$)', 'day_only'),
            # Standard formats
            (r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', 'numeric'),
            (r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2}),?\s*(\d{4})', 'month_day_comma_year'),
            # ISO format
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', 'iso'),
        ]
        
        # Try each pattern
        for pattern, pattern_type in date_patterns:
            match = re.search(pattern, cleaned.lower(), re.IGNORECASE)
            if match:
                try:
                    groups = match.groups()
                    day, month, year = None, None, None
                    
                    if pattern_type == 'day_month_year':
                        day = int(groups[0])
                        month = all_months[groups[2].lower()]
                        year = int(groups[3])
                    
                    elif pattern_type == 'month_day_year':
                        month = all_months[groups[0].lower()]
                        day = int(groups[1])
                        year = int(groups[3])
                    
                    elif pattern_type == 'day_only':
                        # Extract day only - assume previous context has month/year
                        day = int(groups[0])
                        # For day-only, we need to use a default or error
                        if 1 <= day <= 31:
                            return ValidationResult(False, "", "Please provide the complete date", "I need the full date including month and year")
                    
                    elif pattern_type == 'numeric':
                        # Assume MM/DD/YYYY format
                        month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                    
                    elif pattern_type == 'month_day_comma_year':
                        month = all_months[groups[0].lower()]
                        day = int(groups[1])
                        year = int(groups[2])
                    
                    elif pattern_type == 'iso':
                        year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                    
                    # Validate date components
                    if month and day and year:
                        # Validate ranges
                        if not (1 <= month <= 12):
                            continue
                        if not (1 <= day <= 31):
                            continue
                        if not (1900 <= year <= datetime.now().year + 10):
                            continue
                        
                        # Validate actual date (handles month-specific day limits)
                        try:
                            import datetime as dt
                            dt.date(year, month, day)
                            formatted_date = f"{month:02d}/{day:02d}/{year}"
                            return ValidationResult(True, formatted_date, "", "")
                        except ValueError:
                            continue
                        
                except (ValueError, IndexError, KeyError):
                    continue
        
        return ValidationResult(False, "", "Invalid date format", "Please use format like 'January 1, 2000', '01/01/2000', or 'January 1st, 2000'")

class EnhancedDynamicFormConversation:
    """Enhanced conversational form handler with LLM integration"""
    
    def __init__(self, form_id: str, session_state: SessionState):
        self.form_id = form_id
        self.session = session_state
        self.form_schema = form_store.get_form(form_id)
        
        if not self.form_schema:
            raise ValueError(f"Form {form_id} not found")
        
        # Enhanced session management - create form-specific session context
        self._initialize_form_session()
        
        # Initialize LLM with enhanced system prompt
        self.model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=self._get_enhanced_system_prompt()
        )
        
        self.validator = AdvancedValidator()
        self.intent_classifier = IntentClassifier()
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.5
    
    def _initialize_form_session(self):
        """Initialize form-specific session context to avoid cross-form contamination"""
        
        # Create form-specific context namespace
        form_context_key = f"form_{self.form_id}"
        
        if form_context_key not in self.session.context:
            self.session.context[form_context_key] = {
                "form_id": self.form_id,
                "form_title": self.form_schema.title,
                "conversation_started": False,
                "fields_initialized": False,
                "current_field_index": 0,
                "user_name": None,
                "conversation_style": "friendly"
            }
        
        # Initialize form fields if not done
        if not self.session.context[form_context_key].get("fields_initialized"):
            for field in self.form_schema.fields:
                field_key = f"{form_context_key}_{field.name}"
                if field_key not in self.session.fields:
                    self.session.update_field(
                        field_key, 
                        None, 
                        FieldStatus.PENDING
                    )
            self.session.context[form_context_key]["fields_initialized"] = True
    
    def _get_form_context_key(self) -> str:
        """Get the form-specific context key"""
        return f"form_{self.form_id}"
    
    def _get_field_key(self, field_name: str) -> str:
        """Get form-specific field key"""
        return f"{self._get_form_context_key()}_{field_name}"
    
    def _get_enhanced_system_prompt(self) -> str:
        """Get enhanced system prompt for this specific form"""
        
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
You are an intelligent, friendly, and personable conversational assistant helping users fill out the form: "{self.form_schema.title}".

FORM FIELDS TO COLLECT:
{chr(10).join(fields_info)}

PERSONALITY & STYLE:
- Natural, conversational, and personable (not robotic)
- Use the user's name when you learn it
- Vary your responses - avoid repetitive phrases
- Show empathy and understanding
- Keep responses concise but warm
- Celebrate progress and completion

FIELD PROCESSING RULES:
1. NORMALIZATION: Clean speech-to-text errors aggressively
   - "at the rate" → "@"
   - "dot com" → ".com" 
   - "3 times 5" → "555"
   - Natural date formats accepted

2. VALIDATION: Extract and validate field values strictly
   - Names: Extract proper names from conversational text
   - Emails: Handle speech-to-text email errors
   - Phones: Format consistently, handle repetition patterns like "3 times 5" → "555"
   - Dates: CONTEXT AWARE - Remember previous month/year mentions. Accept "22" if December 2004 was mentioned before
   - Passwords: Validate but remind users to type manually for security
   - MCQ/Checkboxes: Must match provided options exactly

3. EXTRACTION: Pull relevant info from any part of user's message
   - If user mentions multiple fields, extract all
   - Handle corrections like "fix my email" or "change my name"
   - Support removal requests like "remove my phone number"

CONVERSATION MANAGEMENT:
- Ask for ONE field at a time unless user provides multiple
- Handle field corrections immediately when requested
- ASK FOR NON-REQUIRED FIELDS TOO: Don't skip optional fields automatically - ask user if they want to provide them
- Allow users to skip non-required fields when they explicitly refuse
- Politely insist on required fields
- Remember user's name and use it naturally
- Provide encouraging feedback
- For non-required fields, use phrases like "This field is optional, but would you like to provide...?"

RESPONSE FORMAT (JSON ONLY):
{{
  "action": "ask" | "set" | "done" | "clarify" | "correct" | "remove",
  "updates": {{"field_name": "cleaned_value or null if removed"}},
  "ask": "Your natural, personalized response",
  "field_focus": "current_field_name",
  "tone": "friendly" | "encouraging" | "apologetic" | "professional"
}}

Remember: Be conversational, helpful, and make the form-filling experience pleasant!
"""
    
    def get_next_field(self) -> Optional[FormField]:
        """Get the next field that needs to be filled"""
        form_context_key = self._get_form_context_key()
        
        # Sort fields by order
        sorted_fields = sorted(self.form_schema.fields, key=lambda f: f.order)
        
        for field in sorted_fields:
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
    
    def process_user_input(self, user_text: str) -> Dict[str, Any]:
        """Enhanced user input processing with LLM integration"""
        form_context_key = self._get_form_context_key()
        
        # Log session state for debugging
        logger.info(f"Processing input for session {self.session.session_id}, form {self.form_id}, conversation_started: {self.session.context.get(form_context_key, {}).get('conversation_started')}, input: '{user_text}'")
        
        # Always check for conversation start
        if not self.session.context[form_context_key].get("conversation_started"):
            self.session.context[form_context_key]["conversation_started"] = True
            first_field = self.get_next_field()
            logger.info(f"Next field: {first_field.name if first_field else None}")
            if first_field:
                response = {
                    "action": "ask",
                    "updates": {},
                    "ask": self._generate_field_question_text(first_field),
                    "field_focus": first_field.name,
                    "tone": "friendly",
                    "reply": self._generate_field_question_text(first_field)  # Ensure reply is set
                }
                logger.info(f"Starting conversation, asking: {response['ask']}")
                return response
        
        # Clean and normalize input
        cleaned_input = clean_speech_input(user_text)
        
        # Classify user intent
        current_field = self.get_next_field()
        intent = self.intent_classifier.classify_intent(cleaned_input, current_field.name if current_field else None)
        if intent["type"] == "skip" and current_field and not current_field.validation.required:
            field_key = self._get_field_key(current_field.name)
            self.session.update_field(field_key, None, FieldStatus.COLLECTED)
            next_field = self.get_next_field()
            if next_field:
                return {
                    "action": "ask",
                    "updates": {},
                    "ask": self._generate_field_question_text(next_field),
                    "field_focus": next_field.name,
                    "tone": "friendly"
                }
            else:
                return {
                    "action": "done",
                    "updates": {},
                    "ask": f"Perfect! I've collected all the information. {self.form_schema.confirmation_message}",
                    "field_focus": None,
                    "tone": "success"
                }
        # Build context for LLM
        context = self._build_llm_context(cleaned_input, intent, current_field)
        
        # Get LLM response
        try:
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
            
            # Process field updates with validation
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
    
    def _build_llm_context(self, user_input: str, intent: Dict[str, Any], current_field: Optional[FormField]) -> Dict[str, Any]:
        """Build comprehensive context for LLM with enhanced date context tracking"""
        
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
        
        # Get conversation history with more context for date fields
        conversation_history = self.session.get_conversation_context(10)  # More history for context
        
        # Enhanced date context extraction
        date_context = self._extract_date_context_from_history(conversation_history)
        
        return {
            "form_info": {
                "title": self.form_schema.title,
                "description": self.form_schema.description
            },
            "field_states": field_states,
            "current_field": current_field.name if current_field else None,
            "user_input": user_input,
            "user_intent": intent,
            "conversation_history": conversation_history,
            "date_context": date_context,  # Enhanced date context
            "form_context": self.session.context.get(form_context_key, {}),
            "completion_status": self.get_completion_status()
        }
    
    def _extract_date_context_from_history(self, conversation_history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Extract date-related context from conversation history"""
        import calendar
        
        month_names = {month.lower(): idx for idx, month in enumerate(calendar.month_name[1:], 1)}
        month_abbrev = {month.lower(): idx for idx, month in enumerate(calendar.month_abbr[1:], 1)}
        all_months = {**month_names, **month_abbrev}
        
        date_context = {
            "mentioned_month": None,
            "mentioned_year": None,
            "partial_date_info": None
        }
        
        # Look through recent conversation for date mentions
        for msg in reversed(conversation_history):  # Most recent first
            content = msg.get('content', '').lower()
            
            # Look for month mentions
            for month_name, month_num in all_months.items():
                if month_name in content:
                    date_context["mentioned_month"] = {
                        "name": month_name,
                        "number": month_num
                    }
                    break
            
            # Look for year mentions
            year_match = re.search(r'\b(19|20)\d{2}\b', content)
            if year_match:
                date_context["mentioned_year"] = int(year_match.group())
            
            # If we found both month and year, we can note partial info
            if date_context["mentioned_month"] and date_context["mentioned_year"]:
                date_context["partial_date_info"] = f"{date_context['mentioned_month']['name']} {date_context['mentioned_year']}"
                break
        
        return date_context
    
    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """Parse LLM JSON response with fallback handling"""
        
        try:
            return json.loads(response_text.strip())
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON in the text
        json_patterns = [
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
            r'\{.*\}',
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, response_text, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
        
        # Fallback response
        logger.warning(f"Failed to parse LLM response: {response_text[:200]}...")
        return {
            "action": "ask",
            "updates": {},
            "ask": "I had trouble understanding. Could you please rephrase that?",
            "field_focus": None,
            "tone": "apologetic",
            "reply": "I had trouble understanding. Could you please rephrase that?"
        }
    
    def _process_field_updates(self, llm_response: Dict[str, Any], current_field: Optional[FormField]) -> Dict[str, Any]:
        """Process and validate field updates from LLM response"""
        updates = llm_response.get("updates", {})
        validated_updates = {}
        validation_errors = {}
        
        logger.info(f"Processing updates: {updates}")
        
        # Validate each field update
        for field_name, value in updates.items():
            if value is not None and str(value).strip():
                # Find the field schema
                field_schema = next((f for f in self.form_schema.fields if f.name == field_name), None)
                
                if field_schema:
                    validation_result = self._validate_field_value(field_schema, str(value))
                    logger.info(f"Validation for {field_name}: is_valid={validation_result.is_valid}, "
                            f"cleaned_value={validation_result.cleaned_value}, "
                            f"error={validation_result.error_message}")
                    
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
            error_response = {
                "action": "ask",
                "updates": {},
                "ask": f"{error_info['error']}. {error_info['suggestion']}",
                "field_focus": field_name,
                "tone": "helpful",
                "reply": f"{error_info['error']}. {error_info['suggestion']}"
            }
            logger.info(f"Validation error response: {error_response}")
            return error_response
        
        # Update response with validated data
        llm_response["updates"] = validated_updates
        
        # Check if form is complete
        next_field = self.get_next_field()
        logger.info(f"Next field after updates: {next_field.name if next_field else None}")
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
        
        logger.info(f"Final processed response: {llm_response}")
        return llm_response
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
        completion_status = self.get_completion_status()
        if self.get_next_field() is None:
            llm_response.update({
                "action": "done",
                "ask": f"Perfect! I've collected all the required information. {self.form_schema.confirmation_message}",
                "field_focus": None,
                "tone": "success",
                "reply": f"Perfect! I've collected all the required information. {self.form_schema.confirmation_message}"
            })
        elif llm_response.get("action") == "set" and validated_updates:
            # Move to next field
            next_field = self.get_next_field()
            if next_field:
                llm_response["field_focus"] = next_field.name
                if not llm_response.get("ask"):
                    llm_response["ask"] = self._generate_field_question_text(next_field)
                    llm_response["reply"] = llm_response["ask"]
        
        return llm_response
    
    def _validate_field_value(self, field: FormField, value: str) -> ValidationResult:
        """Validate field value using appropriate validator"""
        
        if field.type == FieldType.SHORT_ANSWER and 'name' in field.name.lower():
            return self.validator.validate_full_name(value)
        elif field.type == FieldType.EMAIL:
            return self.validator.validate_email(value)
        elif field.type == FieldType.PHONE:
            return self.validator.validate_phone(value)
        elif field.type == FieldType.DATE:
            return self.validator.validate_date(value)
        elif field.type == FieldType.PASSWORD:
            return self.validator.validate_password(value)
        elif field.type in [FieldType.MULTIPLE_CHOICE, FieldType.DROPDOWN]:
            # Strict option matching
            if field.options and value not in field.options:
                return ValidationResult(
                    False, "", 
                    f"Please choose from the available options", 
                    f"Available options: {', '.join(field.options)}"
                )
        elif field.type == FieldType.CHECKBOXES:
            # Handle multiple selections
            if field.options:
                selected = value.split(',') if isinstance(value, str) else [value]
                invalid_options = [opt.strip() for opt in selected if opt.strip() not in field.options]
                if invalid_options:
                    return ValidationResult(
                        False, "", 
                        f"Invalid options: {', '.join(invalid_options)}", 
                        f"Available options: {', '.join(field.options)}"
                    )
        
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

# Alias for backward compatibility
DynamicFormConversation = EnhancedDynamicFormConversation