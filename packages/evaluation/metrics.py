"""Deterministic metrics used for retrieval and citation experiments."""

from __future__ import annotations

import math
from collections.abc import Sequence


def retrieval_metrics(retrieved: Sequence[str], relevant: set[str], k: int = 5) -> dict[str, float]:
    top = list(retrieved[:k])
    if not relevant:
        return {"recall_at_k": 1.0 if not top else 0.0, "mrr": 0.0, "ndcg": 0.0}
    hits = [1 if item in relevant else 0 for item in top]
    recall = sum(hits) / len(relevant)
    reciprocal_rank = next((1 / index for index, hit in enumerate(hits, start=1) if hit), 0.0)
    dcg = sum(hit / math.log2(index + 1) for index, hit in enumerate(hits, start=1))
    ideal_hits = [1] * min(len(relevant), k)
    idcg = sum(hit / math.log2(index + 1) for index, hit in enumerate(ideal_hits, start=1))
    return {
        "recall_at_k": round(recall, 6),
        "mrr": round(reciprocal_rank, 6),
        "ndcg": round(dcg / idcg if idcg else 0.0, 6),
    }


def citation_metrics(
    cited_document_ids: Sequence[str],
    supported_document_ids: set[str],
    required_document_ids: set[str],
) -> dict[str, float]:
    cited = set(cited_document_ids)
    correct = len(cited & supported_document_ids)
    precision = correct / len(cited) if cited else 0.0
    completeness = (
        len(cited & required_document_ids) / len(required_document_ids)
        if required_document_ids
        else 1.0
    )
    return {
        "citation_precision": round(precision, 6),
        "citation_completeness": round(completeness, 6),
    }
