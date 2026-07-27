from __future__ import annotations

from pydantic import BaseModel, Field


class ProductAliasOut(BaseModel):
    canonical: str
    aliases: list[str] = Field(default_factory=list)
