import asyncio
from pathlib import Path

import pytest

from apps.api.app.config import Settings
from apps.api.app.database import Repository
from apps.api.app.service import TaskService
from packages.agent_core.models import Budget, TaskStatus
from packages.evaluation.runner import EvalCase
from packages.retrieval.hybrid import HybridRetriever


@pytest.mark.asyncio
async def test_document_to_answer_to_evaluation_journey(tmp_path: Path) -> None:
    database = tmp_path / "journey.db"
    repository = Repository(f"sqlite+aiosqlite:///{database.as_posix()}")
    await repository.initialize()
    service = TaskService(
        repository,
        HybridRetriever(),
        Settings(database_url=f"sqlite+aiosqlite:///{database.as_posix()}"),
    )
    try:
        documents = await service.add_document(
            "RRF",
            "RRF 使用不同结果中的排名倒数来融合 BM25 与向量检索。",
            "local://test",
        )
        task_id, _ = await service.create_task("RRF 如何融合 BM25 与向量检索？", Budget())

        state = None
        for _ in range(100):
            state = await service.get_task(task_id)
            if state and state.status in {
                TaskStatus.COMPLETED,
                TaskStatus.PARTIAL,
                TaskStatus.FAILED,
            }:
                break
            await asyncio.sleep(0.01)

        assert state is not None and state.status == TaskStatus.COMPLETED
        assert state.citations and state.citations[0].document_id == documents[0].id

        run = await service.create_eval_run(
            "journey",
            [
                EvalCase(
                    question="RRF 如何融合检索？",
                    relevant_document_ids={documents[0].id},
                    required_document_ids={documents[0].id},
                )
            ],
        )
        current = None
        for _ in range(100):
            current = service.get_eval_run(run.id)
            if current and current.status == "completed":
                break
            await asyncio.sleep(0.01)

        assert current is not None and current.status == "completed"
        assert current.summary["task_success"] == 1.0
    finally:
        await repository.close()
