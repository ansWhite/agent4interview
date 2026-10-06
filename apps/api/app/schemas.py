"""Public API request and response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from packages.agent_core.models import AgentState, Budget
from packages.evaluation.runner import EvalCase, EvalResult


class ErrorDetail(BaseModel):
    code: str
    message: str
    trace_id: str | None = None


class CreateTaskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    budget: Budget = Field(default_factory=Budget)


class TaskResponse(BaseModel):
    id: str
    state: AgentState


class CreateDocumentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=200_000)
    source: str = Field(default="local", max_length=200)


class CreateDocumentResponse(BaseModel):
    document_ids: list[str]
    chunks: int


class CreateEvalRunRequest(BaseModel):
    name: str = Field(default="experiment", min_length=1, max_length=100)
    cases: list[EvalCase] = Field(min_length=1, max_length=100)


class EvalRunResponse(BaseModel):
    id: str
    name: str
    status: str
    results: list[EvalResult] = Field(default_factory=list)
    summary: dict[str, float] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
