"""Unit tests for DeepSeek-backed web tools (HTTP layer mocked)."""

from typing import Any

import httpx
import pytest

from packages.tools.web_fetch import WebFetchTool, is_unsafe_url
from packages.tools.web_search import WebSearchTool, web_document_id


def _transport(
    url: str,
    response_json: dict[str, Any],
    status_code: int = 200,
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == url
        assert request.headers["Authorization"].startswith("Bearer ")
        return httpx.Response(status_code, json=response_json)

    return httpx.MockTransport(handler)


def _patch_client(monkeypatch: pytest.MonkeyPatch, transport: httpx.MockTransport) -> None:
    original_init = httpx.AsyncClient.__init__

    def patched_init(self: httpx.AsyncClient, *args: Any, **kwargs: Any) -> None:
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


SEARCH_RESPONSE = {
    "results": [
        {
            "rerank_score": 2.4,
            "title": "DeepSeek V4 model released",
            "url": "https://example.com/deepseek-v4",
            "snippet": "DeepSeek V4 is now available.",
            "summary": "DeepSeek has released the V4 model with tool calling support.",
            "site_name": "Example News",
            "date": "2026-06-01T00:00:00+00:00",
            "authority": 3,
        },
        {
            "rerank_score": 0.6,
            "title": "Unrelated page",
            "url": "https://other.example.org/page",
            "summary": "Not very relevant.",
            "site_name": None,
            "date": None,
            "authority": -1,
        },
    ]
}


@pytest.mark.asyncio
async def test_web_search_converts_results(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(
        monkeypatch,
        _transport("https://api.deepseek.com/v1/tools/search", SEARCH_RESPONSE),
    )
    tool = WebSearchTool(api_key="sk-test")

    result = await tool.invoke({"query": "DeepSeek V4", "count": 5})

    assert result.ok
    results = result.metadata["results"]
    assert len(results) == 2
    top = results[0]
    assert top["title"] == "DeepSeek V4 model released"
    assert top["score"] == pytest.approx(2.4 / 3.0)
    assert top["document_id"] == web_document_id("https://example.com/deepseek-v4")
    assert top["summary"].startswith("DeepSeek has released")


@pytest.mark.asyncio
async def test_web_search_rejects_invalid_query() -> None:
    tool = WebSearchTool(api_key="sk-test")

    empty = await tool.invoke({"query": "   "})
    missing = await tool.invoke({})

    assert not empty.ok and empty.error_code == "invalid_arguments"
    assert not missing.ok and missing.error_code == "invalid_arguments"


@pytest.mark.asyncio
async def test_web_search_requires_api_key() -> None:
    tool = WebSearchTool(api_key="")

    result = await tool.invoke({"query": "anything"})

    assert not result.ok and result.error_code == "missing_api_key"


@pytest.mark.asyncio
async def test_web_search_reports_http_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(
        monkeypatch,
        _transport("https://api.deepseek.com/v1/tools/search", {"detail": "boom"}, 500),
    )
    tool = WebSearchTool(api_key="sk-test")

    result = await tool.invoke({"query": "boom"})

    assert not result.ok and result.error_code == "web_search_failure"


FETCH_RESPONSE = {
    "title": "Example article",
    "content": "# Example article\n\nArticle content.",
}


@pytest.mark.asyncio
async def test_web_fetch_returns_markdown_body(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(
        monkeypatch,
        _transport("https://api.deepseek.com/v1/tools/fetch", FETCH_RESPONSE),
    )
    tool = WebFetchTool(api_key="sk-test")

    result = await tool.invoke({"url": "https://example.com/article"})

    assert result.ok
    assert result.output.startswith("# Example article")
    assert result.metadata["title"] == "Example article"
    assert result.metadata["url"] == "https://example.com/article"


@pytest.mark.asyncio
async def test_web_fetch_blocks_unsafe_urls() -> None:
    tool = WebFetchTool(api_key="sk-test")

    loopback = await tool.invoke({"url": "http://127.0.0.1:8000/admin"})
    private = await tool.invoke({"url": "http://192.168.1.1/router"})
    scheme = await tool.invoke({"url": "file:///etc/passwd"})
    userinfo = await tool.invoke({"url": "http://user:pass@example.com/"})

    assert not loopback.ok and loopback.error_code == "unsafe_url"
    assert not private.ok and private.error_code == "unsafe_url"
    assert not scheme.ok and scheme.error_code == "unsafe_url"
    assert not userinfo.ok and userinfo.error_code == "unsafe_url"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/x",
        "http://10.0.0.1/x",
        "http://172.16.0.1/x",
        "http://192.168.0.1/x",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/x",
        "http://localhost:8000/x",
        "ftp://example.com/x",
        "http://user:pass@example.com/x",
        "",
    ],
)
def test_is_unsafe_url_rejects_dangerous_targets(url: str) -> None:
    assert is_unsafe_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/article",
        "http://8.8.8.8/docs",
        "https://api.deepseek.com/v1/tools/fetch",
    ],
)
def test_is_unsafe_url_allows_public_targets(url: str) -> None:
    assert not is_unsafe_url(url)
