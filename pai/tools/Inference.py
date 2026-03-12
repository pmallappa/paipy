#!/usr/bin/env python3
"""
INFERENCE - Unified inference tool with three run levels

PURPOSE:
Single inference tool with configurable speed/capability trade-offs:
- Fast: Haiku - quick tasks, simple generation, basic classification
- Standard: Sonnet - balanced reasoning, typical analysis
- Smart: Opus - deep reasoning, strategic decisions, complex analysis

USAGE:
  python Inference.py --level fast <system_prompt> <user_prompt>
  python Inference.py --level standard <system_prompt> <user_prompt>
  python Inference.py --level smart <system_prompt> <user_prompt>
  python Inference.py --json --level fast <system_prompt> <user_prompt>

BILLING: Uses Claude CLI with subscription (not API key)
"""

import json
import os
import re
import subprocess
import sys
import time
from typing import Any, Optional

InferenceLevel = str  # "fast" | "standard" | "smart"

LEVEL_CONFIG = {
    "fast": {"model": "haiku", "defaultTimeout": 15},
    "standard": {"model": "sonnet", "defaultTimeout": 30},
    "smart": {"model": "opus", "defaultTimeout": 90},
}


def inference(options: dict[str, Any]) -> dict[str, Any]:
    """
    Run inference with configurable level.

    options:
      systemPrompt: str
      userPrompt: str
      level: "fast" | "standard" | "smart" (default: "standard")
      expectJson: bool (default: False)
      timeout: int in ms (default: varies by level)

    Returns dict with:
      success: bool
      output: str
      parsed: Any (if expectJson)
      error: str (if failed)
      latencyMs: int
      level: str
    """
    level = options.get("level", "standard")
    config = LEVEL_CONFIG.get(level, LEVEL_CONFIG["standard"])
    start_time = time.time()
    timeout_ms = options.get("timeout", config["defaultTimeout"] * 1000)
    timeout_secs = timeout_ms / 1000

    # Build environment without ANTHROPIC_API_KEY to force subscription auth
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("CLAUDECODE", None)

    args = [
        "claude",
        "--print",
        "--model", config["model"],
        "--tools", "",
        "--output-format", "text",
        "--setting-sources", "",
        "--system-prompt", options["systemPrompt"],
    ]

    try:
        proc = subprocess.run(
            args,
            input=options["userPrompt"],
            capture_output=True,
            text=True,
            timeout=timeout_secs,
            env=env,
        )

        latency_ms = int((time.time() - start_time) * 1000)

        if proc.returncode != 0:
            return {
                "success": False,
                "output": proc.stdout,
                "error": proc.stderr or f"Process exited with code {proc.returncode}",
                "latencyMs": latency_ms,
                "level": level,
            }

        output = proc.stdout.strip()

        # Parse JSON if requested
        if options.get("expectJson"):
            object_match = re.search(r"\{[\s\S]*\}", output)
            array_match = re.search(r"\[[\s\S]*\]", output)

            for candidate in [
                object_match.group(0) if object_match else None,
                array_match.group(0) if array_match else None,
            ]:
                if candidate is None:
                    continue
                try:
                    parsed = json.loads(candidate)
                    return {
                        "success": True,
                        "output": output,
                        "parsed": parsed,
                        "latencyMs": latency_ms,
                        "level": level,
                    }
                except json.JSONDecodeError:
                    continue

            return {
                "success": False,
                "output": output,
                "error": "Failed to parse JSON response",
                "latencyMs": latency_ms,
                "level": level,
            }

        return {
            "success": True,
            "output": output,
            "latencyMs": latency_ms,
            "level": level,
        }

    except subprocess.TimeoutExpired:
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "success": False,
            "output": "",
            "error": f"Timeout after {timeout_ms}ms",
            "latencyMs": latency_ms,
            "level": level,
        }
    except FileNotFoundError:
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "success": False,
            "output": "",
            "error": "'claude' command not found",
            "latencyMs": latency_ms,
            "level": level,
        }
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "latencyMs": latency_ms,
            "level": level,
        }


def main() -> None:
    args = sys.argv[1:]

    expect_json = False
    timeout: Optional[int] = None
    level: InferenceLevel = "standard"
    positional_args: list[str] = []

    i = 0
    while i < len(args):
        if args[i] == "--json":
            expect_json = True
        elif args[i] == "--level" and i + 1 < len(args):
            requested = args[i + 1].lower()
            if requested in ("fast", "standard", "smart"):
                level = requested
            else:
                print(f"Invalid level: {args[i + 1]}. Use fast, standard, or smart.", file=sys.stderr)
                sys.exit(1)
            i += 1
        elif args[i] == "--timeout" and i + 1 < len(args):
            timeout = int(args[i + 1])
            i += 1
        else:
            positional_args.append(args[i])
        i += 1

    if len(positional_args) < 2:
        print(
            "Usage: python Inference.py [--level fast|standard|smart] [--json] "
            "[--timeout <ms>] <system_prompt> <user_prompt>",
            file=sys.stderr,
        )
        sys.exit(1)

    system_prompt, user_prompt = positional_args[0], positional_args[1]

    result = inference({
        "systemPrompt": system_prompt,
        "userPrompt": user_prompt,
        "level": level,
        "expectJson": expect_json,
        "timeout": timeout,
    })

    if result["success"]:
        if expect_json and result.get("parsed"):
            print(json.dumps(result["parsed"]))
        else:
            print(result["output"])
    else:
        print(f"Error: {result.get('error', 'unknown')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
