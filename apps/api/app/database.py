"""Async SQLAlchemy persistence for tasks, events and local documents."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from packages.agent_core.models import AgentEvent, AgentState
from packages.retrieval.hybrid import Document


class Base(DeclarativeBase):
    pass


class TaskRecord(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), index=True)
    state_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventRecord(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DocumentRecord(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(200))
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")


class Repository:
    def __init__(self, database_url: str) -> None:
        self.engine = create_async_engine(database_url)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def initialize(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    async def save_task(self, task_id: str, state: AgentState) -> None:
        now = datetime.now(UTC)
        async with self.session_factory() as session:
            record = await session.get(TaskRecord, task_id)
            payload = state.model_dump_json()
            if record is None:
                session.add(
                    TaskRecord(
                        id=task_id,
                        trace_id=state.trace_id,
                        question=state.question,
                        status=str(state.status),
                        state_json=payload,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                record.status = str(state.status)
                record.state_json = payload
                record.updated_at = now
            await session.commit()

    async def get_task(self, task_id: str) -> AgentState | None:
        async with self.session_factory() as session:
            record = await session.get(TaskRecord, task_id)
            return AgentState.model_validate_json(record.state_json) if record else None

    async def save_event(self, task_id: str, event: AgentEvent) -> None:
        async with self.session_factory() as session:
            session.add(
                EventRecord(
                    task_id=task_id,
                    sequence=event.sequence,
                    payload_json=event.model_dump_json(),
                    created_at=event.created_at,
                )
            )
            await session.commit()

    async def get_events_after(self, task_id: str, sequence: int) -> list[AgentEvent]:
        async with self.session_factory() as session:
            statement = (
                select(EventRecord)
                .where(EventRecord.task_id == task_id, EventRecord.sequence > sequence)
                .order_by(EventRecord.sequence)
            )
            records = (await session.scalars(statement)).all()
            return [AgentEvent.model_validate_json(record.payload_json) for record in records]

    async def add_documents(self, documents: list[Document]) -> None:
        async with self.session_factory() as session:
            for document in documents:
                session.add(
                    DocumentRecord(
                        id=document.id,
                        title=document.title,
                        content=document.content,
                        source=document.source,
                        metadata_json=json.dumps(document.metadata, ensure_ascii=False),
                    )
                )
            await session.commit()

    async def list_documents(self) -> list[Document]:
        async with self.session_factory() as session:
            records = (await session.scalars(select(DocumentRecord))).all()
            return [
                Document(
                    id=record.id,
                    title=record.title,
                    content=record.content,
                    source=record.source,
                    metadata=json.loads(record.metadata_json),
                )
                for record in records
            ]
