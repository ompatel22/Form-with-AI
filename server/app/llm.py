import json
import os
import re
import time
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass

from .memory import FieldStatus, MessageRole

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    is_valid: bool
    cleaned_value: str = ""
    error_message: str = ""
    suggestion: str = ""

class IntentClassifier:
    """Classifies user intent from their response"""
    
    REFUSAL_PATTERNS = [
        r'\b(no|nope|not|dont|don\'t|wont|won\'t|refuse|skip)\b',
        r'\b(i (will not|wont|won\'t|dont want|don\'t want))\b',
        r'\b(skip (it|this|that))\b',
        r'\b(next question)\b',
        r'\b(move on)\b'
    ]
    
    CORRECTION_PATTERNS = [
        r'\b(actually|correction|correct|fix|change|update|mistake)\b',
        r'\b(that\'s wrong|thats wrong|not right|incorrect)\b'
    ]
    
    CLARIFICATION_PATTERNS = [
        r'\b(what|why|how|which|where|when)\b.*\?',
        r'\b(explain|tell me|what do you mean)\b'
    ]

    @staticmethod
    def classify_intent(text: str, current_field: str = None) -> Dict[str, Any]:
        text_lower = text.lower().strip()
        
        intent = {
            "type": "answer",  # answer, refusal, correction, clarification, irrelevant
            "confidence": 0.5,
            "contains_data": False,
            "field_specific": current_field,
            "metadata": {}
        }
        
        # Check for refusal
        for pattern in IntentClassifier.REFUSAL_PATTERNS:
            if re.search(pattern, text_lower):
                intent["type"] = "refusal"
                intent["confidence"] = 0.9
                return intent
        
        # Check for correction
        for pattern in IntentClassifier.CORRECTION_PATTERNS:
            if re.search(pattern, text_lower):
                intent["type"] = "correction"
                intent["confidence"] = 0.8
                return intent
        
        # Check for clarification request
        for pattern in IntentClassifier.CLARIFICATION_PATTERNS:
            if re.search(pattern, text_lower):
                intent["type"] = "clarification"
                intent["confidence"] = 0.8
                return intent
        
        # Check if contains potential data
        if current_field:
            if IntentClassifier._contains_field_data(text, current_field):
                intent["contains_data"] = True
                intent["confidence"] = 0.8
        
        return intent

    @staticmethod
    def _contains_field_data(text: str, field_type: str) -> bool:
        """Check if text contains data relevant to field type"""
        text = text.lower().strip()
        
        if field_type == "email":
            return "@" in text or "email" in text or ".com" in text
        elif field_type == "phone":
            return any(char.isdigit() for char in text) and len([c for c in text if c.isdigit()]) >= 7
        elif field_type == "full_name":
            # Check for name-like patterns (2+ letters, possibly with space)
            return bool(re.search(r'\b[A-Za-z]{2,}\b', text)) and not text.isdigit()
        elif field_type == "dob":
            return bool(re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', text)) or any(month in text for month in ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'])
        
        return False

