#!/usr/bin/env python3
"""
============================================================================
PAI ACTIONS - Local Runner
============================================================================

Executes actions locally or dispatches to cloud workers.
Handles input validation, execution, output validation.

USAGE:
  # As library
  from runner import run_action
  result = await run_action('parse/topic', {'text': 'quantum computing'})

  # As CLI (via pai wrapper)
  echo '{"text":"quantum"}' | python runner.py parse/topic
  python runner.py parse/topic --input '{"text":"quantum"}'

============================================================================
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import sys
import time
import uuid
from glob import glob
from pathlib import Path
from typing import Any, Dict, List, Optional

from types_module import ActionContext, ActionResult, ActionResultMetadata, ActionSpec

ACTIONS_DIR = Path(__file__).parent.parent


def load_action(name: str) -> Any:
    """Load an action by name."""
    # Convert category/name to path: parse/topic -> parse/topic.action.py
    action_path = ACTIONS_DIR / f"{name}.action.py"

    if not action_path.exists():
        raise FileNotFoundError(f"Action not found: {name} (looked in {action_path})")

    spec = importlib.util.spec_from_file_location(f"action_{name.replace('/', '_')}", action_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Action {name} does not export a valid ActionSpec")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    action = getattr(module, "default", None) or getattr(module, "action", None)
    if action is None or not hasattr(action, "execute"):
        raise ImportError(f"Action {name} does not export a valid ActionSpec")

    return action


async def run_action(
    name: str,
    input_data: Any,
    options: Optional[Dict[str, Any]] = None,
) -> ActionResult:
    """Run an action with input validation."""
    options = options or {}
    start_time = time.time()
    mode = options.get("mode", "local")

    try:
        action = load_action(name)

        # Validate input using Pydantic model if available
        validated_input = input_data
        if hasattr(action, "inputSchema") and action.inputSchema:
            validated_input = action.inputSchema.model_validate(input_data)

        # Build context
        ctx = ActionContext(
            mode=mode,
            env=options.get("env", dict(os.environ)),
            trace=(
                {
                    "trace_id": options.get("trace_id", ""),
                    "span_id": str(uuid.uuid4())[:8],
                }
                if options.get("trace_id")
                else None
            ),
        )

        if mode == "cloud":
            return await _dispatch_to_cloud(name, validated_input, ctx)

        # Execute locally
        output = await action.execute(validated_input, ctx)

        # Validate output
        validated_output = output
        if hasattr(action, "outputSchema") and action.outputSchema:
            validated_output = action.outputSchema.model_validate(output)

        duration_ms = int((time.time() - start_time) * 1000)

        return ActionResult(
            success=True,
            output=validated_output if isinstance(validated_output, dict) else (
                validated_output.model_dump() if hasattr(validated_output, "model_dump") else validated_output
            ),
            metadata=ActionResultMetadata(
                duration_ms=duration_ms,
                action=name,
                mode=mode,
            ),
        )
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return ActionResult(
            success=False,
            error=str(e),
            metadata=ActionResultMetadata(
                duration_ms=duration_ms,
                action=name,
                mode=mode,
            ),
        )


async def _dispatch_to_cloud(
    name: str,
    input_data: Any,
    ctx: ActionContext,
) -> ActionResult:
    """Dispatch to cloud worker."""
    import urllib.request
    import urllib.error

    start_time = time.time()
    worker_name = name.replace("/", "-")
    cf_subdomain = os.environ.get("CF_ACCOUNT_SUBDOMAIN", "workers")
    worker_url = f"https://pai-{worker_name}.{cf_subdomain}.dev"

    try:
        data = json.dumps(input_data).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if ctx.trace:
            headers["X-Trace-Id"] = ctx.trace.get("trace_id", "")

        req = urllib.request.Request(worker_url, data=data, headers=headers, method="POST")

        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))

        duration_ms = int((time.time() - start_time) * 1000)
        return ActionResult(
            success=True,
            output=result,
            metadata=ActionResultMetadata(
                duration_ms=duration_ms,
                action=name,
                mode="cloud",
            ),
        )
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        duration_ms = int((time.time() - start_time) * 1000)
        return ActionResult(
            success=False,
            error=f"Worker error ({e.code}): {error_body}",
            metadata=ActionResultMetadata(
                duration_ms=duration_ms,
                action=name,
                mode="cloud",
            ),
        )
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return ActionResult(
            success=False,
            error=str(e),
            metadata=ActionResultMetadata(
                duration_ms=duration_ms,
                action=name,
                mode="cloud",
            ),
        )


async def list_actions() -> List[str]:
    """List all available actions."""
    pattern = str(ACTIONS_DIR / "**" / "*.action.py")
    files = glob(pattern, recursive=True)
    actions_dir_str = str(ACTIONS_DIR) + os.sep

    return [
        f.replace(actions_dir_str, "").replace(".action.py", "")
        for f in files
    ]


async def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PAI Action Runner",
        usage="python runner.py <action-name> [--mode local|cloud] [--input '<json>']",
    )
    parser.add_argument("action", nargs="?", help="Action name (e.g., parse/topic)")
    parser.add_argument("--mode", choices=["local", "cloud"], default="local", help="Execution mode")
    parser.add_argument("--input", dest="input_json", help="Input as JSON string")
    parser.add_argument("--list", action="store_true", help="List available actions")

    args = parser.parse_args()

    if args.list:
        actions = await list_actions()
        print(json.dumps({"actions": actions}, indent=2))
        return

    if not args.action:
        parser.print_help()
        sys.exit(1)

    # Get input from stdin or --input flag
    input_data = None

    if args.input_json:
        input_data = json.loads(args.input_json)
    elif not sys.stdin.isatty():
        stdin_content = sys.stdin.read().strip()
        if stdin_content:
            input_data = json.loads(stdin_content)

    if input_data is None:
        print("Error: No input provided. Use --input or pipe JSON to stdin.", file=sys.stderr)
        sys.exit(1)

    result = await run_action(args.action, input_data, {"mode": args.mode})

    if result.success:
        print(json.dumps(result.output))
    else:
        print(
            json.dumps({"error": result.error, "metadata": result.metadata.model_dump() if result.metadata else None}),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
