import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path(__file__).resolve().parent.parent / "call_assistant.db"

DEFAULT_SETTINGS = {
    "ai_greeting_hi": "नमस्ते! मैं एक AI कॉल असिस्टेंट बोल रहा हूँ। आपका नाम क्या है?",
    "ai_greeting_en": "Hello! I am an AI Call Assistant for 8094725777. May I know who is calling, please?",
    "active_language": os.getenv("ASSISTANT_LANGUAGE", "en"),  # 'en' for English, 'hi' for Hindi
    "demo_mode": "true",
    "owner_name": os.getenv("OWNER_NAME", "Owner"),
    "owner_phone": os.getenv("OWNER_PHONE", "+91 8094725777"),
    "retention_days": "30",
    "screening_strictness": "balanced",  # relaxed, balanced, strict
    "ai_provider": "local_nlp",  # 'local_nlp' (100% free), 'gemini', 'openai'
    "telephony_provider": os.getenv("TELEPHONY_PROVIDER", "simulated"),  # 'simulated', 'exotel', 'twilio'
    "notify_on_urgent": "true",
}


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Calls table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS calls (
                id TEXT PRIMARY KEY,
                caller_name TEXT,
                caller_number TEXT,
                category TEXT DEFAULT 'Unknown',
                status TEXT DEFAULT 'completed',
                urgency TEXT DEFAULT 'Not confirmed',
                purpose TEXT,
                message TEXT,
                suggested_action TEXT,
                summary_text TEXT,
                transcript_json TEXT,
                created_at TEXT,
                duration_sec INTEGER DEFAULT 0,
                is_spam_suspected INTEGER DEFAULT 0,
                owner_decision TEXT DEFAULT 'pending'
            )
            """
        )

        # Settings table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )

        # Insert default settings if not existing
        for key, val in DEFAULT_SETTINGS.items():
            cursor.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, val),
            )

        # Ensure owner_phone is updated from legacy placeholder if present
        cursor.execute("SELECT value FROM settings WHERE key = 'owner_phone'")
        curr_phone = cursor.fetchone()
        if curr_phone and curr_phone[0] in ["+91 98765 43210", "9876543210"]:
            cursor.execute("UPDATE settings SET value = ? WHERE key = 'owner_phone'", (DEFAULT_SETTINGS["owner_phone"],))

        # Ensure active_language defaults to en
        cursor.execute("SELECT value FROM settings WHERE key = 'active_language'")
        curr_lang = cursor.fetchone()
        if curr_lang and curr_lang[0] == "hi":
            cursor.execute("UPDATE settings SET value = 'en' WHERE key = 'active_language'")

        conn.commit()

        # Seed initial sample calls if table is empty
        cursor.execute("SELECT COUNT(*) FROM calls")
        count = cursor.fetchone()[0]
        if count == 0:
            seed_initial_calls(cursor)
            conn.commit()


def seed_initial_calls(cursor: sqlite3.Cursor) -> None:
    now = datetime.now(timezone.utc).isoformat()
    samples = [
        {
            "id": "call-101",
            "caller_name": "Aman",
            "caller_number": "+91 98123 45678",
            "category": "Work",
            "status": "completed",
            "urgency": "Not confirmed",
            "purpose": "College project discussion",
            "message": "Wants to discuss the submission deadline and slides",
            "suggested_action": "Call back when available.",
            "summary_text": (
                "Caller: Aman\n"
                "Purpose: College project discussion\n"
                "Urgency: Not confirmed\n"
                "Message: Wants to discuss the submission deadline and slides\n"
                "Suggested action: Call back when available."
            ),
            "transcript_json": json.dumps(
                [
                    {
                        "speaker": "ai",
                        "text": "नमस्ते! मैं एक AI कॉल असिस्टेंट बोल रहा हूँ। आपका नाम क्या है?",
                    },
                    {"speaker": "caller", "text": "मेरा नाम अमन है।"},
                    {
                        "speaker": "ai",
                        "text": "धन्यवाद अमन जी। आप किस काम से कॉल कर रहे हैं?",
                    },
                    {
                        "speaker": "caller",
                        "text": "मुझे कॉलेज प्रोजेक्ट के सबमिशन और प्रेजेंटेशन पर चर्चा करनी है।",
                    },
                    {
                        "speaker": "ai",
                        "text": "क्या प्रोजेक्ट की डेडलाइन आज है या समय है?",
                    },
                    {
                        "speaker": "caller",
                        "text": "डेडलाइन कल शाम की है, आज रात तक बात हो जाए तो अच्छा रहेगा।",
                    },
                    {
                        "speaker": "ai",
                        "text": "क्या यह ज़रूरी है या मैं बाद में कॉल बैक कर सकता हूँ?",
                    },
                    {
                        "caller": "caller",
                        "speaker": "caller",
                        "text": "जब भी समय मिले कॉल बैक कर लें।",
                    },
                    {
                        "speaker": "ai",
                        "text": "क्या आप कोई संदेश देना चाहेंगे?",
                    },
                    {
                        "speaker": "caller",
                        "text": "बस यही कि सबमिशन की स्लाइड्स तैयार हैं, एक बार रिव्यू करना है।",
                    },
                    {
                        "speaker": "ai",
                        "text": "धन्यवाद अमन जी! मैंने आपकी जानकारी नोट कर ली है।",
                    },
                ]
            ),
            "created_at": now,
            "duration_sec": 78,
            "is_spam_suspected": 0,
            "owner_decision": "callback_requested",
        },
        {
            "id": "call-102",
            "caller_name": "डॉ. शर्मा (क्लीनिक)",
            "caller_number": "+91 98450 11223",
            "category": "Important",
            "status": "flagged",
            "urgency": "High",
            "purpose": "Medical test reports update",
            "message": "ब्लड टेस्ट रिपोर्ट आ गई है, डॉक्टर से तुरंत बात करें",
            "suggested_action": "Call back immediately.",
            "summary_text": (
                "Caller: डॉ. शर्मा (क्लीनिक)\n"
                "Purpose: Medical test reports update\n"
                "Urgency: High\n"
                "Message: ब्लड टेस्ट रिपोर्ट आ गई है, डॉक्टर से तुरंत बात करें\n"
                "Suggested action: Call back immediately."
            ),
            "transcript_json": json.dumps(
                [
                    {
                        "speaker": "ai",
                        "text": "नमस्ते! मैं एक AI कॉल असिस्टेंट हूँ। आपका नाम क्या है?",
                    },
                    {
                        "speaker": "caller",
                        "text": "मैं डॉ. शर्मा के क्लीनिक से रिसेप्शनिस्ट बोल रही हूँ।",
                    },
                    {
                        "speaker": "ai",
                        "text": "आप किस काम से कॉल कर रहे हैं?",
                    },
                    {
                        "speaker": "caller",
                        "text": "कल के मेडिकल टेस्ट की रिपोर्ट आ गई है और डॉक्टर ने तुरंत परामर्श के लिए कहा है।",
                    },
                    {
                        "speaker": "ai",
                        "text": "क्या यह अति आवश्यक (emergency) है?",
                    },
                    {
                        "speaker": "caller",
                        "text": "हाँ, कृपया जितनी जल्दी हो सके संपर्क करें।",
                    },
                ]
            ),
            "created_at": now,
            "duration_sec": 45,
            "is_spam_suspected": 0,
            "owner_decision": "pending",
        },
        {
            "id": "call-103",
            "caller_name": "अज्ञात कॉलर",
            "caller_number": "+91 140 9876543",
            "category": "Suspected Spam",
            "status": "completed",
            "urgency": "Low",
            "purpose": "Credit card pre-approved loan offer",
            "message": "बैंक से प्री-अप्रूव्ड पर्सनल लोन ऑफर",
            "suggested_action": "Decline or ignore.",
            "summary_text": (
                "Caller: अज्ञात कॉलर\n"
                "Purpose: Credit card pre-approved loan offer\n"
                "Urgency: Low\n"
                "Message: बैंक से प्री-अप्रूव्ड पर्सनल लोन ऑफर\n"
                "Suggested action: Decline or ignore."
            ),
            "transcript_json": json.dumps(
                [
                    {
                        "speaker": "ai",
                        "text": "नमस्ते! मैं एक AI कॉल असिस्टेंट हूँ। आपका नाम क्या है?",
                    },
                    {
                        "speaker": "caller",
                        "text": "सर आपके लिए 5 लाख का प्री-अप्रूव्ड लोन है।",
                    },
                    {
                        "speaker": "ai",
                        "text": "कृपया अपना नाम और कंपनी का नाम बताएं?",
                    },
                    {
                        "speaker": "caller",
                        "text": "लोन डिपार्टमेंट से बोल रहा हूँ, सिर्फ 2 मिनट लगेंगे।",
                    },
                ]
            ),
            "created_at": now,
            "duration_sec": 30,
            "is_spam_suspected": 1,
            "owner_decision": "declined",
        },
        {
            "id": "call-104",
            "caller_name": "राकेश (सोसायटी ऑफिस)",
            "caller_number": "+91 97112 34455",
            "category": "Personal",
            "status": "completed",
            "urgency": "Medium",
            "purpose": "Society maintenance parking allocation",
            "message": "सोसायटी पार्किंग स्लॉट रिन्यूअल के कागजात पर दस्तखत चाहिए",
            "suggested_action": "Review documents and respond.",
            "summary_text": (
                "Caller: राकेश (सोसायटी ऑफिस)\n"
                "Purpose: Society maintenance parking allocation\n"
                "Urgency: Medium\n"
                "Message: सोसायटी पार्किंग स्लॉट रिन्यूअल के कागजात पर दस्तखत चाहिए\n"
                "Suggested action: Review documents and respond."
            ),
            "transcript_json": json.dumps(
                [
                    {
                        "speaker": "ai",
                        "text": "नमस्ते! मैं एक AI कॉल असिस्टेंट हूँ। आपका नाम क्या है?",
                    },
                    {"speaker": "caller", "text": "राकेश बात कर रहा हूँ सोसायटी ऑफिस से।"},
                    {
                        "speaker": "ai",
                        "text": "राकेश जी, आप किस काम से कॉल कर रहे हैं?",
                    },
                    {
                        "speaker": "caller",
                        "text": "पार्किंग स्लॉट रिन्यूअल फॉर्म पर आपके हस्ताक्षर चाहिए थे।",
                    },
                    {
                        "speaker": "ai",
                        "text": "क्या यह ज़रूरी है या मैं बाद में कॉल बैक कर सकता हूँ?",
                    },
                    {
                        "speaker": "caller",
                        "text": "कल शाम तक ऑफिस आकर साइन कर दें तो चलेगा।",
                    },
                ]
            ),
            "created_at": now,
            "duration_sec": 52,
            "is_spam_suspected": 0,
            "owner_decision": "accepted",
        },
    ]

    for item in samples:
        cursor.execute(
            """
            INSERT INTO calls (
                id, caller_name, caller_number, category, status, urgency,
                purpose, message, suggested_action, summary_text, transcript_json,
                created_at, duration_sec, is_spam_suspected, owner_decision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["id"],
                item["caller_name"],
                item["caller_number"],
                item["category"],
                item["status"],
                item["urgency"],
                item["purpose"],
                item["message"],
                item["suggested_action"],
                item["summary_text"],
                item["transcript_json"],
                item["created_at"],
                item["duration_sec"],
                item["is_spam_suspected"],
                item["owner_decision"],
            ),
        )


