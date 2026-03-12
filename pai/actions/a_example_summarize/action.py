"""PAI Action: Example Summarize — uses LLM to summarize content."""

from __future__ import annotations

from typing import Any, Dict, Optional


class _Action:
    """Example summarize action."""

    async def execute(self, input_data: Dict[str, Any], ctx: Any) -> Dict[str, Any]:
        content: Optional[str] = input_data.get("content")

        if not content:
            raise ValueError("Missing required input: content")

        # Collect upstream keys (everything except our known keys)
        upstream = {k: v for k, v in input_data.items() if k != "content"}

        llm = ctx.capabilities.llm
        if not llm:
            raise RuntimeError("LLM capability required")

        from lib.types_v2 import LLMOptions

        result = await llm(
            content,
            LLMOptions(
                system=(
                    "You are a concise summarizer. Summarize the following text in 2-3 sentences. "
                    "Return ONLY the summary, no preamble or labels."
                ),
                tier="fast",
            ),
        )

        summary = result.text.strip()

        return {
            **upstream,
            "summary": summary,
            "word_count": len(summary.split()),
        }


default = _Action()
