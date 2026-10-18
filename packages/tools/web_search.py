"""DeepSeek-powered web search tool.

Wraps POST /v1/tools/search. Each result carries a rerank_score in [0, 3];
we normalize it to [0, 1] so web evidence is comparable with local retrieval
scores. Structured results travel through ToolResult.metadata so callers can
convert them into Evidence without parsing free-form output.
"""

from __future__ import annotations

import hashlib
from typing import Any

import httpx

from packages.tools.base import ToolResult

SEARCH_ENDPOINT = "https://api.deepseek.com/v1/tools/search"


def web_document_id(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return f"web:{digest}"


class WebSearchTool:
    name = "web_search"
    description = "调用 DeepSeek 网页搜索，返回带相关性分数的网页结果列表"

    def __init__(self, api_key: str, timeout_seconds: float = 20.0) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    async def invoke(self, arguments: dict[str, Any]) -> ToolResult:
        query = arguments.get("query")
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 128:
            return ToolResult(
                ok=False,
                error_code="invalid_arguments",
                output="query 必须是 1~128 个字符的字符串",
            )
        if not self.api_key:
            return ToolResult(
                ok=False,
                error_code="missing_api_key",
                output="未配置 DEEPSEEK_API_KEY，无法联网检索",
            )
        count = arguments.get("count", 5)
        if not isinstance(count, int) or not 1 <= count <= 50:
            count = 5
        payload: dict[str, Any] = {
            "query": query.strip(),
            "count": count,
            "need_content": False,
        }
        ori_question = arguments.get("ori_question")
        if isinstance(ori_question, str) and ori_question.strip():
            payload["ori_question"] = ori_question.strip()[:128]
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(SEARCH_ENDPOINT, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            return ToolResult(ok=False, error_code="web_search_timeout", output=query)
        except httpx.HTTPError as exc:
            return ToolResult(
                ok=False,
                error_code="web_search_failure",
                output=f"{type(exc).__name__}: {exc}",
            )

        results = [self._convert(item) for item in data.get("results", [])]
        return ToolResult(
            ok=True,
            output=f"搜索到 {len(results)} 条网页结果",
            metadata={"results": results},
        )

    @staticmethod
    def _convert(item: dict[str, Any]) -> dict[str, Any]:
        url = item.get("url") or ""
        rerank_score = item.get("rerank_score") or 0.0
        return {
            "document_id": web_document_id(url),
            "title": item.get("title") or "",
            "url": url,
            "summary": item.get("summary") or item.get("snippet") or "",
            "score": round(min(1.0, max(0.0, float(rerank_score) / 3.0)), 6),
            "site_name": item.get("site_name"),
            "date": item.get("date"),
            "authority": item.get("authority"),
        }
