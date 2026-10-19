"""
Telephony Provider Adapter Layer.
Provides a unified interface for telephony providers (Simulated, Twilio, Exotel).
All provider credentials and numbers are read strictly from environment variables.
Demo Mode is active by default until real credentials are fully configured.
"""

import base64
import hashlib
import hmac
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dotenv import load_dotenv

load_dotenv()


def mask_phone_number(phone: Optional[str]) -> str:
    """Masks phone number for PII privacy protection."""
    if not phone or phone in ["+1-XXXXXXXXXX", "+91-XXXXXXXXXX"]:
        return "Not configured"
    clean = re.sub(r"[^\d+]", "", phone)
    if len(clean) >= 10:
        return f"{clean[:5]}****{clean[-3:]}"
    return clean


class BaseTelephonyAdapter(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def is_demo_mode(self) -> bool:
        pass

    @abstractmethod
    def validate_webhook_signature(
        self, signature: Optional[str], url: str, params: Dict[str, Any]
    ) -> bool:
        """Validate carrier webhook cryptographic signature."""
        pass

    @abstractmethod
    def handle_incoming_call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming call webhook payload and return session data."""
        pass

    @abstractmethod
    def generate_voice_response(
        self,
        text: str,
        callback_url: str = "/api/telephony/webhook",
        listen: bool = True,
        is_final: bool = False,
        language: str = "en-IN",
    ) -> Any:
        """Generate provider-specific markup (e.g. TwiML XML or Exotel JSON) for TTS/STT."""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Return provider status and configuration details without exposing secrets."""
        pass


class SimulatedTelephonyAdapter(BaseTelephonyAdapter):
    """
    Default adapter for local development and free demonstrations.
    Runs 100% locally and free with simulated webhooks and browser Web Speech.
    Zero carrier charges, zero paid API keys required.
    """

    @property
    def provider_name(self) -> str:
        return "Simulated (Local Demo)"

    @property
    def is_demo_mode(self) -> bool:
        return True

    def validate_webhook_signature(
        self, signature: Optional[str], url: str, params: Dict[str, Any]
    ) -> bool:
        # In simulation mode, local requests are always permitted
        return True

    def handle_incoming_call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        caller_number = payload.get("caller_number", "+91 98123 45678")
        session_id = payload.get("session_id") or f"sim-{payload.get('timestamp', 'local')}"
        return {
            "status": "connected",
            "session_id": session_id,
            "caller_number": caller_number,
            "caller_number_masked": mask_phone_number(caller_number),
            "mode": "simulation",
            "demo_mode": True,
        }

    def generate_voice_response(
        self,
        text: str,
        callback_url: str = "/api/telephony/webhook",
        listen: bool = True,
        is_final: bool = False,
        language: str = "en-IN",
    ) -> Dict[str, Any]:
        return {
            "type": "simulated_tts",
            "text": text,
            "language": language,
            "listen": listen,
            "is_final": is_final,
            "callback_url": callback_url,
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "provider": "Simulated",
            "active": True,
            "demo_mode": True,
            "cost_incurred": "₹0.00 (Free)",
            "virtual_number": "Simulated Local DID",
            "owner_phone": mask_phone_number(os.getenv("OWNER_PHONE", "+91 8094725777")),
            "message": "Demo mode active. 100% free with no external carrier contracts or fees.",
        }


class TwilioAdapter(BaseTelephonyAdapter):
    """
    Adapter for Twilio Programmable Voice.
    Uses TwiML for speech recognition (<Gather>) and synthesis (<Say>).
    Credentials read strictly from environment variables.
    """

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        phone_number: Optional[str] = None,
    ):
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN", "")
        self.phone_number = phone_number or os.getenv("TWILIO_PHONE_NUMBER", "")

    @property
    def provider_name(self) -> str:
        return "Twilio Voice"

    @property
    def is_demo_mode(self) -> bool:
        # If credentials are not set, fallback to Demo Mode
        return not (bool(self.account_sid) and bool(self.auth_token))

    def validate_webhook_signature(
        self, signature: Optional[str], url: str, params: Dict[str, Any]
    ) -> bool:
        """
        Validates Twilio HMAC-SHA1 signature (X-Twilio-Signature).
        If auth token is not configured (demo mode), bypasses validation.
        """
        if self.is_demo_mode:
            return True
        if not signature:
            return False

        # Twilio signature format: URL + sorted key-value pairs
        data = url
        for key in sorted(params.keys()):
            data += f"{key}{params[key]}"

        expected_sig = base64.b64encode(
            hmac.new(
                self.auth_token.encode("utf-8"),
                data.encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode("utf-8")

        return hmac.compare_digest(signature, expected_sig)

    def handle_incoming_call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        call_sid = payload.get("CallSid", "tw-sim")
        from_number = payload.get("From", "+91 98000 00000")
        return {
            "status": "connected",
            "session_id": call_sid,
            "caller_number": from_number,
            "caller_number_masked": mask_phone_number(from_number),
            "mode": "twilio",
            "demo_mode": self.is_demo_mode,
        }

    def generate_voice_response(
        self,
        text: str,
        callback_url: str = "/api/telephony/webhook",
        listen: bool = True,
        is_final: bool = False,
        language: str = "en-IN",
    ) -> str:
        """
        Generates standard TwiML XML with speech recognition gathering.
        """
        twiml = '<?xml version="1.0" encoding="UTF-8"?>\n<Response>\n'
        if listen and not is_final:
            twiml += (
                f'  <Gather input="speech" language="{language}" speechTimeout="auto" action="{callback_url}" method="POST">\n'
                f'    <Say language="{language}">{text}</Say>\n'
                f"  </Gather>\n"
                f'  <Say language="{language}">I did not receive your response. Thank you, goodbye.</Say>\n'
                f"  <Hangup/>\n"
            )
        else:
            twiml += f'  <Say language="{language}">{text}</Say>\n'
            twiml += "  <Hangup/>\n"
        twiml += "</Response>"
        return twiml

    def get_status(self) -> Dict[str, Any]:
        configured = not self.is_demo_mode
        return {
            "provider": "Twilio Voice",
            "active": configured,
            "demo_mode": self.is_demo_mode,
            "virtual_number": mask_phone_number(self.phone_number) if self.phone_number else "Not configured",
            "owner_phone": mask_phone_number(os.getenv("OWNER_PHONE", "+91 8094725777")),
            "status": "Configured & Ready for live webhooks" if configured else "Demo Mode (Credentials not set in .env)",
            "cost_incurred": "Metered by carrier" if configured else "₹0.00 (Demo Mode)",
        }


class ExotelAdapter(BaseTelephonyAdapter):
    """
    Adapter for Exotel (Major Indian Telephony Provider).
    Supports Indian mobile numbers (+91) with English & Hindi audio prompts.
    Credentials read strictly from environment variables.
    """

    def __init__(
        self,
        account_sid: Optional[str] = None,
        api_key: Optional[str] = None,
        api_token: Optional[str] = None,
        virtual_number: Optional[str] = None,
    ):
        self.account_sid = account_sid or os.getenv("EXOTEL_ACCOUNT_SID", "")
        self.api_key = api_key or os.getenv("EXOTEL_API_KEY", "")
        self.api_token = api_token or os.getenv("EXOTEL_API_TOKEN", "")
        self.virtual_number = virtual_number or os.getenv("EXOTEL_VIRTUAL_NUMBER", "")

    @property
    def provider_name(self) -> str:
        return "Exotel (India +91)"

    @property
    def is_demo_mode(self) -> bool:
        return not (bool(self.account_sid) and bool(self.api_token))

    def validate_webhook_signature(
        self, signature: Optional[str], url: str, params: Dict[str, Any]
    ) -> bool:
        if self.is_demo_mode:
            return True
        if not signature:
            return False
        # Exotel token comparison
        return hmac.compare_digest(signature, self.api_token)

    def handle_incoming_call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        call_sid = payload.get("CallSid", payload.get("CallSid", "exo-sim"))
        from_number = payload.get("From", payload.get("CallFrom", "+91 98000 00000"))
        return {
            "status": "connected",
            "session_id": call_sid,
            "caller_number": from_number,
            "caller_number_masked": mask_phone_number(from_number),
            "mode": "exotel",
            "demo_mode": self.is_demo_mode,
        }

    def generate_voice_response(
        self,
        text: str,
        callback_url: str = "/api/telephony/webhook",
        listen: bool = True,
        is_final: bool = False,
        language: str = "en-IN",
    ) -> Dict[str, Any]:
        return {
            "action": "play_and_record" if (listen and not is_final) else "play_and_hangup",
            "prompt_text": text,
            "language": language,
            "callback_url": callback_url,
            "gather": listen and not is_final,
        }

    def get_status(self) -> Dict[str, Any]:
        configured = not self.is_demo_mode
        return {
            "provider": "Exotel (India)",
            "active": configured,
            "demo_mode": self.is_demo_mode,
            "virtual_number": mask_phone_number(self.virtual_number) if self.virtual_number else "Not configured",
            "owner_phone": mask_phone_number(os.getenv("OWNER_PHONE", "+91 8094725777")),
            "status": "Configured & Ready for live webhooks" if configured else "Demo Mode (Credentials not set in .env)",
            "cost_incurred": "Metered by carrier" if configured else "₹0.00 (Demo Mode)",
        }


def get_telephony_adapter(provider_type: Optional[str] = None) -> BaseTelephonyAdapter:
    """
    Factory function to retrieve the configured telephony adapter.
    Defaults to SimulatedTelephonyAdapter (100% Free Demo Mode).
    """
    provider = (provider_type or os.getenv("TELEPHONY_PROVIDER", "simulated")).lower().strip()
    if provider == "twilio":
        return TwilioAdapter()
    elif provider == "exotel":
        return ExotelAdapter()
    return SimulatedTelephonyAdapter()
