from packages.retrieval.chunking import chunk_text
from packages.retrieval.hybrid import Document, HybridRetriever


def test_hybrid_retrieval_ranks_relevant_document_first() -> None:
    retriever = HybridRetriever()
    retriever.add(
        [
            Document(id="rag", title="混合检索", content="BM25 向量检索 RRF 融合排序"),
            Document(id="ops", title="部署", content="容器健康检查和日志采集"),
        ]
    )

    hits = retriever.search("BM25 和 RRF 如何组合", limit=2)

    assert hits[0].document.id == "rag"
    assert hits[0].score > hits[1].score
    assert hits[0].lexical_score > 0


def test_irrelevant_documents_have_zero_score() -> None:
    retriever = HybridRetriever()
    retriever.add([Document(id="x", title="烹饪", content="番茄和鸡蛋")])

    assert retriever.search("Kubernetes", limit=1)[0].score == 0


def test_chunking_preserves_overlap() -> None:
    chunks = chunk_text("A" * 80, chunk_size=40, overlap=10)

    assert len(chunks) == 3
    assert chunks[0][-10:] == chunks[1][:10]
