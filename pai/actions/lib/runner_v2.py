#!/usr/bin/env python3
"""
============================================================================
PAI ACTIONS v2 - Runner with Capability Injection
============================================================================

Loads action packages (action.json + action.py) and provides capabilities.

============================================================================
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from types_v2 import (
    ActionCapabilities,
    ActionContext,
    ActionImplementation,
    ActionManifest,
    ActionResult,
    ActionResultMetadata,
    EnvContext,
    LLMOptions,
    LLMResponse,
    ShellResult,
    validate_schema,
)

ACTIONS_DIR = Path(__file__).parent.parent
USER_ACTIONS_DIR = ACTIONS_DIR.parent / "USER" / "ACTIONS"


# ── Local LLM Provider ──────────────────────────────────────────


async def _create_local_llm():
    """Local LLM provider using PAI's Inference tool."""
    home = Path.home()
    inference_path = home / ".claude" / "PAI" / "Tools" / "Inference.py"

    spec = importlib.util.spec_from_file_location("inference_module", inference_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load inference module from {inference_path}")

    inference_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inference_module)
    inference_fn = inference_module.inference

    async def llm_fn(prompt: str, options: Optional[LLMOptions] = None) -> LLMResponse:
        opts = options or LLMOptions()
        tier_map = {"fast": "fast", "standard": "standard", "smart": "smart"}

        result = await inference_fn(
            user_prompt=prompt,
            system_prompt=opts.system,
            level=tier_map.get(opts.tier or "fast", "fast"),
            expect_json=opts.json,
            max_tokens=opts.max_tokens,
        )

        if not result.get("success"):
            raise RuntimeError(result.get("error", "LLM inference failed"))

        return LLMResponse(
            text=result.get("output", ""),
            json=result.get("parsed"),
            usage=result.get("usage"),
        )

    return llm_fn


# ── Capability Creation ──────────────────────────────────────────


