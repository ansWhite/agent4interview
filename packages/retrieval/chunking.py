"""Deterministic paragraph-aware text chunking."""

from __future__ import annotations


def chunk_text(text: str, chunk_size: int = 600, overlap: int = 80) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")

    paragraphs = [paragraph.strip() for paragraph in text.replace("\r\n", "\n").split("\n\n")]
    paragraphs = [paragraph for paragraph in paragraphs if paragraph]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if not current:
            current = paragraph
            continue
        candidate = f"{current}\n\n{paragraph}"
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        chunks.extend(_split_long_text(current, chunk_size, overlap))
        prefix = current[-overlap:] if overlap else ""
        current = f"{prefix}\n\n{paragraph}".strip()

    if current:
        chunks.extend(_split_long_text(current, chunk_size, overlap))
    return chunks


def _split_long_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    result: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        result.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return result
