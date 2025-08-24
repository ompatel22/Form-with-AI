from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional

class STTResponse(BaseModel):
    text: str

class StartFormRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    schema: Dict[str, Any]  # dynamic schema: {"fields":[{...}]}
    generate_audio: bool = False

class StartFormResponse(BaseModel):
    session_id: str
    agent_reply: Optional[str]
    audio_b64: Optional[str] = None
    form_state: Dict[str, Any]
    is_complete: bool

class TurnRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    user_text: Optional[str] = None
    audio_b64: Optional[str] = None
    generate_audio: bool = False

class TurnResponse(BaseModel):
    agent_reply: str
    audio_b64: Optional[str] = None
    form_state: Dict[str, Any]
    is_complete: bool

class ResetRequest(BaseModel):
    session_id: str