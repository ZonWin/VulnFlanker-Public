from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AICompletionPayload(BaseModel):
    messages: list[dict[str, str]]
    metadata: dict[str, Any] = {}

