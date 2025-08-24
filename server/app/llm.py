import json
import os
import re
from typing import Dict, Any, List
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ---- SYSTEM PROMPT ----
SYSTEM = """
You are a conversational form-filling assistant.
You must collect: full_name, email, phone, dob.

### Personality & Tone:
- Be warm, natural, and human-like. Imagine you are chatting with a friend.
- Keep responses short, friendly, and specific to the current field.
- Never sound robotic or repetitive.

### Rules:
- You are responsible for validating user inputs (name, email, phone, dob).
- If input is invalid, explain politely *only about that field* and give a quick example.
  Example: "That doesn’t look like a valid email — it should look like name@example.com. Could you try again?"
- Do NOT repeat already captured info unless the user explicitly asks to change it.
- If the user asks to correct a field, respond ONLY about that field and confirm once it looks good.
- If user asks to change a field, allow correction and acknowledge naturally. 
  Example: "Got it, I’ve updated your email."
- Only mark "done" when all fields are valid and filled.

### STRICT Response format (always JSON only, no text outside JSON):
{
  "action": "ask" | "set" | "done" | "error",
  "updates": { "<field_name>": "<value>" },
  "ask": "<next question or clarification in a warm, human tone>"
}
Return ONLY the JSON object. Do not add ```json or any extra text.
"""

# -------------------
# Python-side Validators
# -------------------
def validate_field(field: str, value: str) -> bool:
    """Strict validation for each field type."""
    if field == "full_name":
        return bool(re.match(r"^[A-Za-z ]{2,}$", value.strip()))
    if field == "email":
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value.strip()))
    if field == "phone":
        return bool(re.match(r"^\+?\d{7,15}$", value.strip().replace(" ", "")))
    if field == "dob":
        return bool(re.match(r"^(0[1-9]|1[0-2])[/-](0[1-9]|[12]\d|3[01])[/-]\d{4}$", value.strip()))
    return True


class GeminiLLM:
    def __init__(self, model_name: str = "gemini-2.0-flash-lite"):
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY missing in environment.")
        self.model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=SYSTEM
        )

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Directly parse JSON, fallback if wrapped in extra text."""
        try:
            return json.loads(text)
        except Exception:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
            return {
                "action": "error",
                "updates": {},
                "ask": f"Sorry, invalid response (not JSON): {text[:120]}"
            }

    def infer(self, fields: List[dict], state: Dict[str, Any], user_text: str) -> Dict[str, Any]:
        """Delegate flow control to LLM + enforce Python validation."""
        try:
            context = {
                "fields": fields,
                "current_state": state,
                "user_message": user_text,
            }

            response = self.model.generate_content(
                json.dumps(context),
                generation_config={
                    "temperature": 0.3,
                    "top_p": 0.9
                }
            )

            text = (response.text or "").strip()
            parsed = self._extract_json(text)

            # ---- Extra Safety: Python Validation ----
            updates = parsed.get("updates", {})
            safe_updates = {}

            for field, value in updates.items():
                if validate_field(field, value):
                    safe_updates[field] = value
                else:
                    # Reject invalid update, force re-ask for that field
                    return {
                        "action": "ask",
                        "updates": {},
                        "ask": f"That doesn’t look like a valid {field.replace('_',' ')}. Could you try again?"
                    }

            parsed["updates"] = safe_updates
            return parsed

        except Exception as e:
            return {
                "action": "error",
                "updates": {},
                "ask": f"System error: {e}"
            }

    def infer_freeform(self, prompt: str) -> str:
        """Optional freeform mode (not strict JSON)."""
        try:
            response = self.model.generate_content(prompt)
            return (response.text or "").strip()
        except Exception:
            return "Service temporarily unavailable."
