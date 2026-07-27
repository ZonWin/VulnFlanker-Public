from __future__ import annotations

from app.ai.base import AIProviderClient
from app.ai.providers.fake import FakeAIProviderClient
from app.ai.providers.openai_compatible import OpenAICompatibleProviderClient


def build_provider_client(provider: str) -> AIProviderClient:
    normalized = provider.strip().lower()
    if normalized == "fake":
        return FakeAIProviderClient()
    if normalized == "openai_compatible":
        return OpenAICompatibleProviderClient()
    raise ValueError(f"Unsupported AI provider: {provider}")

