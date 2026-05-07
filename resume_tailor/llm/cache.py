from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from resume_tailor.llm.base import LLMClient


LLM_CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "llm"


@dataclass
class CachedLLMClient:
    provider: str
    model: str
    inner: LLMClient
    cache_dir: Path = LLM_CACHE_DIR

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        path = self._cache_path(system_prompt, user_prompt)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                response = str(data.get("response", ""))
                if response:
                    return response
            except (OSError, json.JSONDecodeError):
                pass

        response = self.inner.complete(system_prompt, user_prompt)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "provider": self.provider,
            "model": self.model,
            "response": response,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return response

    def _cache_path(self, system_prompt: str, user_prompt: str) -> Path:
        digest = hashlib.sha256(
            json.dumps(
                {
                    "provider": self.provider,
                    "model": self.model,
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return self.cache_dir / f"{digest}.json"
