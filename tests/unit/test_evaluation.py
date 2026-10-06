from packages.evaluation.metrics import citation_metrics, retrieval_metrics


def test_retrieval_metrics() -> None:
    metrics = retrieval_metrics(["noise", "expected", "other"], {"expected"}, k=3)

    assert metrics == {"recall_at_k": 1.0, "mrr": 0.5, "ndcg": 0.63093}


def test_citation_metrics() -> None:
    metrics = citation_metrics(["a", "noise"], {"a", "b"}, {"a", "b"})

    assert metrics["citation_precision"] == 0.5
    assert metrics["citation_completeness"] == 0.5
