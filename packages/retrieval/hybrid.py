"""Dependency-light BM25 + hashed dense retrieval with RRF fusion."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from uuid import uuid4

from pydantic import BaseModel, Field

from packages.agent_core.models import Evidence

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_+#.-]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_PATTERN.findall(text)]


class Document(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    content: str
    source: str = "local"
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class SearchHit(BaseModel):
    document: Document
    score: float
    lexical_score: float
    dense_score: float
    rank_score: float

    def to_evidence(self) -> Evidence:
        return Evidence(
            document_id=self.document.id,
            title=self.document.title,
            content=self.document.content,
            source=self.document.source,
            score=self.score,
            metadata=self.document.metadata,
        )


class HybridRetriever:
    def __init__(self, dimensions: int = 128, rrf_k: int = 60) -> None:
        self.dimensions = dimensions
        self.rrf_k = rrf_k
        self._documents: dict[str, Document] = {}
        self._tokens: dict[str, list[str]] = {}
        self._vectors: dict[str, list[float]] = {}
        self._document_frequency: Counter[str] = Counter()

    @property
    def size(self) -> int:
        return len(self._documents)

    def add(self, documents: list[Document]) -> None:
        for document in documents:
            if document.id in self._documents:
                self.remove(document.id)
            tokens = tokenize(f"{document.title} {document.content}")
            self._documents[document.id] = document
            self._tokens[document.id] = tokens
            self._vectors[document.id] = self._embed(tokens)
            self._document_frequency.update(set(tokens))

    def remove(self, document_id: str) -> None:
        tokens = self._tokens.pop(document_id, [])
        self._documents.pop(document_id, None)
        self._vectors.pop(document_id, None)
        for token in set(tokens):
            self._document_frequency[token] -= 1
            if self._document_frequency[token] <= 0:
                del self._document_frequency[token]

    def search(self, query: str, limit: int = 5) -> list[SearchHit]:
        if not query.strip() or not self._documents or limit <= 0:
            return []
        query_tokens = tokenize(query)
        query_vector = self._embed(query_tokens)
        lexical = {
            document_id: self._bm25(query_tokens, document_id) for document_id in self._documents
        }
        dense = {
            document_id: max(0.0, self._cosine(query_vector, vector))
            for document_id, vector in self._vectors.items()
        }
        lexical_rank = self._rank(lexical)
        dense_rank = self._rank(dense)
        fused = {
            document_id: 1 / (self.rrf_k + lexical_rank[document_id])
            + 1 / (self.rrf_k + dense_rank[document_id])
            for document_id in self._documents
        }
        max_fused = max(fused.values(), default=1.0)
        hits: list[SearchHit] = []
        query_unique = set(query_tokens)
        for document_id, document in self._documents.items():
            coverage = len(query_unique & set(self._tokens[document_id])) / max(
                1, len(query_unique)
            )
            normalized_rrf = fused[document_id] / max_fused
            has_signal = lexical[document_id] > 0 or dense[document_id] > 0
            final_score = (0.75 * normalized_rrf + 0.25 * coverage) if has_signal else 0.0
            hits.append(
                SearchHit(
                    document=document,
                    score=round(final_score, 6),
                    lexical_score=round(lexical[document_id], 6),
                    dense_score=round(dense[document_id], 6),
                    rank_score=round(fused[document_id], 6),
                )
            )
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:limit]

    def _bm25(self, query_tokens: list[str], document_id: str) -> float:
        tokens = self._tokens[document_id]
        frequencies = Counter(tokens)
        average_length = sum(map(len, self._tokens.values())) / max(1, len(self._tokens))
        score = 0.0
        k1, b = 1.5, 0.75
        for token in query_tokens:
            frequency = frequencies[token]
            if not frequency:
                continue
            document_frequency = self._document_frequency[token]
            idf = math.log(
                1 + (len(self._documents) - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            denominator = frequency + k1 * (1 - b + b * len(tokens) / max(1.0, average_length))
            score += idf * frequency * (k1 + 1) / denominator
        return score

    def _embed(self, tokens: list[str]) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest, "big") % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right, strict=True))

    @staticmethod
    def _rank(scores: dict[str, float]) -> dict[str, int]:
        ordered = sorted(scores, key=lambda key: (-scores[key], key))
        return {document_id: index for index, document_id in enumerate(ordered, start=1)}
