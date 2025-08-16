import re
from datetime import datetime
from typing import Dict, Any, Optional

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

def validate_value(ftype: str, value: str, field: Dict[str, Any]) -> Optional[str]:
    """Return None if OK, else error message."""
    req = field.get("required", False)
    v = (value or "").strip()

    if req and not v:
        return f"{field['name']} is required."

    if not v:
        return None  # allow empty if not required

    if ftype in ("string", "text"):
        pattern = field.get("pattern")
        if pattern and not re.match(pattern, v):
            return f"Invalid format for {field['name']}."
        return None

    if ftype == "email":
        return None if EMAIL_RE.match(v) else "Invalid email format."

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
        fmt = field.get("format", "%Y-%m-%d")
        try:
            datetime.strptime(v, fmt)
            return None
        except ValueError:
            return f"Date must match format {fmt}."

    if ftype == "enum":
        opts = field.get("enum", [])
        return None if v in opts else f"Value must be one of: {', '.join(opts)}."

    return None  # default OK
