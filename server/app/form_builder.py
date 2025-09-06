"""
Dynamic Form Builder - Supports all Google Forms field types
"""
import json
import uuid
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

class FieldType(str, Enum):
    """All supported field types matching Google Forms"""
    SHORT_ANSWER = "short_answer"
    PARAGRAPH = "paragraph"
    MULTIPLE_CHOICE = "multiple_choice"
    CHECKBOXES = "checkboxes"
    DROPDOWN = "dropdown"
    FILE_UPLOAD = "file_upload"
    LINEAR_SCALE = "linear_scale"
    MULTIPLE_CHOICE_GRID = "multiple_choice_grid"
    CHECKBOX_GRID = "checkbox_grid"
    DATE = "date"
    TIME = "time"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
    NUMBER = "number"
    PASSWORD = "password"

class ValidationRule(BaseModel):
    """Validation rules for form fields"""
    required: bool = False
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    pattern: Optional[str] = None
    custom_error_message: Optional[str] = None

class FormField(BaseModel):
    """Dynamic form field definition"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: FieldType
    label: str
    description: Optional[str] = None
    placeholder: Optional[str] = None
    
    # Options for choice-based fields
    options: Optional[List[str]] = None
    
    # For grid fields
    rows: Optional[List[str]] = None
    columns: Optional[List[str]] = None
    
    # For linear scale
    scale_min: Optional[int] = None
    scale_max: Optional[int] = None
    scale_min_label: Optional[str] = None
    scale_max_label: Optional[str] = None
    
    # File upload settings
    allowed_file_types: Optional[List[str]] = None
    max_file_size_mb: Optional[int] = None
    
    # Validation
    validation: ValidationRule = Field(default_factory=ValidationRule)
    
    # Display settings
    order: int = 0
    section: Optional[str] = None
    help_text: Optional[str] = None

class FormSchema(BaseModel):
    """Complete form definition"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: Optional[str] = None
    fields: List[FormField]
    
    # Form settings
    allow_response_editing: bool = False
    collect_email: bool = False
    require_sign_in: bool = False
    
    # Submission settings
    confirmation_message: str = "Thank you for your response!"
    redirect_url: Optional[str] = None
    
    # Metadata
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    created_by: Optional[str] = None
    is_active: bool = True

class FormResponse(BaseModel):
    """User's response to a form"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    form_id: str
    session_id: str
    responses: Dict[str, Any]  # field_id -> response_value
    submitted_at: float = Field(default_factory=time.time)
    user_email: Optional[str] = None
    completion_time_seconds: Optional[int] = None

class FormStore:
    """In-memory storage for forms (replace with database in production)"""
    
    def __init__(self):
        self.forms: Dict[str, FormSchema] = {}
        self.responses: Dict[str, List[FormResponse]] = {}
    
    def create_form(self, form_data: Dict[str, Any]) -> FormSchema:
        """Create a new form"""
        form = FormSchema(**form_data)
        self.forms[form.id] = form
        self.responses[form.id] = []
        return form
    
    def get_form(self, form_id: str) -> Optional[FormSchema]:
        """Get form by ID"""
        return self.forms.get(form_id)
    
    def update_form(self, form_id: str, form_data: Dict[str, Any]) -> Optional[FormSchema]:
        """Update existing form"""
        if form_id not in self.forms:
            return None
        
        form_data['id'] = form_id
        form_data['updated_at'] = time.time()
        form = FormSchema(**form_data)
        self.forms[form_id] = form
        return form
    
    def delete_form(self, form_id: str) -> bool:
        """Delete form and all responses"""
        if form_id not in self.forms:
            return False
        
        del self.forms[form_id]
        if form_id in self.responses:
            del self.responses[form_id]
        return True
    
    def list_forms(self) -> List[FormSchema]:
        """List all forms"""
        return list(self.forms.values())
    
    def submit_response(self, response_data: Dict[str, Any]) -> FormResponse:
        """Submit a response to a form"""
        response = FormResponse(**response_data)
        form_id = response.form_id
        
        if form_id not in self.responses:
            self.responses[form_id] = []
        
        self.responses[form_id].append(response)
        return response
    
    def get_responses(self, form_id: str) -> List[FormResponse]:
        """Get all responses for a form"""
        return self.responses.get(form_id, [])

# Global form store instance
form_store = FormStore()

# Predefined form templates
SAMPLE_FORMS = {
    "student_registration": {
        "title": "Student Registration Form",
        "description": "Complete registration for new students",
        "fields": [
            {
                "name": "full_name",
                "type": "short_answer",
                "label": "Full Name",
                "validation": {"required": True},
                "order": 1
            },
            {
                "name": "email",
                "type": "email", 
                "label": "Email Address",
                "validation": {"required": True},
                "order": 2
            },
            {
                "name": "phone",
                "type": "phone",
                "label": "Phone Number",
                "validation": {"required": True},
                "order": 3
            },
            {
                "name": "program",
                "type": "dropdown",
                "label": "Program of Interest",
                "options": ["Computer Science", "Engineering", "Business", "Arts", "Other"],
                "validation": {"required": True},
                "order": 4
            },
            {
                "name": "experience",
                "type": "linear_scale",
                "label": "Rate your programming experience",
                "scale_min": 1,
                "scale_max": 10,
                "scale_min_label": "Beginner",
                "scale_max_label": "Expert",
                "order":5
            },
            {
                "name": "additional_info",
                "type": "paragraph",
                "label": "Additional Information",
                "description": "Tell us anything else you'd like us to know",
                "validation": {"required": False},
                "order": 8
            }
        ]
    },
    
    "feedback_survey": {
        "title": "Customer Feedback Survey",
        "description": "Help us improve our services",
        "fields": [
            {
                "name": "overall_satisfaction",
                "type": "linear_scale",
                "label": "Overall satisfaction with our service",
                "scale_min": 1,
                "scale_max": 5,
                "scale_min_label": "Very Unsatisfied",
                "scale_max_label": "Very Satisfied",
                "validation": {"required": True},
                "order": 1
            },
            {
                "name": "service_quality",
                "type": "multiple_choice",
                "label": "How would you rate our service quality?",
                "options": ["Excellent", "Good", "Average", "Poor", "Very Poor"],
                "validation": {"required": True},
                "order": 2
            },
            {
                "name": "recommend",
                "type": "multiple_choice",
                "label": "Would you recommend us to others?",
                "options": ["Definitely", "Probably", "Not sure", "Probably not", "Definitely not"],
                "validation": {"required": True},
                "order": 3
            },
            {
                "name": "comments",
                "type": "paragraph",
                "label": "Additional Comments",
                "description": "Please share any specific feedback or suggestions",
                "validation": {"required": False},
                "order": 5
            }
        ]
    }
}

def initialize_sample_forms():
    """Initialize the form store with sample forms"""
    for form_key, form_data in SAMPLE_FORMS.items():
        form_store.create_form(form_data)

# Initialize sample forms
initialize_sample_forms()