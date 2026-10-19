"""
Run script for Personal AI Call Assistant.
Starts the FastAPI server with uvicorn.
"""
import sys
import uvicorn

if __name__ == "__main__":
    print("=" * 65)
    print("🤖 PERSONAL AI CALL ASSISTANT (HINDI CALL SCREENING)")
    print("=" * 65)
    print("• Mode: Demo Mode (100% Free • No Real Calls or Paid APIs)")
    print("• Language: Hindi (हिंदी)")
    print("• Local Web UI: http://127.0.0.1:8000")
    print("• Documentation: http://127.0.0.1:8000/docs")
    print("=" * 65)
    print("Starting server... Press Ctrl+C to stop.\n")

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
