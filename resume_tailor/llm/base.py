from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return a model completion for the given prompts."""
