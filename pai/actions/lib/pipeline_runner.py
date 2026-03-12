#!/usr/bin/env python3
"""
PAI Pipeline Runner -- v2 (simplified)

A pipeline is a list of actions. That's it.
Each action's output pipes into the next action's input.
The pipeline output is the last action's output.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

ACTIONS_DIR = Path(__file__).parent.parent
PIPELINES_DIR = ACTIONS_DIR.parent / "PIPELINES"
USER_PIPELINES_DIR = ACTIONS_DIR.parent / "USER" / "PIPELINES"


class Pipeline:
    """Pipeline definition."""

    def __init__(self, name: str, description: str, actions: List[str]) -> None:
        self.name = name
        self.description = description
        self.actions = actions


def _load_pipeline(name: str) -> Pipeline:
    """
    Load a pipeline YAML.
    Resolution order: USER/PIPELINES (personal) -> PIPELINES (system/framework)
    """
    # Check USER/PIPELINES first
    user_path = USER_PIPELINES_DIR / f"{name}.yaml"
    if user_path.exists():
        content = user_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        return Pipeline(
            name=data.get("name", name),
            description=data.get("description", ""),
            actions=data.get("actions", []),
        )

    # Fall back to PIPELINES (system)
    system_path = PIPELINES_DIR / f"{name}.yaml"
    content = system_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    return Pipeline(
        name=data.get("name", name),
        description=data.get("description", ""),
        actions=data.get("actions", []),
    )


async def run_pipeline(
    name: str,
    input_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Run a pipeline: pipe data through each action sequentially."""
    try:
        pipeline = _load_pipeline(name)
        data: Any = input_data

        for action_name in pipeline.actions:
            print(f"[pipeline] {action_name}", file=sys.stderr)

            from runner_v2 import run_action

            result = await run_action(action_name, data)

            if not result.success:
                return {"success": False, "error": f"{action_name} failed: {result.error}"}

            data = result.output  # pipe: output becomes next input

        return {"success": True, "output": data}
    except Exception as err:
        return {"success": False, "error": str(err)}


async def list_pipelines() -> List[str]:
    """List all pipelines from both USER (personal) and SYSTEM (framework) directories."""
    seen: set[str] = set()
    result: List[str] = []

    # USER first (personal takes precedence)
    for pipeline_dir in [USER_PIPELINES_DIR, PIPELINES_DIR]:
        if not pipeline_dir.exists():
            continue
        try:
            for f in pipeline_dir.iterdir():
                if f.suffix == ".yaml":
                    name = f.stem
                    if name not in seen:
                        result.append(name)
                        seen.add(name)
        except Exception:
            pass

    return result


# ── CLI ──────────────────────────────────────────────────────────


async def main() -> None:
    """CLI entry point."""
    args = sys.argv[1:]

    if not args:
        print("Usage:")
        print("  pipeline_runner.py list")
        print("  pipeline_runner.py run <pipeline> [--key value ...]")
        return

    if args[0] == "list":
        pipelines = await list_pipelines()
        print(json.dumps({"pipelines": pipelines}, indent=2))

    elif args[0] == "run" and len(args) > 1:
        name = args[1]
        input_data: Dict[str, Any] = {}

        i = 2
        while i < len(args) - 1:
            key = args[i].lstrip("-")
            value: Any = args[i + 1]
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass
            input_data[key] = value
            i += 2

        result = await run_pipeline(name, input_data)
        print(json.dumps(result, indent=2))

    else:
        print("Usage:")
        print("  pipeline_runner.py list")
        print("  pipeline_runner.py run <pipeline> [--key value ...]")


if __name__ == "__main__":
    asyncio.run(main())
