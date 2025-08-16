from typing import Dict, Any, Optional
from .validators import validate_value

class DynamicDialog:
    """
    Drives the dialog strictly by the runtime schema.
    Schema shape:
    {
      "fields": [
        {"name":"full_name","question":"What is your full name?","type":"string","required":true},
        {"name":"email","question":"Email?","type":"email","required":true,"pattern":"..."},
        ...
      ]
    }
    """
    def __init__(self, schema: Dict[str, Any]):
        self.fields = list(schema.get("fields", []))
        self.field_order = [f["name"] for f in self.fields]
        self.index = 0
        self.form: Dict[str, Any] = {}
        self.completed = False

    def current_field(self) -> Optional[Dict[str, Any]]:
        if self.index >= len(self.fields):
            return None
        return self.fields[self.index]

    def next_question(self) -> Optional[str]:
        f = self.current_field()
        return f.get("question") if f else None

    def set_updates(self, updates: Dict[str, Any]) -> Optional[str]:
        """Apply one or more field updates. Returns first error string or None."""
        for k, v in updates.items():
            # update only if allowed by schema
            f = next((x for x in self.fields if x["name"] == k), None)
            if not f:
                return f"Unknown field: {k}"
            err = validate_value(f.get("type", "string"), str(v), f)
            if err:
                return err
            self.form[k] = str(v)
        self._advance_index()
        return None

    def confirm_or_ask(self) -> str:
        if self.is_complete():
            self.completed = True
            return "All fields captured. Do you want to submit?"
        q = self.next_question()
        return q or "All fields captured."

    def is_complete(self) -> bool:
        # complete if all required are present and valid
        for f in self.fields:
            name = f["name"]
            if f.get("required", False) and not self.form.get(name):
                return False
        return True

    def _advance_index(self):
        # move index to next unanswered required field
        while self.index < len(self.fields):
            name = self.fields[self.index]["name"]
            if name not in self.form:
                break
            self.index += 1
