"""Typed state shared by every Agent node."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class Budget(BaseModel):
    max_steps: int = Field(default=8, ge=1, le=32)
    max_tool_calls: int = Field(default=12, ge=0, le=64)
    max_retries: int = Field(default=1, ge=0, le=3)
    steps_used: int = 0
    tool_calls_used: int = 0
    retries_used: int = 0

    def consume_step(self) -> bool:
        if self.steps_used >= self.max_steps:
            return False
        self.steps_used += 1
        return True

    def consume_tool_call(self) -> bool:
        if self.tool_calls_used >= self.max_tool_calls:
            return False
        self.tool_calls_used += 1
        return True

    def consume_retry(self) -> bool:
        if self.retries_used >= self.max_retries:
            return False
        self.retries_used += 1
        return True


class ResearchStep(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    query: str
    dependencies: list[str] = Field(default_factory=list)
    status: StepStatus = StepStatus.PENDING


class Evidence(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    document_id: str
    title: str
    content: str
    score: float = Field(ge=0.0)
    source: str = "local"
    metadata: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    marker: str
    evidence_id: str
    document_id: str
    quote: str


class AgentEvent(BaseModel):
    sequence: int
    trace_id: str
    event_type: str
    node: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentState(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    question: str
    status: TaskStatus = TaskStatus.PENDING
    steps: list[ResearchStep] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    answer: str | None = None
    warnings: list[str] = Field(default_factory=list)
    budget: Budget = Field(default_factory=Budget)
    model_version: str = "deterministic-fake-v1"
    retrieval_version: str = "hybrid-rrf-v1"
    prompt_version: str = "research-v1"
    started_at: datetime | None = None
    completed_at: datetime | None = None


EventSink = Any
