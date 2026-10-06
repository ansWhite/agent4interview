"""Confidence- and freshness-aware long-term memory selection."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from packages.retrieval.hybrid import tokenize


class MemoryItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str
    kind: str = "fact"
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None


class MemoryStore:
    def __init__(self) -> None:
        self._items: dict[str, MemoryItem] = {}

    def remember(self, item: MemoryItem) -> None:
        self._items[item.id] = item

    def recall(self, query: str, limit: int = 5, now: datetime | None = None) -> list[MemoryItem]:
        current = now or datetime.now(UTC)
        query_tokens = set(tokenize(query))
        ranked: list[tuple[float, MemoryItem]] = []
        for item in self._items.values():
            if item.expires_at is not None and item.expires_at <= current:
                continue
            item_tokens = set(tokenize(item.content))
            relevance = len(query_tokens & item_tokens) / max(1, len(query_tokens | item_tokens))
            age_days = max(0.0, (current - item.created_at).total_seconds() / 86400)
            freshness = math.exp(-age_days / 90)
            score = 0.65 * relevance + 0.25 * item.confidence + 0.10 * freshness
            if relevance > 0:
                ranked.append((score, item))
        ranked.sort(key=lambda pair: (-pair[0], pair[1].id))
        return [item for _, item in ranked[:limit]]
