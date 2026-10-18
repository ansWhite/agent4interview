"""DeepSeek API provider for Agent."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from packages.agent_core.models import Evidence, ResearchStep


class DeepSeekModel:
    """DeepSeek API provider using the chat completion interface."""

    name = "deepseek-chat"
    base_url = "https://api.deepseek.com/chat/completions"

    def __init__(self, api_key: str | None = None, model: str = "deepseek-chat") -> None:
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.model = model

    async def plan(self, question: str, max_steps: int) -> list[ResearchStep]:
        """Decompose question into research steps."""
        prompt = f"""你是一个研究问题拆解助手。请将以下问题拆解成 {max_steps} 个子任务。

要求：
1. 每个子任务有明确的检索查询词
2. 子任务之间尽量独立
3. 覆盖问题的不同方面（定义、原理、优缺点、应用等）

问题：{question}

请以 JSON 格式返回，格式如下：
{{"steps": ["子任务1查询词", "子任务2查询词", ...]}}
"""

        response = await self._call(prompt)
        steps_data = self._parse_json(response)

        steps = []
        for i, query in enumerate(steps_data.get("steps", [question])[:max_steps]):
            steps.append(ResearchStep(
                title=f"子任务 {i + 1}",
                query=query
            ))

        if not steps:
            steps = [
                ResearchStep(title="子任务 1", query=f"定义与背景：{question}"),
                ResearchStep(title="子任务 2", query=f"核心机制：{question}"),
            ]

        return steps

    async def synthesize(self, question: str, evidence: list[Evidence]) -> str:
        """Generate answer based on evidence."""
        evidence_text = "\n".join([
            f"[{i+1}] {item.title}\n{item.content}"
            for i, item in enumerate(evidence[:5])
        ])

        prompt = f"""你是一个研究助手，基于提供的证据回答问题。

要求：
1. 只基于证据回答，不要编造信息
2. 使用 [1][2] 等标记引用证据
3. 回答要清晰、有条理

问题：{question}

证据：
{evidence_text}

请生成回答：
"""

        return await self._call(prompt)

    async def revise(self, answer: str, issues: list[str], evidence: list[Evidence]) -> str:
        """Revise answer based on issues."""
        evidence_text = "\n".join([
            f"[{i+1}] {item.content}"
            for i, item in enumerate(evidence[:5])
        ])

        prompt = f"""你是一个答案修订助手。请根据以下问题修订答案。

原答案：
{answer}

问题：
{chr(10).join(f"- {issue}" for issue in issues)}

证据：
{evidence_text}

请修订答案，确保：
1. 解决上述问题
2. 只基于证据回答
3. 保持引用标记

修订后的答案：
"""

        return await self._call(prompt)

    async def _call(self, prompt: str, system: str = "") -> str:
        """Make API call to DeepSeek."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.base_url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return str(data["choices"][0]["message"]["content"])

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        """Extract JSON from response."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        try:
            return dict(json.loads(text.strip()))
        except json.JSONDecodeError:
            # Try to find JSON in text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                return dict(json.loads(text[start:end]))
            return {}
