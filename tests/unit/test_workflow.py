import pytest

from packages.agent_core.llm import DeterministicFakeModel
from packages.agent_core.models import AgentState, Budget, TaskStatus
from packages.agent_core.workflow import ResearchAgent
from packages.retrieval.hybrid import Document, HybridRetriever


@pytest.mark.asyncio
async def test_workflow_returns_cited_answer_and_trace() -> None:
    retriever = HybridRetriever()
    retriever.add(
        [Document(id="agent", title="Agent 预算", content="Agent 使用最大步骤预算避免无限循环")]
    )
    events = []
    agent = ResearchAgent(DeterministicFakeModel(), retriever)

    state = await agent.run(AgentState(question="Agent 为什么需要步骤预算？"), events.append)

    assert state.status == TaskStatus.COMPLETED
    assert state.answer is not None and "[1]" in state.answer
    assert state.citations[0].document_id == "agent"
    assert events[-1].event_type == "task_finished"


@pytest.mark.asyncio
async def test_workflow_refuses_when_evidence_is_missing() -> None:
    agent = ResearchAgent(DeterministicFakeModel(), HybridRetriever())

    state = await agent.run(AgentState(question="完全未知的问题", budget=Budget(max_steps=5)))

    assert state.status == TaskStatus.PARTIAL
    assert state.answer == "现有知识库没有足够证据回答该问题。"
    assert state.budget.steps_used <= state.budget.max_steps
