"""LLM diagnostics — useful while wiring up your Claude API key."""
from __future__ import annotations
from fastapi import APIRouter

from ..config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, llm_mode

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/status")
def status():
    masked = ""
    if ANTHROPIC_API_KEY:
        k = ANTHROPIC_API_KEY
        masked = f"{k[:7]}…{k[-4:]}" if len(k) > 12 else "set"
    return {
        "mode": llm_mode(),
        "api_key_present": bool(ANTHROPIC_API_KEY),
        "api_key_preview": masked,
        "model": ANTHROPIC_MODEL,
    }


@router.post("/test")
def test_call():
    """Round-trip a tiny request to Claude to confirm the key works."""
    if llm_mode() != "claude":
        return {
            "ok": False,
            "mode": llm_mode(),
            "error": "Claude mode is not active. Set ANTHROPIC_API_KEY in your .env "
                     "(or environment) and restart the backend.",
        }
    try:
        import anthropic  # type: ignore
    except ImportError:
        return {"ok": False, "error": "anthropic SDK not installed. Run: pip install anthropic"}

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=64,
            temperature=0.0,
            messages=[{"role": "user", "content": "Reply with exactly the word: PONG"}],
        )
        text = "\n".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
        return {
            "ok": True,
            "mode": "claude",
            "model": ANTHROPIC_MODEL,
            "response": text,
            "input_tokens": getattr(msg.usage, "input_tokens", None),
            "output_tokens": getattr(msg.usage, "output_tokens", None),
        }
    except Exception as e:
        return {
            "ok": False,
            "mode": "claude",
            "model": ANTHROPIC_MODEL,
            "error": f"{type(e).__name__}: {e}",
        }
