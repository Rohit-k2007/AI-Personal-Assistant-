import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.ai_screener import AIScreener
from app.database import (
    delete_call,
    get_all_calls,
    get_all_settings,
    get_call_by_id,
    get_call_summary,
    get_dashboard_metrics,
    init_db,
    mask_phone_number,
    save_call,
    update_call_decision,
    update_settings,
)
from app.models import (
    CallCreate,
    CallResponse,
    CallSummaryResponse,
    DecisionUpdate,
    HealthCheckResponse,
    SettingsUpdate,
    SimulateIncomingRequest,
    SimulateIncomingResponse,
    SimulateStepRequest,
    SimulateStepResponse,
)
from app.telephony_adapter import get_telephony_adapter

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

# In-memory session store for live incoming webhook calls (keyed by CallSid)
active_webhook_sessions: Dict[str, Dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database on startup
    init_db()
    yield


app = FastAPI(
    title="Personal AI Call Assistant",
    description="AI-powered call-screening assistant for unanswered calls. Screens callers, records purpose and urgency, generates structured summaries, and sends notifications.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------- HEALTH & SYSTEM ROUTES ----------------


@app.get("/health", response_model=HealthCheckResponse)
@app.get("/api/health", response_model=HealthCheckResponse)
def health_check():
    """
    Health check endpoint for container monitoring, uptime checks, and integration readiness.
    """
    settings = get_all_settings()
    provider_type = settings.get("telephony_provider", os.getenv("TELEPHONY_PROVIDER", "simulated"))
    adapter = get_telephony_adapter(provider_type)
    owner_phone = settings.get("owner_phone", os.getenv("OWNER_PHONE", "+91 8094725777"))

    return HealthCheckResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
        provider=adapter.provider_name,
        demo_mode=adapter.is_demo_mode,
        owner_phone=mask_phone_number(owner_phone),
        database="connected (sqlite3 / call_assistant.db)",
    )


# ---------------- TELEPHONY WEBHOOK ROUTES ----------------


@app.post("/api/telephony/webhook")
@app.post("/api/webhooks/voice")
async def telephony_voice_webhook(
    request: Request,
    x_twilio_signature: Optional[str] = Header(None, alias="X-Twilio-Signature"),
):
    """
    Primary incoming voice webhook for telephony providers (Twilio Voice, Exotel).
    Receives caller speech input, drives the 4-question screening conversation in English,
    validates provider signatures, and generates TwiML / response markup.
    """
    settings = get_all_settings()
    provider_type = settings.get("telephony_provider", os.getenv("TELEPHONY_PROVIDER", "simulated"))
    language = settings.get("active_language", os.getenv("ASSISTANT_LANGUAGE", "en"))
    screener = AIScreener(
        provider=settings.get("ai_provider", "local_nlp"),
        language=language,
    )

    # Parse payload (form-urlencoded from Twilio or JSON)
    content_type = request.headers.get("content-type", "")
    params: Dict[str, Any] = {}
    if "application/x-www-form-urlencoded" in content_type:
        form_data = await request.form()
        params = dict(form_data)
    elif "application/json" in content_type:
        try:
            params = await request.json()
        except Exception:
            params = {}
    else:
        params = dict(request.query_params)

    # Resolve provider adapter: if CallSid/SpeechResult or twilio header present, use TwilioAdapter
    req_provider = params.get("provider") or request.headers.get("x-telephony-provider")
    if not req_provider:
        if "CallSid" in params or "SpeechResult" in params or x_twilio_signature:
            req_provider = "twilio"
        else:
            req_provider = provider_type
    adapter = get_telephony_adapter(req_provider)

    # Validate provider webhook cryptographic signature
    full_url = str(request.url)
    if not adapter.validate_webhook_signature(x_twilio_signature, full_url, params):
        raise HTTPException(
            status_code=403,
            detail="Invalid carrier webhook signature. Unauthorized request.",
        )

    call_sid = params.get("CallSid") or params.get("call_id") or f"call-{int(datetime.now(timezone.utc).timestamp())}"
    caller_phone = params.get("From") or params.get("CallFrom") or "+91 98123 45678"
    speech_result = params.get("SpeechResult") or params.get("TranscriptionText") or params.get("text")

    # Retrieve or create multi-turn conversation session
    session = active_webhook_sessions.get(call_sid)
    callback_path = "/api/telephony/webhook"

    if not session:
        # Step 0: New incoming call arrived
        step0_result = screener.process_step(step_index=0, caller_text=None, state={"language": language})
        active_webhook_sessions[call_sid] = {
            "step_index": 1,
            "caller_phone": caller_phone,
            "transcript": [{"speaker": "ai", "text": step0_result["next_question"]}],
            "extracted_state": step0_result["extracted_state"],
            "start_time": datetime.now(timezone.utc),
        }

        voice_response = adapter.generate_voice_response(
            text=step0_result["next_question"],
            callback_url=callback_path,
            listen=True,
            is_final=False,
            language="en-IN" if language == "en" else "hi-IN",
        )

        if isinstance(voice_response, str):
            return Response(content=voice_response, media_type="application/xml")
        return voice_response

    # Existing session: Advance to next screening turn
    current_step = session["step_index"]
    state = session["extracted_state"]
    transcript = session["transcript"]

    # Record caller's speech
    caller_text = speech_result or "No speech detected"
    transcript.append({"speaker": "caller", "text": caller_text})

    # Process step with AI Screener
    result = screener.process_step(
        step_index=current_step,
        caller_text=caller_text,
        state=state,
    )

    next_question = result["next_question"]
    is_finished = result["is_finished"]
    session["step_index"] = result["step_index"]
    session["extracted_state"] = result["extracted_state"]
    transcript.append({"speaker": "ai", "text": next_question})

    if is_finished:
        # Call completed: Generate summary & save to SQLite call history
        summary_data = screener.generate_final_summary(result["extracted_state"])
        duration = int((datetime.now(timezone.utc) - session["start_time"]).total_seconds())

        call_record = {
            "id": call_sid,
            "caller_name": summary_data["caller_name"],
            "caller_number": caller_phone,
            "category": summary_data["category"],
            "status": "flagged" if summary_data["urgency"] == "High" else "completed",
            "urgency": summary_data["urgency"],
            "purpose": summary_data["purpose"],
            "message": summary_data["message"],
            "suggested_action": summary_data["suggested_action"],
            "summary_text": summary_data["summary_text"],
            "transcript_json": json.dumps(transcript, ensure_ascii=False),
            "duration_sec": max(duration, 1),
            "is_spam_suspected": summary_data["is_spam_suspected"],
            "owner_decision": "pending",
        }
        save_call(call_record)
        # Clear in-memory session
        active_webhook_sessions.pop(call_sid, None)

        voice_response = adapter.generate_voice_response(
            text=next_question,
            callback_url=callback_path,
            listen=False,
            is_final=True,
            language="en-IN" if language == "en" else "hi-IN",
        )
    else:
        voice_response = adapter.generate_voice_response(
            text=next_question,
            callback_url=callback_path,
            listen=True,
            is_final=False,
            language="en-IN" if language == "en" else "hi-IN",
        )

    if isinstance(voice_response, str):
        return Response(content=voice_response, media_type="application/xml")
    return voice_response


# ---------------- SIMULATED INCOMING CALL ROUTE ----------------


@app.post("/api/simulate/incoming", response_model=SimulateIncomingResponse)
def simulate_incoming_call(request: SimulateIncomingRequest):
    """
    Initiates a simulated incoming call session for testing.
    Demonstrates the initial call forwarding detection and AI greeting without carrier charges.
    """
    settings = get_all_settings()
    provider_type = settings.get("telephony_provider", os.getenv("TELEPHONY_PROVIDER", "simulated"))
    adapter = get_telephony_adapter(provider_type)
    lang = request.language or settings.get("active_language", os.getenv("ASSISTANT_LANGUAGE", "en"))

    screener = AIScreener(language=lang)
    step0 = screener.process_step(step_index=0, caller_text=None, state={"language": lang})

    session_id = f"sim-{int(datetime.now(timezone.utc).timestamp())}"

    return SimulateIncomingResponse(
        status="initiated",
        session_id=session_id,
        greeting=step0["next_question"],
        step_index=1,
        demo_mode=adapter.is_demo_mode,
        caller_number=request.caller_number or "+91 98123 45678",
    )


# ---------------- CALL HISTORY & SUMMARY ROUTES ----------------


@app.get("/api/metrics")
def get_metrics():
    """Retrieve dashboard counters: incoming, completed, missed, flagged, urgent."""
    return get_dashboard_metrics()


@app.get("/api/calls")
def list_calls(
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """Retrieve list of screened calls with optional category/status filters."""
    return get_all_calls(category=category, status=status)


@app.get("/api/calls/{call_id}")
def get_call_details(call_id: str):
    """Retrieve complete details and transcript of a specific call."""
    call = get_call_by_id(call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    try:
        call["transcript"] = json.loads(call["transcript_json"])
    except Exception:
        call["transcript"] = []
    return call


@app.get("/api/calls/{call_id}/summary", response_model=CallSummaryResponse)
def get_call_summary_endpoint(call_id: str):
    """
    Retrieve structured call summary with PII protection (masked phone number),
    urgency classification, purpose, message, and recommended action.
    """
    summary = get_call_summary(call_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Call not found")
    return summary


@app.post("/api/calls")
def create_or_save_call(payload: CallCreate):
    """Save a screened or simulated call into the database."""
    call_id = save_call(payload.model_dump())
    return {"status": "success", "call_id": call_id}


@app.patch("/api/calls/{call_id}/decision")
def update_decision(call_id: str, payload: DecisionUpdate):
    """Update owner review decision (accept, decline, callback_requested)."""
    success = update_call_decision(call_id, payload.decision)
    if not success:
        raise HTTPException(status_code=404, detail="Call not found")
    return {"status": "success", "call_id": call_id, "decision": payload.decision}


@app.delete("/api/calls/{call_id}")
def remove_call(call_id: str):
    """Delete a call record for privacy control."""
    success = delete_call(call_id)
    if not success:
        raise HTTPException(status_code=404, detail="Call not found")
    return {"status": "success", "message": "Call deleted"}


@app.post("/api/simulate/step", response_model=SimulateStepResponse)
def simulate_conversation_step(request: SimulateStepRequest):
    """
    Handles one turn of the screening conversation.
    Interprets caller input, determines if follow-up question is needed,
    or advances to the next core question.
    """
    settings = get_all_settings()
    language = settings.get("active_language", os.getenv("ASSISTANT_LANGUAGE", "en"))
    screener = AIScreener(
        provider=settings.get("ai_provider", "local_nlp"),
        language=language,
    )

    state = request.extracted_state or {
        "caller_name": "",
        "purpose": "",
        "urgency": "Not confirmed",
        "message": "",
        "had_follow_up": False,
        "language": language,
    }

    result = screener.process_step(
        step_index=request.step_index,
        caller_text=request.caller_text,
        state=state,
    )

    return SimulateStepResponse(
        next_question=result["next_question"],
        is_finished=result["is_finished"],
        is_follow_up=result.get("is_follow_up", False),
        step_index=result["step_index"],
        extracted_state=result["extracted_state"],
        summary=result.get("summary"),
        category=result.get("category"),
        urgency=result.get("urgency"),
        suggested_action=result.get("suggested_action"),
    )


@app.post("/api/simulate/complete")
def complete_and_save_simulation(payload: Dict[str, Any]):
    """
    Finalizes the simulated call, saves it to SQLite call history,
    and returns the notification preview payload.
    """
    settings = get_all_settings()
    language = settings.get("active_language", os.getenv("ASSISTANT_LANGUAGE", "en"))
    screener = AIScreener(
        provider=settings.get("ai_provider", "local_nlp"),
        language=language,
    )

    state = payload.get("extracted_state", {})
    transcript = payload.get("transcript", [])
    caller_phone = payload.get("caller_phone", "+91 98123 45678")
    call_duration = payload.get("duration_sec", 42)

    if payload.get("is_failed"):
        summary_text = (
            "Caller: Unknown (Unanswered / Silent)\n"
            "Purpose: Failed or dropped call\n"
            "Urgency: Low\n"
            "Message: No response received from caller\n"
            "Suggested action: Ignore or wait for callback."
        )
        call_record = {
            "caller_name": "Unknown",
            "caller_number": caller_phone,
            "category": "Unknown",
            "status": "missed",
            "urgency": "Low",
            "purpose": "Call dropped or silent",
            "message": "No voice response",
            "suggested_action": "Ignore or wait for callback.",
            "summary_text": summary_text,
            "transcript_json": json.dumps(transcript, ensure_ascii=False),
            "duration_sec": call_duration,
            "is_spam_suspected": 0,
            "owner_decision": "pending",
        }
        call_id = save_call(call_record)
        return {
            "call_id": call_id,
            "summary": summary_text,
            "category": "Unknown",
            "urgency": "Low",
            "suggested_action": "Ignore or wait for callback.",
            "notification_preview": {
                "title": "Missed Call / Silent Caller",
                "body": summary_text,
                "urgency": "Low",
            },
        }

    summary_data = screener.generate_final_summary(state)

    call_record = {
        "caller_name": summary_data["caller_name"],
        "caller_number": caller_phone,
        "category": summary_data["category"],
        "status": "flagged" if summary_data["urgency"] == "High" else "completed",
        "urgency": summary_data["urgency"],
        "purpose": summary_data["purpose"],
        "message": summary_data["message"],
        "suggested_action": summary_data["suggested_action"],
        "summary_text": summary_data["summary_text"],
        "transcript_json": json.dumps(transcript, ensure_ascii=False),
        "duration_sec": call_duration,
        "is_spam_suspected": summary_data["is_spam_suspected"],
        "owner_decision": "pending",
    }

    call_id = save_call(call_record)

    return {
        "call_id": call_id,
        "summary": summary_data["summary_text"],
        "category": summary_data["category"],
        "urgency": summary_data["urgency"],
        "suggested_action": summary_data["suggested_action"],
        "is_spam_suspected": summary_data["is_spam_suspected"],
        "notification_preview": {
            "title": f"Call Screened: {summary_data['caller_name']} ({summary_data['category']})",
            "body": summary_data["summary_text"],
            "urgency": summary_data["urgency"],
        },
    }


@app.get("/api/settings")
def get_settings():
    """Retrieve application and privacy settings."""
    return get_all_settings()


@app.post("/api/settings")
def set_settings(payload: SettingsUpdate):
    """Update settings (language, greeting, strictness, etc.)."""
    update_settings(payload.settings)
    return {"status": "success", "settings": get_all_settings()}


@app.get("/api/telephony/status")
def get_telephony_info():
    """Check status of the active telephony adapter (Simulated vs Exotel vs Twilio)."""
    settings = get_all_settings()
    provider_type = settings.get("telephony_provider", os.getenv("TELEPHONY_PROVIDER", "simulated"))
    adapter = get_telephony_adapter(provider_type)
    return adapter.get_status()


# Mount static assets for frontend dashboard
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
