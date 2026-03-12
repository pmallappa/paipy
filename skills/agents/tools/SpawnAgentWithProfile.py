#!/usr/bin/env python3

"""
Spawn Agent With Profile

Helper utility to spawn agents with pre-loaded profile context.
Generates enriched prompts for the Task tool.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal, Optional

# NOTE: AgentProfileLoader is expected in the same directory
# Adjust the import path if it lives elsewhere in your project.
try:
    from AgentProfileLoader import AgentProfileLoader
except ImportError:
    # Fallback: try relative import
    try:
        from .AgentProfileLoader import AgentProfileLoader  # type: ignore[no-redef]
    except ImportError:
        AgentProfileLoader = None  # type: ignore[assignment,misc]


ModelType = Literal["opus", "sonnet", "haiku"]


@dataclass
class SpawnAgentOptions:
    agent_type: str
    task_description: str
    project_path: Optional[str] = None
    model: Optional[ModelType] = None
    run_in_background: bool = False
    description: Optional[str] = None


@dataclass
class AgentPrompt:
    prompt: str
    model: ModelType
    description: str


async def generate_agent_prompt(options: SpawnAgentOptions) -> AgentPrompt:
    """Generate enriched prompt for spawning an agent with profile."""
    if AgentProfileLoader is None:
        raise ImportError(
            "AgentProfileLoader not found. Ensure AgentProfileLoader.py exists "
            "in the same directory."
        )

    loader = AgentProfileLoader()

    # Load the profile
    loaded = await loader.load_profile(
        options.agent_type,
        options.task_description,
        options.project_path,
    )

    # Use profile's model preference if not overridden
    model: ModelType = options.model or getattr(
        loaded.profile, "model_preference", None
    ) or "sonnet"

    # Generate description if not provided
    description = (
        options.description
        or f"{options.agent_type}: {options.task_description[:50]}..."
    )

    return AgentPrompt(
        prompt=loaded.full_prompt,
        model=model,
        description=description,
    )


# ---------------------------------------------------------------------------
# CLI usage
# ---------------------------------------------------------------------------

async def _async_main() -> None:
    args = sys.argv[1:]

    if len(args) < 2:
        print("Usage: SpawnAgentWithProfile.py <agentType> <taskDescription> [projectPath]")
        print("\nExample:")
        print('  python SpawnAgentWithProfile.py Architect "Design REST API" ~/Projects/MyApp')
        print("\nAvailable profiles:")
        if AgentProfileLoader is not None:
            loader = AgentProfileLoader()
            for profile in loader.get_available_profiles():
                print(f"  - {profile}")
        else:
            print("  (AgentProfileLoader not available)")
        sys.exit(1)

    agent_type = args[0]
    task_description = args[1]
    project_path = args[2] if len(args) > 2 else None

    try:
        prompt = await generate_agent_prompt(
            SpawnAgentOptions(
                agent_type=agent_type,
                task_description=task_description,
                project_path=project_path,
            )
        )

        print("\n=== Agent Spawn Configuration ===\n")
        print(f"Agent Type: {agent_type}")
        print(f"Model: {prompt.model}")
        print(f"Description: {prompt.description}")
        print("\n=== Enriched Prompt (ready for Task tool) ===\n")
        print(prompt.prompt)

    except Exception as error:
        print(f"Error generating prompt: {error}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    import asyncio
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
