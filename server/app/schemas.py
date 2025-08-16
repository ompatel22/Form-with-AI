from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional

class STTResponse(BaseModel):
    text: str

class StartFormRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    schema: Dict[str, Any]  # dynamic schema: {"fields":[{...}]}

class StartFormResponse(BaseModel):
    session_id: str
    next_question: Optional[str]
    is_complete: bool

class TurnRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    user_text: str = Field(..., min_length=1)

class TurnResponse(BaseModel):
    agent_reply: str
    audio_url: Optional[str] = None
    form_state: Dict[str, Any]
    is_complete: bool

class ResetRequest(BaseModel):
    session_id: str