class AdvancedValidator:
    """Production-grade field validation with detailed feedback"""
    
    @staticmethod
    def validate_full_name(value: str) -> ValidationResult:
        if not value or not value.strip():
            return ValidationResult(False, "", "Name cannot be empty", "Please enter your full name")
        
        cleaned = re.sub(r'\s+', ' ', value.strip()).title()
        
        # Basic pattern check
        if not re.match(r"^[A-Za-z\s\-\'\.]{2,50}$", cleaned):
            return ValidationResult(False, "", "Name contains invalid characters", "Please use only letters, spaces, hyphens, and apostrophes")
        
        # Must have at least 2 parts or be a single name with 2+ chars
        parts = cleaned.split()
        if len(parts) == 1 and len(cleaned) < 2:
            return ValidationResult(False, "", "Name too short", "Please enter at least 2 characters")
        
        # Check for obviously fake names
        fake_patterns = [r'test', r'asdf', r'qwerty', r'1234', r'abcd']
        if any(re.search(pattern, cleaned.lower()) for pattern in fake_patterns):
            return ValidationResult(False, "", "Please enter a real name", "This looks like a test input")
        
        return ValidationResult(True, cleaned, "", "")

    # @staticmethod
    # def validate_email(value: str) -> ValidationResult:
    #     if not value or not value.strip():
    #         return ValidationResult(False, "", "Email cannot be empty", "Please enter your email address")
        
    #     # Clean up common speech-to-text errors
    #     cleaned = value.lower().strip()
    #     cleaned = re.sub(r'\s+', '', cleaned)  # Remove all spaces
    #     cleaned = re.sub(r'\bat\b', '@', cleaned)  # "at" -> "@"
    #     cleaned = re.sub(r'\bdot\b', '.', cleaned)  # "dot" -> "."
    #     cleaned = re.sub(r'gmail\.com$', '@gmail.com', cleaned)  # Fix "name gmail.com"
        
    #     # Handle common patterns like "john 123 gmail com"
    #     if ' ' in cleaned and '@' not in cleaned:
    #         parts = cleaned.split()
    #         if len(parts) >= 3 and ('gmail' in parts or 'yahoo' in parts or 'hotmail' in parts):
    #             # Reconstruct email
    #             name = parts[0]
    #             domain_parts = [p for p in parts[1:] if not p.isdigit()]
    #             if domain_parts:
    #                 cleaned = f"{name}@{'.'.join(domain_parts)}"
        
    #     # Basic email regex
    #     email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    #     if not re.match(email_pattern, cleaned):
    #         return ValidationResult(False, "", "Invalid email format", "Please use format: name@example.com")
        
    #     # Check for common domains
    #     valid_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com']
    #     domain = cleaned.split('@')[1].lower()
        
    #     return ValidationResult(True, cleaned, "", "")

    @staticmethod
    def validate_email(value: str) -> ValidationResult:
        if not value or not value.strip():
            return ValidationResult(False, "", "Email cannot be empty", "Please enter your email address")
        
        # ENHANCED cleaning for speech-to-text errors
        cleaned = value.lower().strip()
        cleaned = re.sub(r'\s+', '', cleaned)  # Remove ALL spaces first
        
        # Handle "at the rate" and "at rate" patterns
        cleaned = re.sub(r'attherate|atrate|at_the_rate|at_rate', '@', cleaned)
        cleaned = re.sub(r'at', '@', cleaned)  # Simple "at" replacement
        
        # Handle "dot" patterns  
        cleaned = re.sub(r'dotcom|dot_com', '.com', cleaned)
        cleaned = re.sub(r'dot', '.', cleaned)
        
        # Fix specific patterns like "om358227@gmailcom" -> "om358227@gmail.com"
        cleaned = re.sub(r'@gmailcom$', '@gmail.com', cleaned)
        cleaned = re.sub(r'@yahoocom$', '@yahoo.com', cleaned)
        
        # Handle incomplete emails like "om358227" -> try to detect if it's email-ish
        if '@' not in cleaned and len(cleaned) > 3 and not cleaned.endswith('.com'):
            # Don't auto-fix, let user provide complete email
            return ValidationResult(False, "", "Email must contain @ and domain", "Please provide complete email like: name@gmail.com")
        
        # Basic email regex - more permissive
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, cleaned):
            return ValidationResult(False, "", "Invalid email format", "Please use format: name@example.com")
        
        return ValidationResult(True, cleaned, "", "")

    @staticmethod
    def validate_phone(value: str) -> ValidationResult:
        if not value or not value.strip():
            return ValidationResult(False, "", "Phone number cannot be empty", "Please enter your phone number")
        
        # Extract digits only
        digits = re.sub(r'\D', '', value)
        
        if len(digits) < 7:
            return ValidationResult(False, "", "Phone number too short", "Please enter at least 7 digits")
        
        if len(digits) > 15:
            return ValidationResult(False, "", "Phone number too long", "Please enter a valid phone number")
        
        # Format for US numbers
        if len(digits) == 10:
            formatted = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            formatted = f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        else:
            formatted = f"+{digits}"
        
        return ValidationResult(True, formatted, "", "")

    @staticmethod
    def validate_dob(value: str) -> ValidationResult:
        if not value or not value.strip():
            return ValidationResult(False, "", "Date of birth cannot be empty", "Please enter your date of birth (MM/DD/YYYY)")
        
        # Try to parse various date formats
        date_patterns = [
            (r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', '%m/%d/%Y'),
            (r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', '%Y/%m/%d'),
            (r'(\d{1,2})\s+(\d{1,2})\s+(\d{4})', '%m %d %Y')
        ]
        
        for pattern, date_format in date_patterns:
            match = re.search(pattern, value)
            if match:
                try:
                    if date_format == '%m/%d/%Y':
                        month, day, year = match.groups()
                    elif date_format == '%Y/%m/%d':
                        year, month, day = match.groups()
                    else:
                        month, day, year = match.groups()
                    
                    # Validate ranges
                    month, day, year = int(month), int(day), int(year)
                    
                    if not (1 <= month <= 12):
                        return ValidationResult(False, "", "Invalid month", "Month must be 1-12")
                    if not (1 <= day <= 31):
                        return ValidationResult(False, "", "Invalid day", "Day must be 1-31")
                    if year < 1900 or year > datetime.now().year:
                        return ValidationResult(False, "", "Invalid year", f"Year must be between 1900 and {datetime.now().year}")
                    
                    # Check if date is in the future
                    birth_date = datetime(year, month, day)
                    if birth_date > datetime.now():
                        return ValidationResult(False, "", "Future date not allowed", "Birth date cannot be in the future")
                    
                    # Check if person would be too old (150+ years)
                    if datetime.now().year - year > 150:
                        return ValidationResult(False, "", "Invalid birth year", "Please enter a realistic birth year")
                    
                    formatted = f"{month:02d}/{day:02d}/{year}"
                    return ValidationResult(True, formatted, "", "")
                
                except ValueError:
                    continue
        
        return ValidationResult(False, "", "Invalid date format", "Please use MM/DD/YYYY format")

ENHANCED_SYSTEM = """
You are a smart, empathetic conversational assistant that helps users fill a form with: full_name, email, phone, dob.

PERSONALITY:
- Conversational, brief, and natural
- Avoid repeating collected information unless explicitly requested
- Use casual confirmations: "Got it!", "Thanks!", "Perfect!", "Fixed!", "Removed!"
- Only ask for the NEXT pending field; never summarize all fields
- Respond immediately to corrections or removal requests

NEVER SAY:
- "I have your name as X, email as Y..." (robotic)
- Long confirmations listing multiple fields
- Repetitive apologies or filler text

CRITICAL MEMORY RULES:
- ALWAYS check conversation history before asking
- NEVER request info already collected
- Update or remove fields immediately if user requests it
- Track which fields are complete vs pending
- Handle "go back" and "remove" commands gracefully
- Always prioritize corrections/removals over asking the next field

FIELD COMPLETION TRACKING:
- Track each field as: pending, collected, removed, refused, invalid
- Before asking for a field, check if already collected
- If removed, mark as pending again until replaced

HANDLING CORRECTIONS:
1. PHONE: Support "append X", "replace X" instructions
2. EMAIL: Clean up speech-to-text errors, handle typos, accept corrections
3. DOB: Accept natural formats like "22nd December 2004", "12/22/2004"
4. REMOVALS: If user asks to remove a field, confirm with "Removed!" and set it back to pending

CONVERSATION AWARENESS:
- Respond naturally to: "you got my X wrong", "change my Y", "remove my Z", "go back to W"
- Always shift focus to the field the user mentions
- Never force the next field if user wants to correct or remove something

RESPONSE RULES:
- Keep responses short, natural, and casual
- Only confirm the field being processed
- If user asks for removal: confirm removal, then ask if they want to re-enter it
- Move conversation forward only when the user is done correcting
- NEVER repeat all fields unless explicitly asked

RESPONSE FORMAT (JSON ONLY):
{
  "action": "ask" | "set" | "done" | "clarify" | "correct" | "remove",
  "updates": {"field_name": "cleaned_value or null if removed"},
  "ask": "SHORT, natural response focused ONLY on current field",
  "field_focus": "current_field_name",
  "tone": "casual" | "apologetic" | "professional"
}

EXAMPLES:
- "Got it! What's your phone number?"
- "Perfect! Now your date of birth?"
- "Fixed! What's your correct email?"
- "Removed! Do you want to enter a new email?"
- NOT: "I have your name as X, email as Y, phone as Z..."
"""

class GeminiLLM:
    def __init__(self, model_name: str = "gemini-2.0-flash"):
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY missing in environment.")
        
        self.model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=ENHANCED_SYSTEM
        )
        self.validator = AdvancedValidator()
        self.intent_classifier = IntentClassifier()
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.5  # Minimum 500ms between requests

    def _rate_limit(self):
        """Simple rate limiting"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Robust JSON extraction with fallbacks"""
        try:
            # First, try direct parsing
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON in the text
        json_patterns = [
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Simple nested
            r'\{.*\}',  # Greedy match
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
        
        # Last resort - construct error response
        logger.warning(f"Failed to parse LLM response: {text[:200]}...")
        return {
            "action": "error",
            "updates": {},
            "ask": "I had trouble understanding. Could you please rephrase?",
            "field_focus": None,
            "tone": "apologetic"
        }

    def _validate_field_update(self, field_name: str, value: str) -> ValidationResult:
        """Validate a field value using appropriate validator"""
        validators = {
            "full_name": self.validator.validate_full_name,
            "email": self.validator.validate_email,
            "phone": self.validator.validate_phone,
            "dob": self.validator.validate_dob
        }
        
        validator_func = validators.get(field_name)
        if not validator_func:
            return ValidationResult(True, value, "", "")
        
        return validator_func(value)

    def infer(self, fields: List[dict], session_state, user_text: str) -> Dict[str, Any]:
        """Enhanced inference with full context awareness"""
        try:
            self._rate_limit()
            
            # Classify user intent first
            current_field = session_state.current_field
            intent = self.intent_classifier.classify_intent(user_text, current_field)
            
            # Build comprehensive context
            context = {
                "form_fields": fields,
                "current_field_states": session_state.get_field_summary(),
                "conversation_history": session_state.get_conversation_context(),
                "user_message": user_text,
                "user_intent": intent,
                "session_context": {
                    "frustration_level": session_state.context.get("user_frustration_level", 0),
                    "total_refusals": session_state.context.get("total_refusals", 0),
                    "conversation_phase": session_state.context.get("conversation_phase", "collecting"),
                    "current_field": current_field
                }
            }
            
            # Generate response with retry logic
            response = None
            for attempt in range(3):
                try:
                    response = self.model.generate_content(
                        json.dumps(context, indent=2),
                        generation_config={
                            "temperature": 0.3,
                            "top_p": 0.9,
                            "max_output_tokens": 2048
                        }
                    )
                    break
                except Exception as e:
                    logger.warning(f"LLM attempt {attempt + 1} failed: {e}")
                    if attempt == 2:
                        raise
                    time.sleep(1)
            
            if not response or not response.text:
                raise Exception("Empty response from LLM")
            
            # Parse response
            parsed = self._extract_json(response.text)
            
            # Validate any field updates
            updates = parsed.get("updates", {})
            validated_updates = {}
            validation_errors = {}
            
            for field_name, value in updates.items():
                if value and value.strip():
                    validation_result = self._validate_field_update(field_name, value)
                    
                    if validation_result.is_valid:
                        validated_updates[field_name] = validation_result.cleaned_value
                    else:
                        validation_errors[field_name] = {
                            "error": validation_result.error_message,
                            "suggestion": validation_result.suggestion
                        }
            
            # If we have validation errors, modify the response
            if validation_errors:
                field_name = list(validation_errors.keys())[0]
                error_info = validation_errors[field_name]
                
                parsed.update({
                    "action": "ask",
                    "updates": {},
                    "ask": f"{error_info['error']}. {error_info['suggestion']}",
                    "field_focus": field_name,
                    "tone": "helpful"
                })
            else:
                parsed["updates"] = validated_updates
            
            return parsed
            
        except Exception as e:
            logger.error(f"LLM inference error: {e}")
            return {
                "action": "error",
                "updates": {},
                "ask": "I'm having a technical issue. Could you please repeat that?",
                "field_focus": current_field,
                "tone": "apologetic"
            }

    def infer_freeform(self, prompt: str) -> str:
        """Freeform inference for non-structured queries"""
        try:
            self._rate_limit()
            response = self.model.generate_content(prompt)
            return response.text.strip() if response and response.text else "I couldn't process that request."
        except Exception as e:
            logger.error(f"Freeform inference error: {e}")
            return "I'm experiencing technical difficulties. Please try again."