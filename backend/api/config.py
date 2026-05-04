"""Runtime configuration."""
from __future__ import annotations
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Auto-load .env from quantflow/ root (next to README.md). Silently no-op if
# python-dotenv isn't installed or the file doesn't exist.
try:
    from dotenv import load_dotenv  # type: ignore
    _ENV_PATH = os.path.join(BASE_DIR, ".env")
    if os.path.exists(_ENV_PATH):
        load_dotenv(_ENV_PATH, override=False)
except Exception:
    pass

# Database (SQLite for MVP; swap DATABASE_URL env to a Postgres DSN to upgrade)
DATABASE_URL = (
    os.environ.get("QUANTFLOW_DATABASE_URL")
    or f"sqlite:///{os.path.join(BASE_DIR, 'quantflow.db')}"
)

# LLM
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
LLM_MODE = os.environ.get("QUANTFLOW_LLM_MODE", "auto")   # "auto" | "claude" | "mock"

# Backtest defaults
DEFAULT_INITIAL_CAPITAL = float(os.environ.get("QUANTFLOW_INITIAL_CAPITAL", "100000"))
DEFAULT_POSITION_SIZE = float(os.environ.get("QUANTFLOW_POSITION_SIZE", "1.0"))
DEFAULT_DATA_LIMIT = int(os.environ.get("QUANTFLOW_DATA_LIMIT", "20000"))

# How many prior chat messages (user + assistant) to pass to Claude when parsing
# a new strategy or refinement — keeps long tuning threads coherent.
CONVERSATION_HISTORY_MESSAGES = int(os.environ.get("QUANTFLOW_HISTORY_MESSAGES", "60"))

# CORS
ALLOWED_ORIGINS = os.environ.get(
    "QUANTFLOW_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
).split(",")


def llm_mode() -> str:
    """Return the effective LLM mode."""
    if LLM_MODE == "claude":
        return "claude"
    if LLM_MODE == "mock":
        return "mock"
    return "claude" if ANTHROPIC_API_KEY else "mock"
