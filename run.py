"""
PDF Footer Editor - Application Runner
"""
import uvicorn
import webbrowser
import threading
import time
import os
import sys


def open_browser():
    """Open browser after a short delay."""
    time.sleep(2.0)
    webbrowser.open("http://localhost:8000")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print("=" * 50)
    print("  PDF Footer Editor")
    print("=" * 50)
    print(f"  Starting server at http://localhost:{port}")
    print("  Press Ctrl+C to stop")
    print("=" * 50)
    
    if not os.environ.get("RENDER"):
        threading.Thread(target=open_browser, daemon=True).start()
    
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
