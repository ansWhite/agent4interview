"""DeepSeek-powered web page fetch tool with SSRF protection.

Wraps POST /v1/tools/fetch, returning the page title and a Markdown body.
URLs pointing at loopback/private/link-local addresses are rejected before
any request leaves the machine.
"""

from __future__ import annotations

import ipaddress
from typing import Any
from urllib.parse import urlparse

import httpx

from packages.tools.base import ToolResult

FETCH_ENDPOINT = "https://api.deepseek.com/v1/tools/fetch"
MAX_URL_LENGTH = 8192


def is_unsafe_url(url: str) -> bool:
    """Reject non-HTTP schemes, userinfo, and loopback/private addresses.

    Note: this validates the hostname literal only. Full DNS-rebinding
    protection would require resolving the host before the request.
    """
    if not url or len(url) > MAX_URL_LENGTH:
        return True
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return True
    if parsed.username or parsed.password:
        return True
    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        return True
    if hostname == "localhost" or hostname.endswith(".localhost") or hostname.endswith(".local"):
        return True
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


class WebFetchTool:
    name = "web_fetch"
    description = "抓取指定网页并返回 Markdown 正文，自动拒绝内网与非法地址"

    def __init__(self, api_key: str, timeout_seconds: float = 30.0) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    async def invoke(self, arguments: dict[str, Any]) -> ToolResult:
        url = arguments.get("url")
        if not isinstance(url, str) or not url.strip():
            return ToolResult(
                ok=False,
                error_code="invalid_arguments",
                output="url 必须是非空字符串",
            )
        url = url.strip()
        if is_unsafe_url(url):
            return ToolResult(ok=False, error_code="unsafe_url", output=url)
        if not self.api_key:
            return ToolResult(
                ok=False,
                error_code="missing_api_key",
                output="未配置 DEEPSEEK_API_KEY，无法抓取网页",
            )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    FETCH_ENDPOINT, headers=headers, json={"url": url}
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            return ToolResult(ok=False, error_code="web_fetch_timeout", output=url)
        except httpx.HTTPError as exc:
            return ToolResult(
                ok=False,
                error_code="web_fetch_failure",
                output=f"{type(exc).__name__}: {exc}",
            )

        return ToolResult(
            ok=True,
            output=data.get("content") or "",
            metadata={"url": url, "title": data.get("title") or ""},
        )
