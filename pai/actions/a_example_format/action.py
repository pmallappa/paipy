"""PAI Action: Example Format — formats a summary into structured markdown."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional


class _Action:
    """Example format action."""

    async def execute(self, input_data: Dict[str, Any], _ctx: Any) -> Dict[str, Any]:
        summary: Optional[str] = input_data.get("summary")
        title: Optional[str] = input_data.get("title")
        word_count: Optional[int] = input_data.get("word_count")

        if not summary:
            raise ValueError("Missing required input: summary")

        # Collect upstream keys (everything except our known keys)
        upstream = {k: v for k, v in input_data.items() if k not in ("summary", "title", "word_count")}

        # Split summary into sentences for bullet formatting
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", summary) if s.strip()]

        # Build structured markdown
        lines: list[str] = []

        if title:
            lines.extend([f"# {title}", ""])

        lines.extend(["## Summary", ""])

        for sentence in sentences:
            lines.append(f"- {sentence}")

        if word_count:
            lines.extend(["", "---", f"*{word_count} words*"])

        formatted = "\n".join(lines)

        return {
            **upstream,
            "formatted": formatted,
            "format": "markdown",
        }


default = _Action()
