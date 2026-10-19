import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ai_screener import AIScreener
from app.database import init_db, get_all_calls, get_call_by_id, mask_phone_number
from app.telephony_adapter import get_telephony_adapter, TwilioAdapter

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    init_db()


def test_health_check_endpoints():
    """Verify health check endpoints return healthy status, demo mode flag, and DB status."""
    for path in ["/health", "/api/health"]:
        res = client.get(path)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert "timestamp" in data
        assert "provider" in data
        assert data["demo_mode"] is True
        assert "owner_phone" in data
        assert "connected" in data["database"]


def test_simulate_incoming_call_endpoint():
    """Test /api/simulate/incoming initiates a simulated incoming screening session."""
    payload = {
        "caller_number": "+91 98123 45678",
        "caller_name": "Test Caller",
        "language": "en",
    }
    res = client.post("/api/simulate/incoming", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "initiated"
    assert "sim-" in data["session_id"]
    assert "8094725777" in data["greeting"]
    assert data["step_index"] == 1
    assert data["demo_mode"] is True


def test_ai_screener_english_full_screening_flow():
    """Test full multi-turn English conversation: Name -> Purpose -> Urgency -> Message -> Summary."""
    screener = AIScreener(language="en")

    # Step 0: Greeting & Q1 (Name)
    res0 = screener.process_step(step_index=0, caller_text=None, state={})
    assert "Hello" in res0["next_question"]
    assert "8094725777" in res0["next_question"]
    assert "name" in res0["next_question"].lower()
    state = res0["extracted_state"]

    # Step 1: Caller states name
    res1 = screener.process_step(
        step_index=1,
        caller_text="My name is Michael Vance.",
        state=state,
    )
    state = res1["extracted_state"]
    assert state["caller_name"] == "Michael Vance"
    assert "purpose" in res1["next_question"].lower()

    # Step 2: Caller states purpose
    res2 = screener.process_step(
        step_index=2,
        caller_text="I am calling regarding the quarterly project review slides.",
        state=state,
    )
    state = res2["extracted_state"]
    assert "project review" in state["purpose"]

    # If follow-up triggered, respond to it
    if res2.get("is_follow_up"):
        res2_follow = screener.process_step(
            step_index=2,
            caller_text="The submission is tomorrow afternoon.",
            state=state,
        )
        state = res2_follow["extracted_state"]
        assert "urgent" in res2_follow["next_question"].lower()
    else:
        assert "urgent" in res2["next_question"].lower()

    # Step 3: Urgency question answered
    res3 = screener.process_step(
        step_index=3,
        caller_text="It is not urgent, he can call me back whenever free.",
        state=state,
    )
    state = res3["extracted_state"]
    assert state["urgency"] in ["Low", "Not confirmed"]
    assert "message" in res3["next_question"].lower()

    # Step 4: Message question answered
    res4 = screener.process_step(
        step_index=4,
        caller_text="Please tell him I sent the deck to his email.",
        state=state,
    )
    assert res4["is_finished"] is True
    assert res4["category"] == "Work"
    assert "Caller: Michael Vance" in res4["summary"]
    assert "Purpose: I am calling regarding the quarterly project review slides." in res4["summary"]
    assert "Urgency: Low" in res4["summary"]
    assert "Message: Please tell him I sent the deck to his email." in res4["summary"]
    assert "Suggested action: Call back when available." in res4["summary"]


def test_ai_screener_hindi_conversation_flow():
    """Test Hindi conversation flow for backward compatibility."""
    screener = AIScreener(language="hi")

    res0 = screener.process_step(step_index=0, caller_text=None, state={"language": "hi"})
    assert "नमस्ते" in res0["next_question"]
    state = res0["extracted_state"]

    res1 = screener.process_step(step_index=1, caller_text="मेरा नाम अमन है।", state=state)
    state = res1["extracted_state"]
    assert state["caller_name"] == "अमन"


def test_urgent_emergency_call():
    """Test emergency hospital/medical call detection."""
    screener = AIScreener(language="en")
    state = {
        "caller_name": "Dr. Sharma Clinic",
        "purpose": "Urgent medical lab test reports",
        "urgency": "High",
        "message": "Immediate consultation required for emergency",
    }
    summary = screener.generate_final_summary(state)
    assert summary["category"] == "Important"
    assert summary["urgency"] == "High"
    assert summary["suggested_action"] == "Call back immediately."


def test_suspected_spam_call():
    """Test spam loan/credit card marketing detection."""
    screener = AIScreener(language="en")
    state = {
        "caller_name": "Loan Department",
        "purpose": "Special pre-approved credit card and instant loan offer",
        "urgency": "Low",
        "message": "500000 loan approved for today only",
    }
    summary = screener.generate_final_summary(state)
    assert summary["category"] == "Suspected Spam"
    assert summary["is_spam_suspected"] == 1
    assert summary["suggested_action"] == "Decline or ignore."


def test_telephony_voice_webhook_lifecycle():
    """Test full telephony voice webhook lifecycle from call start to completion."""
    call_sid = "test-call-webhook-101"

    # Turn 1: Call arrives at webhook
    res1 = client.post(
        "/api/telephony/webhook",
        data={"CallSid": call_sid, "From": "+91 98450 11223"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res1.status_code == 200
    assert "<Response>" in res1.text
    assert "<Gather" in res1.text
    assert "8094725777" in res1.text

    # Turn 2: Caller states their name
    res2 = client.post(
        "/api/telephony/webhook",
        data={
            "CallSid": call_sid,
            "From": "+91 98450 11223",
            "SpeechResult": "My name is Sarah Connor.",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res2.status_code == 200
    assert "Sarah Connor" in res2.text or "purpose" in res2.text.lower()

    # Turn 3: Caller states purpose
    res3 = client.post(
        "/api/telephony/webhook",
        data={
            "CallSid": call_sid,
            "From": "+91 98450 11223",
            "SpeechResult": "Scheduling our upcoming quarterly meeting.",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res3.status_code == 200
    assert "<Response>" in res3.text

    # Turn 4: Caller states urgency
    res4 = client.post(
        "/api/telephony/webhook",
        data={
            "CallSid": call_sid,
            "From": "+91 98450 11223",
            "SpeechResult": "It is not urgent, just whenever free.",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res4.status_code == 200

    # Turn 5: Caller leaves message -> Webhook completes call and saves to DB
    res5 = client.post(
        "/api/telephony/webhook",
        data={
            "CallSid": call_sid,
            "From": "+91 98450 11223",
            "SpeechResult": "Send me the agenda before tomorrow.",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res5.status_code == 200
    assert "<Hangup/>" in res5.text

    # Verify that call was saved in database
    saved_call = get_call_by_id(call_sid)
    assert saved_call is not None
    assert saved_call["caller_name"] == "Sarah Connor"
    assert "Caller: Sarah Connor" in saved_call["summary_text"]


def test_call_summary_api_and_data_masking():
    """Test /api/calls/{call_id}/summary returns structured summary with masked phone number."""
    # Fetch first call
    calls = get_all_calls()
    assert len(calls) > 0
    call_id = calls[0]["id"]

    res = client.get(f"/api/calls/{call_id}/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["call_id"] == call_id
    assert "caller_name" in data
    assert "caller_number_masked" in data
    assert "****" in data["caller_number_masked"]
    assert "suggested_action" in data
    assert "summary_text" in data


def test_webhook_signature_validation():
    """Test webhook signature validation in live mode vs demo mode."""
    # In Demo Mode (default), signature validation passes gracefully
    adapter = get_telephony_adapter("simulated")
    assert adapter.validate_webhook_signature(None, "http://localhost:8000/webhook", {}) is True

    # TwilioAdapter without auth token also permits in demo mode
    tw = TwilioAdapter(account_sid="", auth_token="")
    assert tw.is_demo_mode is True
    assert tw.validate_webhook_signature(None, "http://localhost:8000/webhook", {}) is True


def test_phone_number_masking_utility():
    """Verify personal phone numbers are masked to protect PII."""
    assert mask_phone_number("+91 8094725777") == "+9180****777"
    assert mask_phone_number("+1 415 555 2671") == "+1415****671"
    assert mask_phone_number("") == "Unknown"
