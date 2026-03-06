from dataclasses import dataclass
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Swarm Strategy Backend")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    default_rounds: int = int(os.getenv("DEFAULT_SWARM_ROUNDS", "3"))

    # Gemini
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    gemini_enabled: bool = os.getenv("GEMINI_ENABLED", "false").lower() == "true"

    # Ollama (local fallback)
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    ollama_timeout_seconds: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "45"))
    ollama_use_chat: bool = os.getenv("OLLAMA_USE_CHAT", "false").lower() == "true"
    ollama_enabled: bool = os.getenv("OLLAMA_ENABLED", "true").lower() == "true"


settings = Settings()
