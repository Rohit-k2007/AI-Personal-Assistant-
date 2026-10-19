"""
AI Call Screener Engine.
Supports English (default) and Hindi screening conversations with rule-based NLP,
intent extraction, urgency classification, spam detection, and structured summaries.
"""

import os
import re
from typing import Any, Dict, List, Optional, Tuple

# Pre-defined prompts for English and Hindi
PROMPTS = {
    "en": {
        "greeting_and_q1": "Hello! I am an AI Call Assistant for 8094725777. May I have your name, please?",
        "q2_purpose": "What is the purpose of your call?",
        "q3_urgency": "Is this urgent, or can the owner call you back when available?",
        "q4_message": "Would you like to leave a message?",
        "closing_thanks": "Thank you. I have recorded your message and notified the owner. Have a good day.",
        "refusal_followup": "I am an AI assistant taking messages for 8094725777. May I know the reason for your call without your name?",
        "emergency_followup": "Understood. Is there an urgent detail or callback number you want me to convey right away?",
        "work_followup": "Is there a specific deadline or scheduled time associated with this?",
        "delivery_followup": "Can the package or parcel be left at the gate or with security?",
        "spam_followup": "Could you state the name of your organization and whether this is an authorized communication?",
        "default_purpose": "Purpose not specified",
        "default_message": "No message left",
        "silent_response": "No voice response",
        "silent_summary": "Caller: Unknown (Unanswered / Silent)\nPurpose: Failed or dropped call\nUrgency: Low\nMessage: No response received from caller\nSuggested action: Ignore or wait for callback.",
    },
    "hi": {
        "greeting_and_q1": "नमस्ते! मैं एक AI कॉल असिस्टेंट बोल रहा हूँ। आपका नाम क्या है?",
        "q2_purpose": "आप किस काम से कॉल कर रहे हैं?",
        "q3_urgency": "क्या यह ज़रूरी है या मैं बाद में कॉल बैक कर सकता हूँ?",
        "q4_message": "क्या आप कोई संदेश देना चाहेंगे?",
        "closing_thanks": "धन्यवाद! मैंने आपकी जानकारी और संदेश नोट कर लिया है। मैं मालिक को जल्द सूचित कर दूंगा।",
        "refusal_followup": "मैं आपकी मदद के लिए पूछ रहा हूँ। क्या आप बिना नाम बताए कॉल का उद्देश्य बता सकते हैं?",
        "emergency_followup": "समझ गया, क्या कोई तुरंत संदेश देना है ताकि मैं उन्हें तुरंत सूचित करूँ?",
        "work_followup": "क्या यह किसी समय-सीमा (deadline) से जुड़ा है या सामान्य विचार-विमर्श है?",
        "delivery_followup": "क्या पार्सल गेट पर या सुरक्षाकर्मी (guard) के पास दिया जा सकता है?",
        "spam_followup": "क्या आप बैंक के अधिकृत प्रतिनिधि हैं? कृपया अपनी शाखा का नाम बताएं।",
        "default_purpose": "उद्देश्य नहीं बताया गया",
        "default_message": "कोई संदेश नहीं छोड़ा",
        "silent_response": "कोई आवाज़ नहीं मिली",
        "silent_summary": "Caller: Unknown (Unanswered / Silent)\nPurpose: Failed or dropped call\nUrgency: Low\nMessage: No response received from caller\nSuggested action: Ignore or wait for callback.",
    },
}

# Refusal / evasion keywords
REFUSAL_KEYWORDS = [
    # English
    "no",
    "not telling",
    "won't say",
    "don't want to say",
    "none of your business",
    "who are you",
    "speak to owner",
    "give the phone",
    "put me through",
    "why should i tell",
    "human please",
    "operator",
    # Hindi
    "नहीं बताना",
    "कॉल मत काटो",
    "तुमसे क्या मतलब",
    "मालिक से बात कराओ",
    "फोन दो",
    "तुम कौन होते हो",
    "नहीं बताऊंगा",
    "सीधे बात कराओ",
]

