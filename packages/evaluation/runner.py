"""Configuration-stamped evaluation runner."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from pydantic import BaseModel, Field

from packages.agent_core.models import AgentState
from packages.evaluation.metrics import citation_metrics, retrieval_metrics


class EvalCase(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    question: str
    relevant_document_ids: set[str] = Field(default_factory=set)
    required_document_ids: set[str] = Field(default_factory=set)
    tags: list[str] = Field(default_factory=list)


class EvalResult(BaseModel):
    case_id: str
    trace_id: str
    status: str
    latency_ms: float
    metrics: dict[str, float]
    warnings: list[str]


class EvaluationRunner:
    def __init__(self, execute: Callable[[str], Awaitable[AgentState]]) -> None:
        self.execute = execute

    async def run(self, cases: list[EvalCase]) -> list[EvalResult]:
        results: list[EvalResult] = []
        for case in cases:
            started = time.perf_counter()
            state = await self.execute(case.question)
            latency_ms = (time.perf_counter() - started) * 1000
            retrieved = [item.document_id for item in state.evidence]
            cited = [item.document_id for item in state.citations]
            metrics = retrieval_metrics(retrieved, case.relevant_document_ids)
            metrics.update(
                citation_metrics(cited, case.relevant_document_ids, case.required_document_ids)
            )
            metrics["task_success"] = float(state.status == "completed")
            metrics["steps"] = float(state.budget.steps_used)
            results.append(
                EvalResult(
                    case_id=case.id,
                    trace_id=state.trace_id,
                    status=state.status,
                    latency_ms=round(latency_ms, 3),
                    metrics=metrics,
                    warnings=state.warnings,
                )
            )
        return results
