import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent
INBOX_PATH = Path(os.getenv("INBOX_PATH", BASE_DIR / "inbox.json"))
PREFS_PATH = Path(os.getenv("PREFS_PATH", BASE_DIR / "prefs.json"))
TRACE_PATH = Path(os.getenv("TRACE_PATH", BASE_DIR / "trace.jsonl"))
OUTBOX_DIR = Path(os.getenv("OUTBOX_DIR", BASE_DIR / "outbox"))

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:26b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

LLM_MODEL = OLLAMA_MODEL if LLM_PROVIDER == "ollama" else GEMINI_MODEL
OFFLINE_MODE = os.getenv("INBOXHERO_OFFLINE", "0") == "1"


def validate_llm_config():
    if OFFLINE_MODE:
        return
    if LLM_PROVIDER == "gemini" and not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. Copy .env.example to .env and add your Gemini API key."
        )
    if LLM_PROVIDER == "ollama":
        if not OLLAMA_MODEL:
            raise RuntimeError("OLLAMA_MODEL is not configured.")
        if not OLLAMA_BASE_URL:
            raise RuntimeError("OLLAMA_BASE_URL is not configured.")
    if LLM_PROVIDER not in {"gemini", "ollama"}:
        raise RuntimeError(
            f"Unsupported LLM_PROVIDER={LLM_PROVIDER!r}; choose 'ollama' or 'gemini'."
        )

# Security-first identity context
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "sam@paperjet.io")
OWNER_DOMAIN = os.getenv("OWNER_DOMAIN", "paperjet.io")
