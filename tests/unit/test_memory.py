from datetime import UTC, datetime, timedelta

from packages.agent_core.memory import MemoryItem, MemoryStore


def test_memory_filters_expired_and_irrelevant_items() -> None:
    now = datetime.now(UTC)
    store = MemoryStore()
    relevant = MemoryItem(content="用户偏好 Python Agent 项目", confidence=0.9)
    store.remember(relevant)
    store.remember(MemoryItem(content="无关的烹饪信息", confidence=1.0))
    store.remember(
        MemoryItem(
            content="过期的 Python 偏好",
            confidence=1.0,
            expires_at=now - timedelta(seconds=1),
        )
    )

    recalled = store.recall("Python Agent", now=now)

    assert [item.id for item in recalled] == [relevant.id]
