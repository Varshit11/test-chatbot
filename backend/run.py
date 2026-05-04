"""Local dev entry-point: `python run.py`."""
import os
import sys
import uvicorn

# Make the parent (quantflow/) importable as `backend.*`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    uvicorn.run(
        "backend.api.main:app",
        host=os.environ.get("QUANTFLOW_HOST", "127.0.0.1"),
        port=int(os.environ.get("QUANTFLOW_PORT", "8000")),
        reload=os.environ.get("QUANTFLOW_RELOAD", "true").lower() == "true",
    )