# Spam keywords
SPAM_KEYWORDS = [
    # English
    "loan",
    "credit card",
    "pre-approved",
    "trading",
    "investment",
    "crypto",
    "lottery",
    "free gift",
    "free offer",
    "insurance policy",
    "promotional",
    "telemarketing",
    "special offer",
    "congratulations you won",
    "fund offer",
    "zero interest",
    # Hindi
    "लोन",
    "क्रेडिट कार्ड",
    "पर्सनल लोन",
    "इन्वेस्टमेंट",
    "शेयर मार्केट",
    "लॉटरी",
    "फ्री ऑफर",
    "बीमा",
    "पॉलिसी",
]

# Urgent keywords
HIGH_URGENCY_KEYWORDS = [
    # English
    "urgent",
    "emergency",
    "hospital",
    "doctor",
    "asap",
    "immediate",
    "critical",
    "life",
    "accident",
    "right now",
    "right away",
    "emergency room",
    # Hindi
    "तुरंत",
    "इमरजेंसी",
    "हॉस्पिटल",
    "डॉक्टर",
    "अति आवश्यक",
    "अभी",
    "तुरंत बात करनी है",
]

MEDIUM_URGENCY_KEYWORDS = [
    # English
    "today",
    "tonight",
    "deadline",
    "important",
    "by tomorrow",
    "meeting",
    "submission",
    "schedule",
    "review",
    # Hindi
    "ज़रूरी",
    "जरूरी",
    "आज ही",
    "आज रात",
    "कल तक",
    "डेडलाइन",
    "मीटिंग",
]

LOW_URGENCY_KEYWORDS = [
    # English
    "no rush",
    "whenever free",
    "later",
    "not urgent",
    "casual",
    "whenever",
    "anytime",
    "no hurry",
    "when you have time",
    # Hindi
    "जब समय मिले",
    "आराम से",
    "कोई जल्दी नहीं",
    "फुर्सत में",
    "बाद में",
    "कभी भी",
]


