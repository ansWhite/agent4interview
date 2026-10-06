"""FastAPI entrypoint and local-only HTTP/SSE interface."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from apps.api.app.config import get_settings
from apps.api.app.database import Repository
from apps.api.app.schemas import (
    CreateDocumentRequest,
    CreateDocumentResponse,
    CreateEvalRunRequest,
    CreateTaskRequest,
    EvalRunResponse,
    TaskResponse,
)
from apps.api.app.seed import SEED_DOCUMENTS
from apps.api.app.service import TaskService
from packages.retrieval.hybrid import HybridRetriever

settings = get_settings()
repository = Repository(settings.database_url)
retriever = HybridRetriever()
service = TaskService(repository, retriever, settings)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await repository.initialize()
    documents = await repository.list_documents()
    if not documents:
        await repository.add_documents(SEED_DOCUMENTS)
        documents = SEED_DOCUMENTS
    retriever.add(documents)
    yield
    await repository.close()


app = FastAPI(
    title="InsightAgent API",
    version="0.1.0",
    description="可控、可观测、可评测的 Deep Research Agent",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Last-Event-ID"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "code": "internal_error",
                "message": f"{type(exc).__name__}: {exc}",
                "trace_id": request.headers.get("x-trace-id"),
            }
        },
    )


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model": service.model.name,
        "documents": retriever.size,
    }


@app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_task(request: CreateTaskRequest) -> TaskResponse:
    task_id, state = await service.create_task(request.question, request.budget)
    return TaskResponse(id=task_id, state=state)


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str) -> TaskResponse:
    state = await service.get_task(task_id)
    if state is None:
        raise HTTPException(status_code=404, detail={"code": "task_not_found", "message": task_id})
    return TaskResponse(id=task_id, state=state)


@app.get("/tasks/{task_id}/events")
async def get_task_events(task_id: str) -> StreamingResponse:
    if await service.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail={"code": "task_not_found", "message": task_id})

    async def stream() -> AsyncIterator[str]:
        async for event in service.stream_events(task_id):
            event_data = event.model_dump_json()
            yield f"id: {event.sequence}\nevent: {event.event_type}\ndata: {event_data}\n\n"
        yield "event: stream_closed\ndata: {}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/documents", response_model=CreateDocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(request: CreateDocumentRequest) -> CreateDocumentResponse:
    documents = await service.add_document(request.title, request.content, request.source)
    return CreateDocumentResponse(
        document_ids=[document.id for document in documents],
        chunks=len(documents),
    )


@app.post("/evaluations/runs", response_model=EvalRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_evaluation(request: CreateEvalRunRequest) -> EvalRunResponse:
    return await service.create_eval_run(request.name, request.cases)


@app.get("/evaluations/runs/{run_id}", response_model=EvalRunResponse)
async def get_evaluation(run_id: str) -> EvalRunResponse:
    run = service.get_eval_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=404, detail={"code": "eval_run_not_found", "message": run_id}
        )
    return run
