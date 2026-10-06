"""Application service coordinating persistence, Agent runs and evaluations."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from statistics import mean
from uuid import uuid4

from apps.api.app.config import Settings
from apps.api.app.database import Repository
from apps.api.app.schemas import EvalRunResponse
from packages.agent_core.llm import DeterministicFakeModel
from packages.agent_core.models import AgentEvent, AgentState, Budget, TaskStatus
from packages.agent_core.workflow import ResearchAgent
from packages.evaluation.runner import EvalCase, EvaluationRunner
from packages.retrieval.chunking import chunk_text
from packages.retrieval.hybrid import Document, HybridRetriever
from packages.tools.registry import ToolRegistry


class TaskService:
    def __init__(
        self, repository: Repository, retriever: HybridRetriever, settings: Settings
    ) -> None:
        self.repository = repository
        self.retriever = retriever
        self.settings = settings
        self.model = DeterministicFakeModel()
        self.tools = ToolRegistry()
        self.eval_runs: dict[str, EvalRunResponse] = {}
        self._background_tasks: set[asyncio.Task[None]] = set()

    def _agent(self) -> ResearchAgent:
        return ResearchAgent(model=self.model, retriever=self.retriever, tools=self.tools)

    async def create_task(self, question: str, budget: Budget) -> tuple[str, AgentState]:
        task_id = str(uuid4())
        budget.max_steps = min(budget.max_steps, self.settings.max_agent_steps)
        budget.max_tool_calls = min(budget.max_tool_calls, self.settings.max_tool_calls)
        state = AgentState(question=question, budget=budget)
        await self.repository.save_task(task_id, state)
        task = asyncio.create_task(self._execute(task_id, state))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task_id, state

    async def _execute(self, task_id: str, state: AgentState) -> None:
        async def persist_event(event: AgentEvent) -> None:
            await self.repository.save_event(task_id, event)

        try:
            await asyncio.wait_for(
                self._agent().run(state, persist_event),
                timeout=self.settings.max_task_seconds,
            )
        except TimeoutError:
            state.status = TaskStatus.FAILED
            state.warnings.append("task_timeout")
        finally:
            await self.repository.save_task(task_id, state)

    async def get_task(self, task_id: str) -> AgentState | None:
        return await self.repository.get_task(task_id)

    async def stream_events(self, task_id: str) -> AsyncIterator[AgentEvent]:
        sequence = 0
        idle_cycles = 0
        while idle_cycles < 1200:
            events = await self.repository.get_events_after(task_id, sequence)
            if events:
                idle_cycles = 0
                for event in events:
                    sequence = event.sequence
                    yield event
            else:
                idle_cycles += 1
            state = await self.repository.get_task(task_id)
            if state is None:
                return
            if (
                state.status in {TaskStatus.COMPLETED, TaskStatus.PARTIAL, TaskStatus.FAILED}
                and not events
            ):
                return
            await asyncio.sleep(0.1)

    async def add_document(self, title: str, content: str, source: str) -> list[Document]:
        documents = [
            Document(
                title=f"{title} · {index + 1}",
                content=chunk,
                source=source,
                metadata={"chunk_index": index, "parent_title": title},
            )
            for index, chunk in enumerate(chunk_text(content))
        ]
        await self.repository.add_documents(documents)
        self.retriever.add(documents)
        return documents

    async def create_eval_run(self, name: str, cases: list[EvalCase]) -> EvalRunResponse:
        run_id = str(uuid4())
        run = EvalRunResponse(
            id=run_id,
            name=name,
            status="running",
            config={
                "model": self.model.name,
                "retrieval": "hybrid-rrf-v1",
                "prompt": "research-v1",
            },
        )
        self.eval_runs[run_id] = run
        task = asyncio.create_task(self._execute_eval(run_id, cases))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return run

    async def _execute_eval(self, run_id: str, cases: list[EvalCase]) -> None:
        async def execute(question: str) -> AgentState:
            return await self._agent().run(AgentState(question=question))

        results = await EvaluationRunner(execute).run(cases)
        metric_names = sorted({name for result in results for name in result.metrics})
        summary = {
            name: round(
                mean(result.metrics[name] for result in results if name in result.metrics), 6
            )
            for name in metric_names
        }
        run = self.eval_runs[run_id]
        run.results = results
        run.summary = summary
        run.status = "completed"

    def get_eval_run(self, run_id: str) -> EvalRunResponse | None:
        return self.eval_runs.get(run_id)
