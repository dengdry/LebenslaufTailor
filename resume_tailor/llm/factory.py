from __future__ import annotations

from resume_tailor.config import LLMSettings
from resume_tailor.llm.base import LLMClient
from resume_tailor.llm.cache import CachedLLMClient
from resume_tailor.llm.deepseek_client import DeepSeekChatClient
from resume_tailor.llm.ollama_client import OllamaClient
from resume_tailor.llm.openai_client import OpenAIResponsesClient


def build_llm_client(settings: LLMSettings) -> LLMClient | None:
    provider = settings.provider.strip().lower()
    if provider in {"", "off", "none", "rules"}:
        return None
    if provider == "openai":
        if not settings.openai_api_key:
            return None
        model = settings.model or "gpt-5.2"
        return CachedLLMClient(provider, model, OpenAIResponsesClient(
            api_key=settings.openai_api_key,
            model=model,
            base_url=settings.openai_base_url,
        ))
    if provider == "deepseek":
        if not settings.deepseek_api_key:
            return None
        model = settings.model or "deepseek-v4-flash"
        return CachedLLMClient(provider, model, DeepSeekChatClient(
            api_key=settings.deepseek_api_key,
            model=model,
            base_url=settings.deepseek_base_url,
        ))
    if provider == "ollama":
        model = settings.model or "llama3.1"
        return CachedLLMClient(provider, model, OllamaClient(
            model=model,
            base_url=settings.ollama_base_url,
        ))
    raise ValueError(f"不支持的模型服务: {settings.provider}")
