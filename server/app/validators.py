import re
from datetime import datetime
from typing import Dict, Any, Optional

# Enhanced email regex that's more permissive
EMAIL_RE = re.compile(r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$")

def clean_speech_input(value: str) -> str:
    """Clean common speech-to-text errors"""
    if not value:
        return value
    
    cleaned = value.strip()
    
    # SUPER AGGRESSIVE email normalization fixes  
    # Handle "at the rate" patterns first
    cleaned = re.sub(r'\bat\s*the\s*rate\b', '@', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bat\s*rate\b', '@', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bthe\s*rate\b', '@', cleaned, flags=re.IGNORECASE)
    
    # Handle patterns like "Om Patel 2212 at the rate gmail.com"
    cleaned = re.sub(r'(\w+\s+\w+)\s+(\d+)\s+at\s+the\s+rate\s+([a-zA-Z]+\.com)', r'\1\2@\3', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'(\w+)\s+(\d+)\s+at\s+the\s+rate\s+([a-zA-Z]+\.com)', r'\1\2@\3', cleaned, flags=re.IGNORECASE)
    
    # General "at" to "@" conversion (only if no @ exists)
    if '@' not in cleaned:
        cleaned = re.sub(r'(\w+)\s*at\s*([a-zA-Z]+)', r'\1@\2', cleaned, flags=re.IGNORECASE)
    
    # Dot corrections
    cleaned = re.sub(r'\bdot\s*com\b', '.com', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bdot\s*gmail\s*com\b', '.gmail.com', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bgmail\s*dot\s*com\b', 'gmail.com', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bdot\s*', '.', cleaned, flags=re.IGNORECASE)
    
    # Fix common domain patterns
    cleaned = re.sub(r'gmail\s*com', 'gmail.com', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'yahoo\s*com', 'yahoo.com', cleaned, flags=re.IGNORECASE)
    
    # Remove extra spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned

def validate_value(ftype: str, value: str, field: Dict[str, Any]) -> Optional[str]:
    """Enhanced validation with better speech-to-text handling."""
    req = field.get("required", False)
    v = (value or "").strip()
    
    # Clean speech-to-text errors first
    v = clean_speech_input(v)

    if req and not v:
        return f"{field['name']} is required."

    if not v:
        return None  # allow empty if not required

    if ftype in ("string", "text", "short_answer", "paragraph"):
        # More permissive name validation - allow numbers in names too
        if field.get("name") == "full_name" or "name" in field.get("name", "").lower():
            # Allow letters, spaces, hyphens, apostrophes, periods, and numbers
            if not re.match(r"^[A-Za-z0-9\s\-\'\.\u00C0-\u017F]+$", v):
                return "Name contains invalid characters. Please use only letters, spaces, hyphens, and apostrophes"
            if len(v.strip()) < 1:
                return "Name cannot be empty."
        
        pattern = field.get("pattern")
        if pattern and not re.match(pattern, v):
            return f"Invalid format for {field['name']}."
        return None

    if ftype == "email":
        # Enhanced email validation with aggressive speech-to-text cleanup
        email_cleaned = v.lower().replace(' ', '')
        
        # Apply our enhanced cleaning first
        email_cleaned = clean_speech_input(email_cleaned)
        
        # Handle patterns where domain gets concatenated without @
        if '@' not in email_cleaned and ('gmail' in email_cleaned or 'yahoo' in email_cleaned or 'hotmail' in email_cleaned):
            # Try to split and reconstruct email
            for domain in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']:
                domain_part = domain.replace('.com', '')
                if domain_part in email_cleaned:
                    parts = email_cleaned.split(domain_part)
                    if len(parts) == 2 and parts[0]:
                        email_cleaned = f"{parts[0]}@{domain}"
                        break
        
        # Handle incomplete domain patterns
        if '@gmail' in email_cleaned and not email_cleaned.endswith('.com'):
            email_cleaned = email_cleaned.replace('@gmail', '@gmail.com')
        if '@yahoo' in email_cleaned and not email_cleaned.endswith('.com'):
            email_cleaned = email_cleaned.replace('@yahoo', '@yahoo.com')
            
        if not EMAIL_RE.match(email_cleaned):
            # More helpful error message
            if '@' not in email_cleaned:
                return "Invalid email format. Please use format: name@example.com"
            elif '.' not in email_cleaned.split('@')[1] if '@' in email_cleaned else False:
                return "Email must contain a domain. Please use format: name@example.com" 
            else:
                return "Invalid email format. Please use format: name@example.com"
        return None

    if ftype == "phone":
        # Extract only digits for phone validation
        digits_only = re.sub(r'\D', '', v)
        if len(digits_only) < 7:
            return "Phone number must have at least 7 digits."
        if len(digits_only) > 15:
            return "Phone number is too long."
        return None

    if ftype == "integer":
        try:
            iv = int(v)
            if "min" in field and iv < field["min"]:
                return f"Value must be >= {field['min']}."
            if "max" in field and iv > field["max"]:
                return f"Value must be <= {field['max']}."
            return None
        except ValueError:
            return "Please enter a valid integer."

    if ftype == "number":
        try:
            fv = float(v)
            if "min" in field and fv < field["min"]:
                return f"Value must be >= {field['min']}."
            if "max" in field and fv > field["max"]:
                return f"Value must be <= {field['max']}."
            return None
        except ValueError:
            return "Please enter a valid number."

    if ftype == "date":
        # Try multiple date formats
        date_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y"]
        for fmt in date_formats:
            try:
                datetime.strptime(v, fmt)
                return None
            except ValueError:
                continue
        return "Invalid date format. Try MM/DD/YYYY or YYYY-MM-DD"

    if ftype in ("enum", "multiple_choice", "dropdown"):
        opts = field.get("options", field.get("enum", []))
        return None if v in opts else f"Value must be one of: {', '.join(opts)}."

    if ftype == "url":
        url_pattern = r'https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?'
        if not re.match(url_pattern, v, re.IGNORECASE):
            return "Please enter a valid URL starting with http:// or https://"
        return None

    return None  # default OK