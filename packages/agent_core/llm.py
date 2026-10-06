"""Provider-neutral model interface and deterministic local implementation."""

from __future__ import annotations

import re
from typing import Protocol

from packages.agent_core.models import Evidence, ResearchStep


class ModelProvider(Protocol):
    name: str

    async def plan(self, question: str, max_steps: int) -> list[ResearchStep]: ...

    async def synthesize(self, question: str, evidence: list[Evidence]) -> str: ...

    async def revise(self, answer: str, issues: list[str], evidence: list[Evidence]) -> str: ...


class DeterministicFakeModel:
    """A stable model used by tests and offline demos.

    It deliberately performs simple transformations. Real providers can implement
    the same protocol without leaking credentials into orchestration code.
    """

    name = "deterministic-fake-v1"

    async def plan(self, question: str, max_steps: int) -> list[ResearchStep]:
        parts = [part.strip() for part in re.split(r"[？?；;。]", question) if part.strip()]
        if len(parts) == 1:
            parts = [f"定义与背景：{question}", f"核心机制与证据：{question}"]
        return [
            ResearchStep(title=f"子任务 {index + 1}", query=part)
            for index, part in enumerate(parts[:max_steps])
        ]

    async def synthesize(self, question: str, evidence: list[Evidence]) -> str:
        if not evidence:
            return "现有知识库没有足够证据回答该问题。"
        lines = [f"针对“{question}”，本地证据支持以下结论："]
        for index, item in enumerate(evidence[:5], start=1):
            summary = " ".join(item.content.strip().split())[:180]
            lines.append(f"- {summary} [{index}]")
        return "\n".join(lines)

    async def revise(self, answer: str, issues: list[str], evidence: list[Evidence]) -> str:
        if not issues:
            return answer
        if not evidence:
            return "现有知识库没有足够证据回答该问题。"
        return answer + "\n\n限制：" + "；".join(issues)
