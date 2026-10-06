"""Bounded research workflow with explicit, observable state transitions."""

from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from packages.agent_core.llm import ModelProvider
from packages.agent_core.models import (
    AgentEvent,
    AgentState,
    Citation,
    Evidence,
    StepStatus,
    TaskStatus,
)
from packages.retrieval.hybrid import HybridRetriever
from packages.tools.registry import ToolRegistry

EventSink = Callable[[AgentEvent], Awaitable[None] | None]


class ResearchAgent:
    """Runs a finite workflow and emits every important decision as an event."""

    def __init__(
        self,
        model: ModelProvider,
        retriever: HybridRetriever,
        tools: ToolRegistry | None = None,
        min_evidence_score: float = 0.08,
    ) -> None:
        self.model = model
        self.retriever = retriever
        self.tools = tools or ToolRegistry()
        self.min_evidence_score = min_evidence_score
        self._sequence = 0

    async def run(self, state: AgentState, sink: EventSink | None = None) -> AgentState:
        state.status = TaskStatus.RUNNING
        state.started_at = datetime.now(UTC)
        await self._emit(state, sink, "task_started", "intake", "任务开始")
        try:
            await self._plan(state, sink)
            await self._research(state, sink)
            await self._synthesize(state, sink)
            await self._verify(state, sink)
            state.status = TaskStatus.COMPLETED if state.evidence else TaskStatus.PARTIAL
        except Exception as exc:  # workflow boundary intentionally catches provider failures
            state.status = TaskStatus.FAILED
            state.warnings.append(f"workflow_error:{type(exc).__name__}")
            await self._emit(
                state,
                sink,
                "task_failed",
                "workflow",
                "任务执行失败",
                {"error": str(exc)},
            )
        finally:
            state.completed_at = datetime.now(UTC)
            await self._emit(
                state,
                sink,
                "task_finished",
                "workflow",
                f"任务状态：{state.status}",
                {"status": state.status, "budget": state.budget.model_dump()},
            )
        return state

    async def _plan(self, state: AgentState, sink: EventSink | None) -> None:
        if not state.budget.consume_step():
            raise RuntimeError("step budget exhausted before planning")
        await self._emit(state, sink, "node_started", "planner", "正在拆解研究问题")
        state.steps = await self.model.plan(state.question, max(1, state.budget.max_steps - 3))
        await self._emit(
            state,
            sink,
            "node_completed",
            "planner",
            f"生成 {len(state.steps)} 个子任务",
            {"steps": [step.model_dump(mode="json") for step in state.steps]},
        )

    async def _research(self, state: AgentState, sink: EventSink | None) -> None:
        seen: set[str] = set()
        for step in state.steps:
            if not state.budget.consume_step():
                state.warnings.append("step_budget_exhausted")
                break
            step.status = StepStatus.RUNNING
            await self._emit(state, sink, "node_started", "retriever", step.query)
            hits = self.retriever.search(step.query, limit=4)
            accepted = [hit.to_evidence() for hit in hits if hit.score >= self.min_evidence_score]
            tool_evidence = await self._maybe_calculate(state, step.query, sink)
            if tool_evidence is not None:
                accepted.append(tool_evidence)
            for item in accepted:
                if item.document_id not in seen:
                    state.evidence.append(item)
                    seen.add(item.document_id)
            step.status = StepStatus.COMPLETED
            await self._emit(
                state,
                sink,
                "node_completed",
                "evidence_grader",
                f"接受 {len(accepted)} 条证据",
                {"query": step.query, "accepted": len(accepted)},
            )

    async def _maybe_calculate(
        self,
        state: AgentState,
        query: str,
        sink: EventSink | None,
    ) -> Evidence | None:
        match = re.search(r"(?<![\w.])([\d\s()+\-*/%.]{3,})(?![\w.])", query)
        if match is None or not any(operator in match.group(1) for operator in "+-*/%"):
            return None
        if not state.budget.consume_tool_call():
            state.warnings.append("tool_budget_exhausted")
            return None
        expression = match.group(1).strip()
        await self._emit(state, sink, "tool_started", "calculator", expression)
        result = await self.tools.execute("calculator", {"expression": expression})
        await self._emit(
            state,
            sink,
            "tool_completed",
            "calculator",
            result.output or result.error_code or "工具执行结束",
            {"ok": result.ok, "error_code": result.error_code},
        )
        if not result.ok:
            state.warnings.append(result.error_code or "tool_failure")
            return None
        return Evidence(
            document_id=f"tool:calculator:{expression}",
            title="计算器结果",
            content=f"{expression} = {result.output}",
            score=1.0,
            source="tool://calculator",
        )

    async def _synthesize(self, state: AgentState, sink: EventSink | None) -> None:
        if not state.budget.consume_step():
            state.warnings.append("step_budget_exhausted_before_synthesis")
            return
        await self._emit(state, sink, "node_started", "synthesizer", "正在组织答案")
        state.answer = await self.model.synthesize(state.question, state.evidence)
        state.citations = [
            Citation(
                marker=f"[{index}]",
                evidence_id=item.id,
                document_id=item.document_id,
                quote=item.content[:200],
            )
            for index, item in enumerate(state.evidence[:5], start=1)
        ]
        await self._emit(
            state,
            sink,
            "node_completed",
            "synthesizer",
            "答案已生成",
            {"citations": len(state.citations)},
        )

    async def _verify(self, state: AgentState, sink: EventSink | None) -> None:
        if not state.budget.consume_step():
            state.warnings.append("step_budget_exhausted_before_verification")
            return
        issues: list[str] = []
        if not state.evidence:
            issues.append("证据不足，已拒绝生成事实性结论")
        elif state.answer and "[1]" not in state.answer:
            issues.append("答案缺少可追踪引用")
        if issues and state.budget.consume_retry():
            state.answer = await self.model.revise(state.answer or "", issues, state.evidence)
        state.warnings.extend(issues)
        await self._emit(
            state,
            sink,
            "node_completed",
            "verifier",
            "验证完成",
            {"issues": issues},
        )

    async def _emit(
        self,
        state: AgentState,
        sink: EventSink | None,
        event_type: str,
        node: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        self._sequence += 1
        event = AgentEvent(
            sequence=self._sequence,
            trace_id=state.trace_id,
            event_type=event_type,
            node=node,
            message=message,
            data=data or {},
        )
        if sink is None:
            return
        result = sink(event)
        if inspect.isawaitable(result):
            await result
