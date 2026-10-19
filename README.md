# 📞 Personal AI Call Assistant

An intelligent, AI-powered call screening assistant designed for personal calls. When you don't answer or reject an incoming call, the assistant answers, greets the caller in Hindi or English, inquires about their identity and purpose, evaluates urgency, and presents structured summaries with real-time alerts on your personal dashboard.

---

## ✨ Features

- **Automated Call Screening:** Asks who is calling and why, maintaining natural multi-turn conversations.
- **Bilingual Support (Hindi & English):** Default Hindi screening with polite greetings tailored for Indian callers.
- **Urgency & Intent Detection:** Automatically categorizes calls (Urgent, Work, Personal, Spam/Marketing) using rule-based and NLP classification.
- **Real-Time Dashboard:** Modern web interface displaying call metrics, audio transcripts, caller identities, and action buttons (Callback, Accept, Decline).
- **Flexible Telephony:**
  - **Simulated Mode (Default):** 100% free local testing in the browser with Web Speech synthesis and recognition.
  - **Exotel & Twilio Integration:** Ready for live carrier webhook integration with Indian virtual DID numbers.
- **Dual Database Support:** Works seamlessly with PostgreSQL (Supabase) or local SQLite fallback.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- `pip`

### 2. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/Rohit-k2007/AI-Personal-Assistant-.git
cd AI-Personal-Assistant-
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Update your variables in `.env`:
```env
TELEPHONY_PROVIDER=simulated
OWNER_PHONE=+918094725777
OWNER_NAME=Rohit Khandelwal
ASSISTANT_LANGUAGE=hi
DATABASE_URL=postgresql://user:password@host:5432/postgres  # Optional (falls back to local SQLite)
```

### 4. Run the Application
```bash
python run.py
```
Open your browser at: **`http://localhost:8000`**

---

## 📱 Using on Mobile (PWA)

1. Connect your phone and PC to the same Wi-Fi network.
2. Find your PC's IP address (e.g. `10.179.220.156` via `ipconfig`).
3. Open `http://<YOUR_PC_IP>:8000` in Chrome (Android) or Safari (iPhone).
4. Tap **Add to Home screen** / **Install App** to use it like a native mobile app.

---

## 🔗 Connecting a Real Mobile Number

To have the assistant answer when you miss a call on your personal mobile:

1. **Get an Inbound DID Virtual Number** from Exotel or Twilio India.
2. **Expose your webhook** (e.g., using `ngrok http 8000` or deploying to Render/Railway).
3. Set the webhook URL on your telephony provider to:
   `https://your-domain.com/api/telephony/webhook`
4. **Set Conditional Forwarding on your Mobile**:
   Dial the GSM code on your phone:
   ```
   *61*<VirtualNumber>*11*25#
   ```
   *(Forwards to your assistant if unanswered after 25 seconds. Cancel anytime with `##61#`)*

---

## 🛡️ Privacy & Security
- Sensitive credentials, auth tokens, and `.env` files are excluded from version control via `.gitignore`.
- Phone numbers in transcripts and UI can be masked for PII privacy.