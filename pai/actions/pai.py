#!/usr/bin/env python3
"""
============================================================================
PAI CLI - Unified Actions & Pipelines Interface
============================================================================

The main entry point for running PAI actions and pipelines.

USAGE:
  # Run an action
  pai action parse/topic --input '{"text":"quantum computing"}'
  echo '{"text":"quantum"}' | pai action parse/topic

  # Run a pipeline
  pai pipeline research --topic "quantum computing"

  # Piping actions together
  pai action parse/topic | pai action transform/summarize

  # List available actions/pipelines
  pai actions
  pai pipelines

  # Show action/pipeline info
  pai info parse/topic

OPTIONS:
  --mode local|cloud    Execution mode (default: local)
  --input '<json>'      Input as JSON string
  --verbose             Show execution details

============================================================================
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib.runner import load_action, list_actions, run_action

PIPELINES_DIR = Path(__file__).parent.parent / "PIPELINES"


class CLIOptions:
    """CLI option container."""

    def __init__(self) -> None:
        self.mode: str = "local"
        self.verbose: bool = False
        self.input: Optional[str] = None


def parse_args(args: List[str]) -> Dict[str, Any]:
    """Parse CLI arguments."""
    options = CLIOptions()
    extra: Dict[str, str] = {}
    command = ""
    target: Optional[str] = None
    expecting_value: Optional[str] = None

    for arg in args:
        if expecting_value:
            if expecting_value == "mode":
                options.mode = arg
            elif expecting_value == "input":
                options.input = arg
            else:
                extra[expecting_value] = arg
            expecting_value = None
            continue

        if arg == "--mode":
            expecting_value = "mode"
            continue
        if arg == "--input":
            expecting_value = "input"
            continue
        if arg in ("--verbose", "-v"):
            options.verbose = True
            continue
        if arg.startswith("--"):
            expecting_value = arg[2:]
            continue

        if not command:
            command = arg
            continue
        if target is None:
            target = arg
            continue

    return {"command": command, "target": target, "options": options, "extra": extra}


def read_stdin() -> Optional[str]:
    """Read from stdin if available."""
    if sys.stdin.isatty():
        return None
    content = sys.stdin.read().strip()
    return content if content else None


async def _list_pipelines() -> List[str]:
    """List available pipelines."""
    if not PIPELINES_DIR.exists():
        return []

    result = []
    for f in PIPELINES_DIR.iterdir():
        if f.name.endswith(".pipeline.yaml") or f.name.endswith(".pipeline.yml"):
            name = f.name
            # Remove .pipeline.yaml or .pipeline.yml suffix
            for suffix in (".pipeline.yaml", ".pipeline.yml"):
                if name.endswith(suffix):
                    name = name[: -len(suffix)]
                    break
            result.append(name)
    return result


def show_help() -> None:
    """Show help text."""
    print(
        """
PAI - Personal AI Actions & Pipelines

USAGE:
  pai action <name> [--input '<json>']     Run an action
  pai pipeline <name> [--<param> <value>]  Run a pipeline
  pai actions                               List all actions
  pai pipelines                             List all pipelines
  pai info <name>                           Show action/pipeline details

OPTIONS:
  --mode local|cloud    Execution mode (default: local)
  --input '<json>'      Input as JSON string
  --verbose, -v         Show execution details

EXAMPLES:
  pai action parse/topic --input '{"text":"quantum computing"}'
  echo '{"text":"AI"}' | pai action parse/topic
  pai action parse/topic | pai action transform/summarize
  pai pipeline research --topic "machine learning"
"""
    )


async def main() -> None:
    """Main entry point."""
    args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h"):
        show_help()
        return

    parsed = parse_args(args)
    command = parsed["command"]
    target = parsed["target"]
    options: CLIOptions = parsed["options"]
    extra: Dict[str, str] = parsed["extra"]

    if command == "action":
        if not target:
            print("Error: Action name required. Usage: pai action <name>", file=sys.stderr)
            sys.exit(1)

        # Get input from stdin, --input flag, or extra params
        input_data: Any = None
        stdin_content = read_stdin()

        if stdin_content:
            input_data = json.loads(stdin_content)
        elif options.input:
            input_data = json.loads(options.input)
        elif extra:
            input_data = extra
        else:
            print(
                "Error: No input provided. Use --input, pipe JSON, or pass --<param> <value>",
                file=sys.stderr,
            )
            sys.exit(1)

        if options.verbose:
            print(f"[pai] Running action: {target}", file=sys.stderr)
            print(f"[pai] Mode: {options.mode}", file=sys.stderr)
            print(f"[pai] Input: {json.dumps(input_data)}", file=sys.stderr)

        result = await run_action(target, input_data, {"mode": options.mode})

        if result.success:
            print(json.dumps(result.output))
            if options.verbose and result.metadata:
                print(f"[pai] Duration: {result.metadata.duration_ms}ms", file=sys.stderr)
        else:
            print(json.dumps({"error": result.error}), file=sys.stderr)
            sys.exit(1)

    elif command == "pipeline":
        if not target:
            print("Error: Pipeline name required. Usage: pai pipeline <name>", file=sys.stderr)
            sys.exit(1)
        # TODO: Implement pipeline runner
        print(f"Pipeline execution not yet implemented: {target}", file=sys.stderr)
        print(f"Params: {json.dumps(extra)}", file=sys.stderr)
        sys.exit(1)

    elif command == "actions":
        actions = await list_actions()
        print(json.dumps({"actions": actions}, indent=2))

    elif command == "pipelines":
        pipelines = await _list_pipelines()
        print(json.dumps({"pipelines": pipelines}, indent=2))

    elif command == "info":
        if not target:
            print("Error: Name required. Usage: pai info <action-or-pipeline-name>", file=sys.stderr)
            sys.exit(1)

        # Try loading as action first
        try:
            action = load_action(target)
            info = {
                "type": "action",
                "name": action.name,
                "version": action.version,
                "description": action.description,
                "tags": getattr(action, "tags", None),
                "deployment": getattr(action, "deployment", None),
            }
            print(json.dumps(info, indent=2, default=str))
        except Exception:
            print(f"Not found: {target}", file=sys.stderr)
            sys.exit(1)

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        show_help()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
