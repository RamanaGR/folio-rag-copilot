import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5-coder:7b")
OLLAMA_FALLBACK_MODEL = os.getenv("OLLAMA_FALLBACK_MODEL", "gemma4:e4b-it-q4_K_M")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text:latest")
PROFILE_PATH = ROOT / os.getenv("PROFILE_PATH", "data/profile.yaml")
MEMORY_DB_PATH = ROOT / os.getenv("MEMORY_DB_PATH", "data/memory.db")
RESUME_PATH = ROOT / "data" / "Ramana_Gangarao_CV.pdf"


def load_profile() -> dict[str, Any]:
    with PROFILE_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}
