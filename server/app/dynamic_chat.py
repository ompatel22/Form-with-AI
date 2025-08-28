"""
Dynamic Conversational Form Handler
"""
import json
import re
from typing import Dict, Any, List, Optional
from .form_builder import FormSchema, FormField, FieldType, form_store
from .validators import validate_value, clean_speech_input
from .memory import SessionState, FieldStatus, MessageRole

class DynamicFormConversation:
    """Handles conversational form filling for any dynamic form"""
    
    def __init__(self, form_id: str, session_state: SessionState):
        self.form_id = form_id
        self.session = session_state
        self.form_schema = form_store.get_form(form_id)
        
        if not self.form_schema:
            raise ValueError(f"Form {form_id} not found")
        
        # Initialize fields in session if not already done
        self._initialize_form_fields()
    
    def _initialize_form_fields(self):
        """Initialize all form fields in session state"""
        for field in self.form_schema.fields:
            if field.name not in self.session.fields:
                self.session.update_field(
                    field.name, 
                    None, 
                    FieldStatus.PENDING
                )
    
    def get_next_field(self) -> Optional[FormField]:
        """Get the next field that needs to be filled"""
        field_summary = self.session.get_field_summary()
        
        # Sort fields by order
        sorted_fields = sorted(self.form_schema.fields, key=lambda f: f.order)
        
        for field in sorted_fields:
            field_status = field_summary.get(field.name, {})
            if field_status.get('status') in ['pending', 'invalid', None]:
                return field
        
        return None
    
    def get_completion_status(self) -> Dict[str, Any]:
        """Get form completion status"""
        field_summary = self.session.get_field_summary()
        
        total_required = sum(1 for f in self.form_schema.fields if f.validation.required)
        completed_required = sum(
            1 for f in self.form_schema.fields 
            if f.validation.required and field_summary.get(f.name, {}).get('status') == 'collected'
        )
        
        total_fields = len(self.form_schema.fields)
        completed_fields = sum(
            1 for f in self.form_schema.fields 
            if field_summary.get(f.name, {}).get('status') == 'collected'
        )
        
        return {
            "total_fields": total_fields,
            "completed_fields": completed_fields,
            "total_required": total_required,
            "completed_required": completed_required,
            "is_complete": completed_required >= total_required,
            "progress_percentage": (completed_fields / total_fields) * 100 if total_fields > 0 else 0
        }
    
    def process_user_input(self, user_text: str) -> Dict[str, Any]:
        """Process user input and return conversation response"""
        
        # Clean speech input
        cleaned_input = clean_speech_input(user_text)
        
        # Check for corrections or field references
        correction_response = self._handle_corrections(cleaned_input)
        if correction_response:
            return correction_response
        
        # Get current field to focus on
        current_field = self.get_next_field()
        
        if not current_field:
            # Form is complete
            return self._generate_completion_response()
        
        # Process input for current field
        return self._process_field_input(current_field, cleaned_input)
    
    def _handle_corrections(self, user_text: str) -> Optional[Dict[str, Any]]:
        """Handle user corrections and field references"""
        lower_text = user_text.lower()
        
        # Check for correction keywords
        correction_patterns = [
            (r'fix|correct|change|update|modify', 'correction'),
            (r'remove|delete|clear', 'removal'),
            (r'go back|previous', 'navigation')
        ]
        
        for pattern, intent in correction_patterns:
            if re.search(pattern, lower_text):
                return self._handle_correction_intent(user_text, intent)
        
        # Check for specific field references
        for field in self.form_schema.fields:
            field_keywords = [field.name.lower(), field.label.lower()]
            
            # Add common variations
            if 'email' in field.name.lower():
                field_keywords.extend(['email', 'e-mail', 'mail'])
            elif 'phone' in field.name.lower():
                field_keywords.extend(['phone', 'number', 'contact'])
            elif 'name' in field.name.lower():
                field_keywords.extend(['name'])
            
            for keyword in field_keywords:
                if keyword in lower_text:
                    return self._handle_field_specific_input(field, user_text)
        
        return None
    
    def _handle_correction_intent(self, user_text: str, intent: str) -> Dict[str, Any]:
        """Handle correction intentions"""
        
        if intent == 'correction':
            # Try to extract field and new value from text
            field, new_value = self._extract_correction_from_text(user_text)
            if field:
                return self._update_field_value(field, new_value)
        
        elif intent == 'removal':
            # Find field to remove
            field = self._find_field_in_text(user_text)
            if field:
                self.session.update_field(field.name, None, FieldStatus.PENDING)
                return {
                    "action": "removed",
                    "updates": {field.name: None},
                    "ask": f"Removed your {field.label.lower()}. Would you like to enter a new one?",
                    "field_focus": field.name,
                    "tone": "helpful"
                }
        
        return {
            "action": "clarify",
            "updates": {},
            "ask": "I'd like to help you make changes. Which field would you like to update?",
            "field_focus": None,
            "tone": "helpful"
        }
    
    def _extract_correction_from_text(self, text: str) -> tuple[Optional[FormField], Optional[str]]:
        """Extract field and correction value from user text"""
        
        # Look for patterns like "fix my email to john@gmail.com"
        correction_patterns = [
            r'(?:fix|correct|change|update)\s+(?:my\s+)?(\w+)\s+(?:to|with)\s+(.+)',
            r'my\s+(\w+)\s+should\s+be\s+(.+)',
            r'(\w+)\s+is\s+(?:actually|really)\s+(.+)'
        ]
        
        for pattern in correction_patterns:
            match = re.search(pattern, text.lower())
            if match:
                field_keyword = match.group(1)
                new_value = match.group(2).strip()
                
                # Find matching field
                for field in self.form_schema.fields:
                    if (field_keyword in field.name.lower() or 
                        field_keyword in field.label.lower()):
                        return field, new_value
        
        return None, None
    
    def _find_field_in_text(self, text: str) -> Optional[FormField]:
        """Find field mentioned in text"""
        lower_text = text.lower()
        
        for field in self.form_schema.fields:
            if (field.name.lower() in lower_text or 
                field.label.lower() in lower_text):
                return field
        
        return None
    
    def _handle_field_specific_input(self, field: FormField, user_text: str) -> Dict[str, Any]:
        """Handle input specifically for a field"""
        
        # Extract value from text for this field
        value = self._extract_field_value_from_text(field, user_text)
        
        if value:
            return self._update_field_value(field, value)
        else:
            # Ask for the field value
            return self._generate_field_question(field)
    
    def _extract_field_value_from_text(self, field: FormField, text: str) -> Optional[str]:
        """Extract field value from user text"""
        
        if field.type == FieldType.EMAIL:
            # Look for email patterns
            email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', text)
            return email_match.group(0) if email_match else None
        
        elif field.type == FieldType.PHONE:
            # Look for phone patterns
            phone_match = re.search(r'[\d\s\-\(\)]{7,}', text)
            return phone_match.group(0).strip() if phone_match else None
        
        elif field.type in [FieldType.SHORT_ANSWER, FieldType.PARAGRAPH]:
            # For names and text fields, try to extract meaningful text
            if 'name' in field.name.lower():
                # Extract name-like patterns
                name_match = re.search(r'\b[A-Za-z]+(?: [A-Za-z]+)*\b', text)
                return name_match.group(0) if name_match else None
        
        elif field.type in [FieldType.MULTIPLE_CHOICE, FieldType.DROPDOWN]:
            # Look for matching options
            if field.options:
                text_lower = text.lower()
                for option in field.options:
                    if option.lower() in text_lower:
                        return option
        
        return None
    
    def _process_field_input(self, field: FormField, user_text: str) -> Dict[str, Any]:
        """Process input for a specific field"""
        
        # Try to extract/validate value
        extracted_value = self._extract_field_value_from_text(field, user_text)
        
        if not extracted_value:
            extracted_value = user_text.strip()
        
        if extracted_value:
            return self._update_field_value(field, extracted_value)
        else:
            return self._generate_field_question(field)
    
    def _update_field_value(self, field: FormField, value: str) -> Dict[str, Any]:
        """Update field value with validation"""
        
        # Convert field to validation format
        validation_field = {
            "name": field.name,
            "required": field.validation.required,
            "pattern": field.validation.pattern,
            "min": field.validation.min_value,
            "max": field.validation.max_value,
            "enum": field.options or [],
            "options": field.options or []
        }
        
        # Validate the value
        error_message = validate_value(field.type.value, value, validation_field)
        
        if error_message:
            return {
                "action": "ask",
                "updates": {},
                "ask": f"{error_message} Please try again.",
                "field_focus": field.name,
                "tone": "helpful"
            }
        
        # Value is valid, update field
        self.session.update_field(field.name, value, FieldStatus.COLLECTED)
        
        # Check if form is complete
        completion_status = self.get_completion_status()
        
        if completion_status["is_complete"]:
            return self._generate_completion_response()
        else:
            # Move to next field
            next_field = self.get_next_field()
            if next_field:
                return {
                    "action": "set",
                    "updates": {field.name: value},
                    "ask": self._generate_field_question_text(next_field),
                    "field_focus": next_field.name,
                    "tone": "encouraging"
                }
        
        return {
            "action": "set",
            "updates": {field.name: value},
            "ask": "Great! What else would you like to update?",
            "field_focus": None,
            "tone": "encouraging"
        }
    
    def _generate_field_question(self, field: FormField) -> Dict[str, Any]:
        """Generate question for a specific field"""
        return {
            "action": "ask",
            "updates": {},
            "ask": self._generate_field_question_text(field),
            "field_focus": field.name,
            "tone": "friendly"
        }
    
    def _generate_field_question_text(self, field: FormField) -> str:
        """Generate question text for a field"""
        
        base_question = field.label
        if not base_question.endswith('?'):
            base_question = f"What's your {base_question.lower()}?"
        
        # Add field-specific context
        if field.type == FieldType.MULTIPLE_CHOICE and field.options:
            options_text = ", ".join(field.options)
            return f"{base_question} Choose from: {options_text}"
        
        elif field.type == FieldType.CHECKBOXES and field.options:
            options_text = ", ".join(field.options)
            return f"{base_question} You can select multiple: {options_text}"
        
        elif field.type == FieldType.LINEAR_SCALE:
            return f"{base_question} Rate from {field.scale_min} ({field.scale_min_label or 'lowest'}) to {field.scale_max} ({field.scale_max_label or 'highest'})"
        
        elif field.type == FieldType.DATE:
            return f"{base_question} Please provide the date (MM/DD/YYYY)"
        
        elif field.type == FieldType.EMAIL:
            return f"{base_question} Please provide your email address"
        
        elif field.type == FieldType.PHONE:
            return f"{base_question} Please provide your phone number"
        
        # Add description if available
        if field.description:
            return f"{base_question} {field.description}"
        
        return base_question
    
    def _generate_completion_response(self) -> Dict[str, Any]:
        """Generate response when form is complete"""
        completion_status = self.get_completion_status()
        
        return {
            "action": "done",
            "updates": {},
            "ask": f"Perfect! I've collected all the required information. {self.form_schema.confirmation_message}",
            "field_focus": None,
            "tone": "success",
            "completion_status": completion_status
        }
    
    def get_form_summary(self) -> Dict[str, Any]:
        """Get summary of current form state"""
        field_summary = self.session.get_field_summary()
        completion_status = self.get_completion_status()
        
        return {
            "form_id": self.form_id,
            "form_title": self.form_schema.title,
            "fields": field_summary,
            "completion_status": completion_status,
            "next_field": self.get_next_field().name if self.get_next_field() else None
        }