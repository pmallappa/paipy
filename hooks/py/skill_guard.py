#!/usr/bin/env python3
"""
PreToolUse (Skill): Block false-positive skill invocations.
"""
import sys

from paipy import read_stdin, allow, block

# Skills that should never be invoked by the model automatically
BLOCKED_SKILLS = {
    "keybindings-help",
    "keyboard-shortcuts",
}


def main():
    data = read_stdin()
    skill = str(data.get("tool_input", {}).get("skill", "")).lower().strip()

    if skill in BLOCKED_SKILLS:
        block(f"Skill '{skill}' is blocked — false-positive invocation guard.")
    else:
        allow()


if __name__ == "__main__":
    main()
