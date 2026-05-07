from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


APP_CONFIG_DIR = Path(__file__).resolve().parents[1] / ".config"
APP_CONFIG_FILE = APP_CONFIG_DIR / "settings.json"


@dataclass
class LLMSettings:
    provider: str = "off"
    model: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    ollama_base_url: str = "http://localhost:11434"

    @classmethod
    def from_env(cls) -> "LLMSettings":
        provider = os.getenv("RESUME_TAILOR_LLM", "off").strip().lower()
        model = os.getenv("RESUME_TAILOR_MODEL", "").strip()
        if provider == "openai" and not model:
            model = "gpt-5.2"
        if provider == "deepseek" and not model:
            model = "deepseek-v4-flash"
        if provider == "ollama" and not model:
            model = "llama3.1"
        return cls(
            provider=provider,
            model=model,
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
        )

    @classmethod
    def load(cls) -> "LLMSettings":
        settings = cls.from_env()
        if not APP_CONFIG_FILE.exists():
            return settings
        try:
            data = json.loads(APP_CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return settings
        settings.provider = str(data.get("provider") or settings.provider).strip().lower()
        settings.model = str(data.get("model") or settings.model).strip()
        settings.openai_api_key = str(data.get("openai_api_key") or settings.openai_api_key).strip()
        settings.deepseek_api_key = str(data.get("deepseek_api_key") or settings.deepseek_api_key).strip()
        settings.openai_base_url = str(data.get("openai_base_url") or settings.openai_base_url).rstrip("/")
        settings.deepseek_base_url = str(data.get("deepseek_base_url") or settings.deepseek_base_url).rstrip("/")
        settings.ollama_base_url = str(data.get("ollama_base_url") or settings.ollama_base_url).rstrip("/")
        return settings

    def save(self) -> None:
        APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "provider": self.provider,
            "model": self.model,
            "openai_api_key": self.openai_api_key,
            "deepseek_api_key": self.deepseek_api_key,
            "openai_base_url": self.openai_base_url,
            "deepseek_base_url": self.deepseek_base_url,
            "ollama_base_url": self.ollama_base_url,
        }
        APP_CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
