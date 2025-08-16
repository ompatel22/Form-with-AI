import json
from typing import Dict, Any
from openai import OpenAI
from .config import settings

SYSTEM = (
    "You are a precise form-filling assistant. "
    "Given: (1) a list of allowed fields with types, (2) current form state, (3) user text, "
    "decide what to do. Output ONLY a JSON object with keys: action, updates, ask.\n"
    "- action ∈ ['ask','set','confirm','done','error']\n"
    "- updates: object mapping field=>value (strings) you want to set/correct\n"
    "- ask: next question to ask (if action='ask' or 'confirm'), else ''\n"
    "Never include commentary or markdown—ONLY JSON."
)

class OpenAILLM:
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY missing.")
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-3.5-turbo"

    def infer(self, fields: list[dict], state: Dict[str, Any], user_text: str) -> Dict[str, Any]:
        content = {
            "fields": [
                {k: v for k, v in f.items() if k in {"name","type","required","pattern","min","max","enum","format"}}
                for f in fields
            ],
            "state": state,
            "user": user_text,
        }

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": json.dumps(content, ensure_ascii=False)},
                ],
            )
            txt = resp.choices[0].message.content.strip()
            print("LLM raw output:", txt)
            return json.loads(txt)
        except Exception as e:
            print("LLM error:", str(e))
            return {"action": "ask", "updates": {}, "ask": "Service temporarily unavailable. Please try again."}