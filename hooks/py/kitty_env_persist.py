#!/usr/bin/env python3
"""
kitty_env_persist.py -- Kitty terminal env persistence + tab reset (SessionStart).

PURPOSE:
Persists Kitty terminal environment variables (KITTY_LISTEN_ON, KITTY_WINDOW_ID)
to disk so hooks running later (without terminal context) can control tabs.
Also resets tab title to clean state at session start.

TRIGGER: SessionStart
"""

import json
import os
import sys
from pathlib import Path

from paipy import set_tab_state, read_tab_state, get_da_name, memory


def main() -> None:
    pai_dir = os.environ.get("PAI_DIR", os.path.join(str(Path.home()), ".claude"))

    # Skip for subagents
    claude_project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    is_subagent = (
        "/.claude/Agents/" in claude_project_dir
        or os.environ.get("CLAUDE_AGENT_TYPE") is not None
    )
    if is_subagent:
        sys.exit(0)

    # Persist Kitty environment
    kitty_listen_on = os.environ.get("KITTY_LISTEN_ON")
    kitty_window_id = os.environ.get("KITTY_WINDOW_ID")
    if kitty_listen_on and kitty_window_id:
        state_dir = memory("STATE")
        (state_dir / "kitty-env.json").write_text(
            json.dumps(
                {"KITTY_LISTEN_ON": kitty_listen_on, "KITTY_WINDOW_ID": kitty_window_id},
                indent=2,
            )
        )

    # Reset tab title to clean state
    try:
        current = read_tab_state()
        if current and current.get("state") in ("working", "thinking"):
            print(f"Tab in {current['state']} state -- preserving title through compaction", file=sys.stderr)
        else:
            set_tab_state(title=f"{get_da_name()} ready\u2026", state="idle")
            print("Tab title reset to clean state", file=sys.stderr)
    except Exception as err:
        print(f"Failed to reset tab title: {err}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
