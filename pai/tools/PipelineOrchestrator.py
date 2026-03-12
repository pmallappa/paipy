#!/usr/bin/env python3
"""
PAI Pipeline Orchestrator - Run Pipelines with Monitoring

Runs pipelines and reports progress to the PipelineMonitor.

USAGE:
  python PipelineOrchestrator.py run <pipeline> [--input '<json>'] [--agent <name>]
  python PipelineOrchestrator.py demo   # Run demo with multiple pipelines
"""

import asyncio
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

TOOLS_DIR = Path(__file__).parent
ACTIONS_DIR = TOOLS_DIR.parent / "ACTIONS"
PIPELINES_DIR = TOOLS_DIR.parent / "PIPELINES"
MONITOR_URL = os.environ.get("MONITOR_URL", "http://localhost:8765")


# Report to monitor
async def report_start(agent: str, pipeline: str, steps: list[dict]) -> Optional[str]:
    if not httpx:
        return None
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{MONITOR_URL}/api/start",
                json={"agent": agent, "pipeline": pipeline, "steps": steps},
            )
            data = res.json()
            return data.get("id")
    except Exception:
        return None


async def report_update(exec_id: str, status: str, result: Any = None, error: Optional[str] = None) -> None:
    if not httpx:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{MONITOR_URL}/api/update",
                json={"id": exec_id, "status": status, "result": result, "error": error},
            )
    except Exception:
        pass


async def report_step(
    execution_id: str,
    step_id: str,
    status: str,
    output: Any = None,
    error: Optional[str] = None,
) -> None:
    if not httpx:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{MONITOR_URL}/api/step",
                json={"executionId": execution_id, "stepId": step_id, "status": status, "output": output, "error": error},
            )
    except Exception:
        pass


# Load pipeline YAML
async def load_pipeline(name: str) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML is required: pip install pyyaml")
    path = PIPELINES_DIR / f"{name}.pipeline.yaml"
    content = path.read_text()
    return yaml.safe_load(content)


# Template interpolation
def interpolate(template: Any, context: dict[str, Any]) -> Any:
    if isinstance(template, str):
        full_match = re.match(r"^\{\{(.+?)\}\}$", template)
        if full_match:
            return resolve_path(full_match.group(1).strip(), context)
        return re.sub(
            r"\{\{(.+?)\}\}",
            lambda m: str(resolve_path(m.group(1).strip(), context) or ""),
            template,
        )
    if isinstance(template, list):
        return [interpolate(item, context) for item in template]
    if isinstance(template, dict):
        return {key: interpolate(value, context) for key, value in template.items()}
    return template


def resolve_path(path: str, context: dict[str, Any]) -> Any:
    parts = path.split(".")
    current: Any = context
    for part in parts:
        if current is None or not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


# Run an action
async def run_action(action_name: str, input_data: Any) -> dict:
    parts = action_name.split("/")
    if len(parts) != 2:
        return {"success": False, "error": f"Invalid action name: {action_name}"}

    category, name = parts
    action_path = ACTIONS_DIR / category / f"{name}.action.ts"

    # Note: In the Python version, we can't directly import .ts action modules
    # This would need to be adapted to use Python action modules
    return {"success": False, "error": f"Action execution not available in Python version: {action_name}"}


# Run a pipeline with monitoring
async def run_pipeline(pipeline_name: str, input_data: dict[str, Any], agent: str) -> dict:
    print(f"[{agent}] Loading pipeline: {pipeline_name}")

    pipeline = await load_pipeline(pipeline_name)
    steps = pipeline.get("steps", [])
    execution_id = await report_start(agent, pipeline_name, steps)

    if execution_id:
        await report_update(execution_id, "running")

    context: dict[str, Any] = {
        "input": input_data,
        "steps": {},
    }

    print(f"[{agent}] Running {len(steps)} steps...")

    for step in steps:
        step_id = step.get("id", "unknown")
        action = step.get("action", "unknown")
        print(f"[{agent}] Step: {step_id} ({action})")

        if execution_id:
            await report_step(execution_id, step_id, "running")

        step_input = interpolate(step.get("input", {}), context)
        result = await run_action(action, step_input)

        if result.get("success"):
            context["steps"][step_id] = {"output": result.get("output")}
            if execution_id:
                await report_step(execution_id, step_id, "completed", result.get("output"))
            print(f"[{agent}] Done: {step_id} completed")
        else:
            if execution_id:
                await report_step(execution_id, step_id, "failed", None, result.get("error"))
                await report_update(execution_id, "failed", None, result.get("error"))
            print(f"[{agent}] Failed: {step_id} failed: {result.get('error')}")
            return {"success": False, "error": result.get("error")}

        await asyncio.sleep(0.2)

    final_result = {"steps": context["steps"]}
    if execution_id:
        await report_update(execution_id, "completed", final_result)

    print(f"[{agent}] Done: Pipeline completed")
    return {"success": True, "result": final_result}


# Demo mode
async def run_demo() -> None:
    print("Starting demo with PAI pipelines...\n")

    jobs = [
        {"agent": "BlogReviewer-1", "pipeline": "blog-review", "input": {"content": "# Sample blog post...", "minWords": 50}},
        {"agent": "BlogReviewer-2", "pipeline": "blog-review", "input": {"content": "# Another blog post...", "minWords": 50}},
        {"agent": "ReportGenerator-1", "pipeline": "content-report", "input": {"title": "Q1 Review", "sections": {}}},
        {"agent": "ReportGenerator-2", "pipeline": "content-report", "input": {"title": "Security Audit", "sections": {}}},
        {"agent": "QAEngineer", "pipeline": "blog-qa", "input": {"title": "Testing", "body": "Sample body...", "minWords": 30}},
    ]

    async def run_with_delay(job: dict, delay: float) -> dict:
        await asyncio.sleep(delay)
        return await run_pipeline(job["pipeline"], job["input"], job["agent"])

    tasks = [run_with_delay(job, i * 0.3) for i, job in enumerate(jobs)]
    results = await asyncio.gather(*tasks)

    print("\n=== Demo Results ===")
    for i, result in enumerate(results):
        status = "Done" if result.get("success") else "Failed"
        print(f"{jobs[i]['agent']}: {status}")


# CLI
async def async_main() -> None:
    args = sys.argv[1:]
    command = args[0] if args else None

    if command == "demo":
        await run_demo()
        return

    if command == "run" and len(args) > 1:
        pipeline_name = args[1]
        input_data: dict[str, Any] = {}
        agent = "Agent-CLI"

        i = 2
        while i < len(args):
            if args[i] == "--input" and i + 1 < len(args):
                input_data = json.loads(args[i + 1])
                i += 2
            elif args[i] == "--agent" and i + 1 < len(args):
                agent = args[i + 1]
                i += 2
            elif args[i].startswith("--"):
                key = args[i][2:]
                value: Any = args[i + 1] if i + 1 < len(args) else ""
                try:
                    value = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    pass
                input_data[key] = value
                i += 2
            else:
                i += 1

        result = await run_pipeline(pipeline_name, input_data, agent)
        print(json.dumps(result, indent=2))
        return

    print("""
PAI Pipeline Orchestrator

USAGE:
  python PipelineOrchestrator.py run <pipeline> [--input '<json>'] [--agent <name>]
  python PipelineOrchestrator.py demo

EXAMPLES:
  python PipelineOrchestrator.py run blog-draft --content "# My Post..."
  python PipelineOrchestrator.py run research --topic "AI agents" --depth 3
  python PipelineOrchestrator.py demo
""")


def main() -> None:
    try:
        asyncio.run(async_main())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
