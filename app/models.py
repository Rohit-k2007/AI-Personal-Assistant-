from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TranscriptTurn(BaseModel):
    speaker: str  # 'ai' or 'caller'
    text: str


class CallBase(BaseModel):
    caller_name: Optional[str] = "Unknown"
    caller_number: Optional[str] = "+91 98765 00000"
    category: Optional[str] = "Unknown"  # Important, Personal, Work, Unknown, Suspected Spam
    status: Optional[str] = "completed"  # incoming, screening, completed, missed, flagged
    urgency: Optional[str] = "Not confirmed"  # High, Medium, Low, Not confirmed
    purpose: Optional[str] = ""
    message: Optional[str] = ""
    suggested_action: Optional[str] = "Call back when available."
    summary_text: Optional[str] = ""
    transcript_json: Optional[str] = "[]"
    duration_sec: Optional[int] = 0
    is_spam_suspected: Optional[int] = 0
    owner_decision: Optional[str] = "pending"


class CallCreate(CallBase):
    pass


class CallResponse(CallBase):
    id: str
    created_at: str


class DecisionUpdate(BaseModel):
    decision: str = Field(..., description="accept, decline, callback_requested, or pending")


class SimulateStepRequest(BaseModel):
    caller_phone: Optional[str] = "+91 98123 45678"
    step_index: int = 0
    caller_text: Optional[str] = None
    transcript: List[TranscriptTurn] = []
    extracted_state: Optional[Dict[str, Any]] = None


class SimulateStepResponse(BaseModel):
    next_question: str
    is_finished: bool = False
    is_follow_up: bool = False
    step_index: int
    extracted_state: Dict[str, Any]
    summary: Optional[str] = None
    category: Optional[str] = None
    urgency: Optional[str] = None
    suggested_action: Optional[str] = None
    call_id: Optional[str] = None


class SettingsUpdate(BaseModel):
    settings: Dict[str, str]


class HealthCheckResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    provider: str
    demo_mode: bool
    owner_phone: str
    database: str


class SimulateIncomingRequest(BaseModel):
    caller_number: Optional[str] = "+91 98123 45678"
    caller_name: Optional[str] = "Unknown"
    language: Optional[str] = "en"


class SimulateIncomingResponse(BaseModel):
    status: str
    session_id: str
    greeting: str
    step_index: int
    demo_mode: bool
    caller_number: str


class CallSummaryResponse(BaseModel):
    call_id: str
    caller_name: str
    caller_number: str
    caller_number_masked: str
    category: str
    status: str
    urgency: str
    purpose: str
    message: str
    suggested_action: str
    summary_text: str
    created_at: str
    duration_sec: int
    is_spam_suspected: bool
    owner_decision: str