def get_all_calls(category: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM calls WHERE 1=1"
        params = []
        if category and category.lower() != "all":
            query += " AND category = ?"
            params.append(category)
        if status and status.lower() != "all":
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_call_by_id(call_id: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM calls WHERE id = ?", (call_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def save_call(call_data: Dict[str, Any]) -> str:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        call_id = call_data.get("id") or f"call-{int(datetime.now(timezone.utc).timestamp())}"
        cursor.execute(
            """
            INSERT OR REPLACE INTO calls (
                id, caller_name, caller_number, category, status, urgency,
                purpose, message, suggested_action, summary_text, transcript_json,
                created_at, duration_sec, is_spam_suspected, owner_decision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                call_id,
                call_data.get("caller_name", "Unknown"),
                call_data.get("caller_number", "+91 98765 00000"),
                call_data.get("category", "Unknown"),
                call_data.get("status", "completed"),
                call_data.get("urgency", "Not confirmed"),
                call_data.get("purpose", ""),
                call_data.get("message", ""),
                call_data.get("suggested_action", "Call back when available."),
                call_data.get("summary_text", ""),
                call_data.get("transcript_json", "[]"),
                call_data.get("created_at") or datetime.now(timezone.utc).isoformat(),
                call_data.get("duration_sec", 0),
                1 if call_data.get("is_spam_suspected") else 0,
                call_data.get("owner_decision", "pending"),
            ),
        )
        conn.commit()
        return call_id


def update_call_decision(call_id: str, decision: str) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE calls SET owner_decision = ? WHERE id = ?",
            (decision, call_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_call(call_id: str) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM calls WHERE id = ?", (call_id,))
        conn.commit()
        return cursor.rowcount > 0


def get_dashboard_metrics() -> Dict[str, int]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM calls")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM calls WHERE status = 'incoming'")
        incoming = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM calls WHERE status = 'completed'")
        completed = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM calls WHERE status = 'missed'")
        missed = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM calls WHERE status = 'flagged' OR is_spam_suspected = 1")
        flagged = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM calls WHERE urgency = 'High'")
        urgent = cursor.fetchone()[0]

        return {
            "total": total,
            "incoming": incoming,
            "completed": completed,
            "missed": missed,
            "flagged": flagged,
            "urgent": urgent,
        }


def get_all_settings() -> Dict[str, str]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        return {row["key"]: row["value"] for row in rows}


def update_settings(updates: Dict[str, str]) -> None:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for key, value in updates.items():
            cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value)),
            )
        conn.commit()


def mask_phone_number(phone: Optional[str]) -> str:
    """
    Masks middle digits of a phone number to protect personal data / PII.
    E.g. '+91 8094725777' -> '+91 809****777'
    """
    if not phone:
        return "Unknown"
    clean = re.sub(r"[^\d+]", "", phone)
    if len(clean) >= 10:
        prefix = clean[:5]
        suffix = clean[-3:]
        return f"{prefix}****{suffix}"
    return clean


def get_call_summary(call_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a structured call summary suitable for API responses.
    """
    call = get_call_by_id(call_id)
    if not call:
        return None
    return {
        "call_id": call["id"],
        "caller_name": call["caller_name"],
        "caller_number": call["caller_number"],
        "caller_number_masked": mask_phone_number(call["caller_number"]),
        "category": call["category"],
        "status": call["status"],
        "urgency": call["urgency"],
        "purpose": call["purpose"],
        "message": call["message"],
        "suggested_action": call["suggested_action"],
        "summary_text": call["summary_text"],
        "created_at": call["created_at"],
        "duration_sec": call["duration_sec"],
        "is_spam_suspected": bool(call["is_spam_suspected"]),
        "owner_decision": call["owner_decision"],
    }
