from pathlib import Path

import pytest

from apps.api.app.database import Repository
from packages.agent_core.models import AgentEvent, AgentState
from packages.retrieval.hybrid import Document


@pytest.mark.asyncio
async def test_repository_persists_task_event_and_document(tmp_path: Path) -> None:
    database = tmp_path / "test.db"
    repository = Repository(f"sqlite+aiosqlite:///{database.as_posix()}")
    await repository.initialize()
    try:
        state = AgentState(question="如何评测 Agent？")
        await repository.save_task("task-1", state)
        await repository.save_event(
            "task-1",
            AgentEvent(
                sequence=1,
                trace_id=state.trace_id,
                event_type="task_started",
                node="intake",
                message="开始",
            ),
        )
        await repository.add_documents(
            [Document(id="doc-1", title="评测", content="使用可复现指标")]
        )

        loaded = await repository.get_task("task-1")
        events = await repository.get_events_after("task-1", 0)
        documents = await repository.list_documents()

        assert loaded is not None and loaded.trace_id == state.trace_id
        assert [event.sequence for event in events] == [1]
        assert documents[0].id == "doc-1"
    finally:
        await repository.close()
