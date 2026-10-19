"""
Run script for Personal AI Call Assistant.
Starts the FastAPI server with uvicorn and optional ngrok public tunnel.
"""
import os
import sys
from dotenv import load_dotenv
import uvicorn

load_dotenv()

def start_ngrok(port: int = 8000) -> str:
    """Starts an ngrok tunnel using pyngrok and returns the public URL."""
    try:
        from pyngrok import ngrok, conf
        
        token = os.getenv("NGROK_AUTHTOKEN")
        if token:
            ngrok.set_auth_token(token)
            
        tunnel = ngrok.connect(port, "http")
        public_url = tunnel.public_url
        if public_url.startswith("http://"):
            public_url = public_url.replace("http://", "https://", 1)
        return public_url
    except Exception as e:
        print(f"⚠️  Could not start ngrok tunnel: {e}")
        print("Tip: Get your free auth token at https://dashboard.ngrok.com/get-started/your-authtoken")
        return ""

if __name__ == "__main__":
    port = 8000
    host = "0.0.0.0"

    print("=" * 65)
    print("🤖 PERSONAL AI CALL ASSISTANT (HINDI CALL SCREENING)")
    print("=" * 65)
    print("• Mode: Demo Mode (100% Free • No Real Calls or Paid APIs)")
    print("• Language: Hindi (हिंदी)")
    print(f"• Local Web UI: http://localhost:{port}")
    print(f"• Local Network (Mobile Wi-Fi): http://10.179.220.156:{port}")
    print(f"• Documentation: http://localhost:{port}/docs")

    use_ngrok = "--ngrok" in sys.argv or bool(os.getenv("NGROK_AUTHTOKEN"))
    if use_ngrok:
        public_url = start_ngrok(port)
        if public_url:
            print(f"🌐 Public Live URL (Mobile / Webhook): {public_url}")
            print(f"   Webhook Endpoint: {public_url}/api/telephony/webhook")
    else:
        print("• Tip: Pass --ngrok to get a free live public URL for mobile access")

    print("=" * 65)
    print("Starting server... Press Ctrl+C to stop.\n")

    uvicorn.run("app.main:app", host=host, port=port, reload=True)