async def _create_local_capabilities(
    required: Optional[List[str]] = None,
) -> ActionCapabilities:
    """Create capability providers for local execution."""
    capabilities = ActionCapabilities()
    required = required or []

    for cap in required:
        if cap == "llm":
            capabilities.llm = await _create_local_llm()

        elif cap == "fetch":
            import urllib.request

            async def fetch_fn(url: str, **kwargs: Any) -> Any:
                req = urllib.request.Request(url, **kwargs)
                with urllib.request.urlopen(req) as response:
                    return response.read()

            capabilities.fetch = fetch_fn

        elif cap == "shell":

            async def shell_fn(cmd: str) -> ShellResult:
                try:
                    result = subprocess.run(
                        ["sh", "-c", cmd],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    return ShellResult(
                        stdout=result.stdout,
                        stderr=result.stderr,
                        code=result.returncode,
                    )
                except subprocess.TimeoutExpired:
                    return ShellResult(stdout="", stderr="Command timed out", code=1)
                except Exception as e:
                    return ShellResult(stdout="", stderr=str(e), code=1)

            capabilities.shell = shell_fn

        elif cap == "readFile":

            async def read_file_fn(path: str) -> str:
                return Path(path).read_text(encoding="utf-8")

            capabilities.read_file = read_file_fn

        elif cap == "writeFile":

            async def write_file_fn(path: str, content: str) -> None:
                Path(path).write_text(content, encoding="utf-8")

            capabilities.write_file = write_file_fn

        # kv would need a backend - skip for now

    return capabilities


# ── Manifest / Implementation Loading ────────────────────────────


def load_manifest(action_path: str) -> ActionManifest:
    """Load an action manifest from a directory."""
    manifest_path = Path(action_path) / "action.json"
    content = manifest_path.read_text(encoding="utf-8")
    return ActionManifest.model_validate_json(content)


def load_implementation(action_path: str) -> Any:
    """Load an action implementation."""
    impl_path = Path(action_path) / "action.py"
    spec = importlib.util.spec_from_file_location("action_impl", impl_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load action from {impl_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "default", module)


# ── Action Resolution ────────────────────────────────────────────


def find_action(name: str) -> Optional[str]:
    """
    Find action directory by name.
    Resolution order: USER/ACTIONS (personal) -> ACTIONS (system/framework)
    Supports: A_NAME (flat, new) or category/name (legacy)
    """
    # New flat format: A_EXTRACT_TRANSCRIPT
    if name.startswith("A_"):
        # Check USER/ACTIONS first (personal actions override system)
        user_path = USER_ACTIONS_DIR / name
        if (user_path / "action.json").exists():
            return str(user_path)

        # Fall back to ACTIONS (system/framework)
        system_path = ACTIONS_DIR / name
        if (system_path / "action.json").exists():
            return str(system_path)

        return None

    # Legacy format: category/name -> check USER first, then SYSTEM
    parts = name.split("/")
    if len(parts) != 2:
        return None

    category, action_name = parts

    # Check USER/ACTIONS first
    user_path = USER_ACTIONS_DIR / category / action_name
    if (user_path / "action.json").exists():
        return str(user_path)

    # Fall back to ACTIONS (system)
    system_path = ACTIONS_DIR / category / action_name
    if (system_path / "action.json").exists():
        return str(system_path)

    return None


# ── Run Action ───────────────────────────────────────────────────


async def run_action(
    name: str,
    input_data: Any = None,
    options: Optional[Dict[str, Any]] = None,
) -> ActionResult:
    """Run an action with capability injection."""
    options = options or {}
    start_time = time.time()
    mode = options.get("mode", "local")

    # Find action
    action_path = find_action(name)
    if not action_path:
        return ActionResult(success=False, error=f"Action not found: {name}")

    try:
        # Load manifest and implementation
        manifest = load_manifest(action_path)
        implementation = load_implementation(action_path)

        # Validate required input fields (simplified -- no jsonschema for new format)
        if manifest.input and "type" not in manifest.input:
            # New simplified format: { field: { type, required } }
            input_obj = input_data if isinstance(input_data, dict) else {}
            for field, field_spec in manifest.input.items():
                if isinstance(field_spec, dict) and field_spec.get("required"):
                    if input_obj.get(field) is None:
                        return ActionResult(success=False, error=f"Missing required input: {field}")
        elif manifest.input and manifest.input.get("type") == "object":
            # Legacy JSON Schema format -- use jsonschema
            validation = validate_schema(input_data, manifest.input)
            if not validation["valid"]:
                errors = ", ".join(validation.get("errors", []))
                return ActionResult(success=False, error=f"Input validation failed: {errors}")

        # Create capabilities
        capabilities = await _create_local_capabilities(manifest.requires)

        # Create context
        ctx = ActionContext(
            capabilities=capabilities,
            env=EnvContext(mode=mode),
        )

        # Execute
        output = await implementation.execute(input_data, ctx)

        duration_ms = int((time.time() - start_time) * 1000)
        return ActionResult(
            success=True,
            output=output,
            metadata=ActionResultMetadata(
                duration_ms=duration_ms,
                action=manifest.name,
                version=manifest.version or "1.0.0",
            ),
        )
    except Exception as err:
        duration_ms = int((time.time() - start_time) * 1000)
        return ActionResult(
            success=False,
            error=str(err),
            metadata=ActionResultMetadata(
                duration_ms=duration_ms,
                action=name,
                version="unknown",
            ),
        )


# ── List Actions ─────────────────────────────────────────────────


async def list_actions_v2() -> List[ActionManifest]:
    """
    List all actions from both USER (personal) and SYSTEM (framework) directories.
    USER actions take precedence over SYSTEM actions with the same name.
    """
    manifests: List[ActionManifest] = []
    seen: set[str] = set()

    def scan_dir(base_dir: Path) -> None:
        if not base_dir.exists():
            return

        try:
            for entry in base_dir.iterdir():
                if not entry.is_dir() or entry.name == "lib":
                    continue

                if entry.name.startswith("A_"):
                    if entry.name in seen:
                        continue
                    try:
                        manifest = load_manifest(str(entry))
                        manifests.append(manifest)
                        seen.add(entry.name)
                    except Exception:
                        pass
                else:
                    # Legacy nested format: category/action
                    cat_path = entry
                    try:
                        for item in cat_path.iterdir():
                            if not item.is_dir():
                                continue
                            key = f"{entry.name}/{item.name}"
                            if key in seen:
                                continue
                            try:
                                manifest = load_manifest(str(item))
                                manifests.append(manifest)
                                seen.add(key)
                            except Exception:
                                pass
                    except Exception:
                        pass
        except Exception:
            pass

    # USER first (personal takes precedence), then SYSTEM
    scan_dir(USER_ACTIONS_DIR)
    scan_dir(ACTIONS_DIR)

    return manifests


# ── CLI ──────────────────────────────────────────────────────────


async def main() -> None:
    """CLI support."""
    args = sys.argv[1:]

    if not args:
        print("Usage: runner_v2.py list | run <action> [input-json]")
        return

    cmd = args[0]

    if cmd == "list":
        actions = await list_actions_v2()
        print(json.dumps({"actions": [a.name for a in actions]}, indent=2))
    elif cmd == "run" and len(args) > 1:
        input_data = json.loads(args[2]) if len(args) > 2 else {}
        result = await run_action(args[1], input_data)
        print(json.dumps(result.model_dump(), indent=2))
    else:
        print("Usage: runner_v2.py list | run <action> [input-json]")


if __name__ == "__main__":
    asyncio.run(main())