class AIScreener:
    """
    Intelligent conversation screener for personal call screening.
    Supports English and Hindi screening workflows with local NLP.
    Zero external paid APIs required.
    """

    def __init__(
        self,
        provider: str = "local_nlp",
        api_key: Optional[str] = None,
        language: str = "en",
    ):
        self.provider = provider
        self.api_key = api_key or os.getenv("AI_API_KEY")
        self.language = language or os.getenv("ASSISTANT_LANGUAGE", "en")

    def get_prompts(self, lang: Optional[str] = None) -> Dict[str, str]:
        active_lang = lang or self.language
        return PROMPTS.get(active_lang, PROMPTS["en"])

    def clean_text(self, text: Optional[str]) -> str:
        if not text:
            return ""
        return text.strip()

    def is_silent_or_empty(self, text: Optional[str]) -> bool:
        if not text:
            return True
        cleaned = text.strip().lower()
        return cleaned in [
            "",
            "...",
            ".",
            "?",
            "पता नहीं",
            "silent",
            "no response",
            "none",
            "nothing",
        ]

    def is_refusal(self, text: str) -> bool:
        text_lower = text.lower()
        for k in REFUSAL_KEYWORDS:
            if re.search(r"(?:^|\s|[^\w])" + re.escape(k) + r"(?:$|\s|[^\w])", text_lower):
                return True
        return False

    def extract_name(self, text: str) -> str:
        raw = self.clean_text(text)
        if self.is_silent_or_empty(raw) or self.is_refusal(raw):
            return "Unknown"

        cleaned = re.sub(r"[।\.,\?!;:'\"]", "", raw).strip()
        if not cleaned:
            return "Unknown"

        patterns = [
            # English introductions
            r"my name is\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)",
            r"this is\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)",
            r"i am\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)",
            r"it's\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)",
            r"([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+here",
            r"([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+calling",
            r"([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+speaking",
            # Hindi introductions
            r"मेरा नाम\s+([A-Za-z\u0900-\u097F]+(?:\s+[A-Za-z\u0900-\u097F]+)?)",
            r"मैं\s+([A-Za-z\u0900-\u097F]+(?:\s+[A-Za-z\u0900-\u097F]+)?)\s+बोल\s*(?:रहा|रही)",
            r"मैं\s+([A-Za-z\u0900-\u097F]+(?:\s+[A-Za-z\u0900-\u097F]+)?)\s+हूँ",
            r"([A-Za-z\u0900-\u097F]+(?:\s+[A-Za-z\u0900-\u097F]+)?)\s+बात\s+कर\s*(?:रहा|रही)",
        ]

        candidate = ""
        for p in patterns:
            match = re.search(p, cleaned, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                break

        if not candidate:
            words = cleaned.split()
            if len(words) <= 3:
                candidate = " ".join(words)

        if candidate:
            candidate = re.sub(r"[।\.,\?!]", "", candidate).strip()
            cand_words = candidate.split()
            stop_words = {
                "a",
                "an",
                "the",
                "ai",
                "assistant",
                "call",
                "calling",
                "here",
                "is",
                "speaking",
                "sir",
                "mr",
                "mrs",
                "ms",
                "एक",
                "है",
                "हूँ",
                "जी",
            }
            filtered_words = [w for w in cand_words if w.lower() not in stop_words]
            if filtered_words:
                return " ".join(filtered_words)

        words = cleaned.split()
        return words[0] if words else "Unknown"

    def analyze_urgency(self, text: str) -> str:
        cleaned = self.clean_text(text).lower()
        # Check explicit low urgency and negation phrases first (e.g. "not urgent", "no rush")
        if any(w in cleaned for w in LOW_URGENCY_KEYWORDS) or "not urgent" in cleaned or "no hurry" in cleaned or "no rush" in cleaned:
            return "Low"
        if any(w in cleaned for w in HIGH_URGENCY_KEYWORDS):
            return "High"
        if any(w in cleaned for w in MEDIUM_URGENCY_KEYWORDS):
            return "Medium"
        return "Not confirmed"

    def determine_category_and_spam(
        self, caller_name: str, purpose: str, message: str
    ) -> Tuple[str, int]:
        combined = f"{caller_name} {purpose} {message}".lower()

        # Check spam first
        if any(k in combined for k in SPAM_KEYWORDS):
            return "Suspected Spam", 1

        # Check Important (Medical, Emergency, Official Legal)
        if any(
            w in combined
            for w in [
                "hospital",
                "doctor",
                "clinic",
                "medical",
                "emergency",
                "police",
                "court",
                "security alert",
                "dr.",
                "dr ",
                "हॉस्पिटल",
                "अस्पताल",
                "डॉक्टर",
                "डॉ.",
                "डॉ",
                "क्लीनिक",
                "सुरक्षा",
                "इमरजेंसी",
                "रिपोर्ट",
            ]
        ):
            return "Important", 0

        # Check Work (Project, Submission, Meeting, Office)
        if any(
            w in combined
            for w in [
                "project",
                "submission",
                "presentation",
                "assignment",
                "college",
                "office",
                "work",
                "client",
                "interview",
                "job",
                "meeting",
                "company",
                "कॉलेज",
                "प्रोजेक्ट",
                "सबमिशन",
                "कंपनी",
                "ऑफ़िस",
            ]
        ):
            return "Work", 0

        # Check Personal (Family, Friend, Home)
        if any(
            w in combined
            for w in [
                "family",
                "friend",
                "home",
                "flat",
                "building",
                "society",
                "party",
                "mom",
                "dad",
                "brother",
                "sister",
                "सोसायटी",
                "घर",
                "दोस्त",
                "मम्मी",
                "पापा",
                "भाई",
                "बहन",
            ]
        ):
            return "Personal", 0

        if caller_name == "Unknown" or not purpose:
            return "Unknown", 0

        return "Personal", 0

    def generate_follow_up(
        self, step_index: int, caller_answer: str, state: Dict[str, Any], lang: str
    ) -> Optional[str]:
        p = self.get_prompts(lang)
        answer_lower = caller_answer.lower()

        # Step 1 (Name): If refusal or empty
        if step_index == 1:
            if self.is_refusal(caller_answer) or state.get("caller_name") == "Unknown":
                return p["refusal_followup"]

        # Step 2 (Purpose)
        if step_index == 2:
            if any(
                w in answer_lower
                for w in [
                    "project",
                    "college",
                    "submission",
                    "assignment",
                    "presentation",
                    "deadline",
                    "प्रोजेक्ट",
                    "कॉलेज",
                    "सबमिशन",
                ]
            ):
                return p["work_followup"]
            if any(
                w in answer_lower
                for w in [
                    "hospital",
                    "doctor",
                    "report",
                    "medical",
                    "clinic",
                    "हॉस्पिटल",
                    "डॉक्टर",
                    "दवा",
                ]
            ):
                return p["emergency_followup"]
            if any(
                w in answer_lower
                for w in [
                    "delivery",
                    "parcel",
                    "courier",
                    "amazon",
                    "flipkart",
                    "swiggy",
                    "zomato",
                    "डिलीवरी",
                    "पार्सल",
                ]
            ):
                return p["delivery_followup"]
            if any(
                w in answer_lower
                for w in ["loan", "credit card", "card", "लोन", "क्रेडिट कार्ड"]
            ):
                return p["spam_followup"]

        # Step 3 (Urgency)
        if step_index == 3:
            if state.get("urgency") == "High":
                return p["emergency_followup"]

        return None

    def process_step(
        self,
        step_index: int,
        caller_text: Optional[str],
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Processes one conversational turn.
        Step 0: Greeting & Q1 (Name)
        Step 1: Caller answers Name -> ask Q2 (Purpose)
        Step 2: Caller answers Purpose -> ask Q3 (Urgency)
        Step 3: Caller answers Urgency -> ask Q4 (Message)
        Step 4: Caller answers Message -> Closing & Summary
        """
        # Determine language for this conversation
        lang = state.get("language") or self.language or "en"
        # Auto-detect Devanagari Hindi if present
        if caller_text and re.search(r"[\u0900-\u097F]", caller_text):
            lang = "hi"
            state["language"] = "hi"

        p = self.get_prompts(lang)
        text = self.clean_text(caller_text)

        # Step 0: Initial prompt
        if step_index == 0:
            return {
                "next_question": p["greeting_and_q1"],
                "is_finished": False,
                "is_follow_up": False,
                "step_index": 1,
                "extracted_state": {
                    "caller_name": "",
                    "purpose": "",
                    "urgency": "Not confirmed",
                    "message": "",
                    "had_follow_up": False,
                    "language": lang,
                },
            }

        # Step 1: Handling answer to Q1 (Name)
        if step_index == 1:
            name = self.extract_name(text)
            state["caller_name"] = name if name != "Unknown" else (state.get("caller_name") or "Unknown")

            follow_up = None
            if not state.get("had_follow_up") and (self.is_refusal(text) or self.is_silent_or_empty(text)):
                follow_up = self.generate_follow_up(1, text, state, lang)

            if follow_up:
                state["had_follow_up"] = True
                return {
                    "next_question": follow_up,
                    "is_finished": False,
                    "is_follow_up": True,
                    "step_index": 1,
                    "extracted_state": state,
                }
            else:
                state["had_follow_up"] = False
                if lang == "hi":
                    name_greeting = f"धन्यवाद {state['caller_name']} जी। " if state["caller_name"] != "Unknown" else "ठीक है। "
                else:
                    name_greeting = f"Thank you {state['caller_name']}. " if state["caller_name"] != "Unknown" else "Understood. "
                next_question = name_greeting + p["q2_purpose"]
                return {
                    "next_question": next_question,
                    "is_finished": False,
                    "is_follow_up": False,
                    "step_index": 2,
                    "extracted_state": state,
                }

        # Step 2: Handling answer to Q2 (Purpose)
        if step_index == 2:
            current_purpose = state.get("purpose", "")
            if not current_purpose:
                state["purpose"] = text if not self.is_silent_or_empty(text) else p["default_purpose"]
            else:
                state["purpose"] += f" ({text})"

            follow_up = None
            if not state.get("had_follow_up"):
                follow_up = self.generate_follow_up(2, text, state, lang)

            if follow_up:
                state["had_follow_up"] = True
                return {
                    "next_question": follow_up,
                    "is_finished": False,
                    "is_follow_up": True,
                    "step_index": 2,
                    "extracted_state": state,
                }
            else:
                state["had_follow_up"] = False
                return {
                    "next_question": p["q3_urgency"],
                    "is_finished": False,
                    "is_follow_up": False,
                    "step_index": 3,
                    "extracted_state": state,
                }

        # Step 3: Handling answer to Q3 (Urgency)
        if step_index == 3:
            urgency = self.analyze_urgency(text)
            state["urgency"] = urgency

            follow_up = None
            if not state.get("had_follow_up") and urgency == "High":
                follow_up = self.generate_follow_up(3, text, state, lang)

            if follow_up:
                state["had_follow_up"] = True
                return {
                    "next_question": follow_up,
                    "is_finished": False,
                    "is_follow_up": True,
                    "step_index": 3,
                    "extracted_state": state,
                }
            else:
                state["had_follow_up"] = False
                return {
                    "next_question": p["q4_message"],
                    "is_finished": False,
                    "is_follow_up": False,
                    "step_index": 4,
                    "extracted_state": state,
                }

        # Step 4: Handling answer to Q4 (Message) & Finalizing
        if step_index >= 4:
            if not state.get("message"):
                state["message"] = text if not self.is_silent_or_empty(text) else p["default_message"]

            summary_data = self.generate_final_summary(state)
            return {
                "next_question": p["closing_thanks"],
                "is_finished": True,
                "is_follow_up": False,
                "step_index": 5,
                "extracted_state": state,
                "summary": summary_data["summary_text"],
                "category": summary_data["category"],
                "urgency": summary_data["urgency"],
                "suggested_action": summary_data["suggested_action"],
                "is_spam_suspected": summary_data["is_spam_suspected"],
            }

        return {
            "next_question": p["closing_thanks"],
            "is_finished": True,
            "is_follow_up": False,
            "step_index": 5,
            "extracted_state": state,
        }

    def generate_final_summary(self, state: Dict[str, Any]) -> Dict[str, Any]:
        caller_name = state.get("caller_name") or "Unknown"
        purpose = state.get("purpose") or "Not specified"
        urgency = state.get("urgency") or "Not confirmed"
        message = state.get("message") or "No message left"

        category, is_spam = self.determine_category_and_spam(caller_name, purpose, message)

        if is_spam:
            suggested_action = "Decline or ignore."
        elif urgency == "High":
            suggested_action = "Call back immediately."
        elif category == "Work":
            suggested_action = "Call back when available."
        elif category == "Personal":
            suggested_action = "Call back when convenient."
        elif caller_name == "Unknown":
            suggested_action = "Verify identity before callback."
        else:
            suggested_action = "Call back when available."

        # Strictly formatted 5-point summary
        summary_text = (
            f"Caller: {caller_name}\n"
            f"Purpose: {purpose}\n"
            f"Urgency: {urgency}\n"
            f"Message: {message}\n"
            f"Suggested action: {suggested_action}"
        )

        return {
            "summary_text": summary_text,
            "category": category,
            "urgency": urgency,
            "suggested_action": suggested_action,
            "is_spam_suspected": is_spam,
            "caller_name": caller_name,
            "purpose": purpose,
            "message": message,
        }
