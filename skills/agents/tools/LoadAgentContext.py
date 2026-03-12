#!/usr/bin/env python3

"""
Load Agent Context

Simple utility to load agent context files when spawning specialized agents.
Each agent type (Architect, Engineer, Designer, etc.) has ONE markdown context file
that references relevant parts of the Skills system.

Usage: python LoadAgentContext.py <agentType>
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal, Optional


ModelType = Literal["opus", "sonnet", "haiku"]


class AgentContext:
    """Container for loaded agent context."""

    def __init__(
        self, agent_type: str, context_content: str, model: ModelType = "opus"
    ) -> None:
        self.agent_type = agent_type
        self.context_content = context_content
        self.model = model


class AgentContextLoader:
    """Loads agent context files for spawning specialized agents."""

    def __init__(self) -> None:
        self.claude_home = Path.home() / ".claude"
        self.agents_dir = self.claude_home / "Skills" / "Agents"

    def load_context(self, agent_type: str) -> AgentContext:
        """Load context for a specific agent type."""
        context_path = self.agents_dir / f"{agent_type}Context.md"

        if not context_path.exists():
            raise FileNotFoundError(
                f"Context file not found for agent type: {agent_type}\n"
                f"Expected at: {context_path}"
            )

        context_content = context_path.read_text(encoding="utf-8")

        # Extract model preference from context file (defaults to opus)
        import re

        model_match = re.search(
            r"\*\*Model\*\*:\s*(opus|sonnet|haiku)", context_content, re.IGNORECASE
        )
        model: ModelType = "opus"
        if model_match:
            model = model_match.group(1).lower()  # type: ignore[assignment]

        return AgentContext(
            agent_type=agent_type,
            context_content=context_content,
            model=model,
        )

    def get_available_agents(self) -> list[str]:
        """Get list of available agent types."""
        if not self.agents_dir.exists():
            return []

        return [
            f.stem.replace("Context", "")
            for f in self.agents_dir.iterdir()
            if f.name.endswith("Context.md")
        ]

    def generate_enriched_prompt(
        self, agent_type: str, task_description: str
    ) -> dict[str, str]:
        """Generate enriched prompt for spawning agent with Task tool."""
        context = self.load_context(agent_type)

        enriched_prompt = f"""{context.context_content}

---

## Current Task

{task_description}"""

        return {
            "prompt": enriched_prompt,
            "model": context.model,
        }


# ---------------------------------------------------------------------------
# CLI usage
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]

    if not args:
        print("Usage: LoadAgentContext.py <agentType> [taskDescription]")
        print("\nAvailable agent types:")
        loader = AgentContextLoader()
        for agent in loader.get_available_agents():
            print(f"  - {agent}")
        sys.exit(1)

    agent_type = args[0]
    task_description = " ".join(args[1:]) if len(args) > 1 else ""

    try:
        loader = AgentContextLoader()

        if task_description:
            result = loader.generate_enriched_prompt(agent_type, task_description)
            print(f"\n=== Enriched Prompt for {agent_type} Agent (Model: {result['model']}) ===\n")
            print(result["prompt"])
        else:
            context = loader.load_context(agent_type)
            print(f"\n=== Context for {context.agent_type} Agent (Model: {context.model}) ===\n")
            print(context.context_content)

    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
