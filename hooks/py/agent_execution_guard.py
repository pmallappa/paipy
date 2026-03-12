#!/usr/bin/env python3
"""
PreToolUse (Task): Warn when Algorithm-scope tasks run without background flag.
Non-blocking — injects a reminder only.
"""
import json
import sys
from paipy import read_stdin, allow

ALGORITHM_KEYWORDS = [
    "algorithm", "prd", "observe", "think", "plan", "build",
    "execute", "verify", "learn", "isc", "loop mode",
]


def main():
    data = read_stdin()
    inp = data.get("tool_input", {})
    prompt = str(inp.get("prompt", "")).lower()
    run_in_bg = inp.get("run_in_background", False)

    is_algorithm_task = any(kw in prompt for kw in ALGORITHM_KEYWORDS)

    if is_algorithm_task and not run_in_bg:
        # Inject a reminder but don't block
        reminder = (
            "[AgentExecutionGuard] This looks like an Algorithm-scope task. "
            "Consider setting run_in_background: true for long-running work."
        )
        print(json.dumps({
            "continue": True,
            "system_reminder": reminder,
        }))
    else:
        allow()


if __name__ == "__main__":
    main()
