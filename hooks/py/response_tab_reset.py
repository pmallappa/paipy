#!/usr/bin/env python3
"""
response_tab_reset.py -- Reset Kitty tab title/color after response.

PURPOSE:
Updates the Kitty terminal tab to show completion state after Claude
finishes responding. Converts the working title to past tense.

TRIGGER: Stop

HANDLER: handlers/tab_state.py
"""

import sys

from paipy import read_hook_input
from handlers.tab_state import handle_tab_state


def main() -> None:
    hook_input = read_hook_input()
    if not hook_input:
        sys.exit(0)

    try:
        # In the Python version, we pass the raw fields since we don't have
        # the full TranscriptParser. The handler will work with what it gets.
        handle_tab_state(
            voice_completion=hook_input.last_assistant_message or "",
            response_state="",
            current_response_text=hook_input.last_assistant_message or "",
            session_id=hook_input.session_id,
        )
    except Exception as e:
        print(f"[ResponseTabReset] Handler failed: {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ResponseTabReset] Fatal: {e}", file=sys.stderr)
        sys.exit(0)
