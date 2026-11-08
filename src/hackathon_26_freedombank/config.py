import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]  # project root
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")
DB_ECHO = os.getenv("DB_ECHO", "false").lower() == "true"  # log SQL statements


def _csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


TEAM_NAME = os.getenv("TEAM_NAME", "Я и Нурай")  # team_name in results.json

# --- LLM -------------------------------------------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()  # "gemini" (cloud) | "ollama" (local)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
# Thinking models (qwen3.5, ...) can "think" for thousands of tokens and never answer: off by default.
OLLAMA_THINK = os.getenv("OLLAMA_THINK", "false").lower() == "true"
# Context window. Ollama's default (4096) is smaller than the prompt for long dialogues (~7.6k tokens).
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "16384"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "4096"))  # max answer tokens (stops runaway output)
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0"))
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "600"))  # seconds per request

# --- CORS (frontend is served from a separate static server) ----------------
CORS_ORIGINS = _csv(os.getenv("CORS_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500"))
