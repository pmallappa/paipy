#!/usr/bin/env python3
"""
question_answered.py -- Reset Tab After Question Answered (PostToolUse).

PURPOSE:
Resets the terminal tab from question state (teal) back to working state (orange)
after the user answers an AskUserQuestion prompt.

TRIGGER: PostToolUse (matcher: AskUserQuestion)
"""

import json
import sys

from paipy import set_tab_state, read_tab_state, strip_prefix


def main() -> None:
    try:
        session_id = None
        try:
            raw = sys.stdin.read()
            if raw.strip():
                parsed = json.loads(raw)
                session_id = parsed.get("session_id")
        except Exception:
            pass

        # Read previous working title saved by set_question_tab
        current_state = read_tab_state(session_id)
        restored_title = "Processing answer."

        if current_state and current_state.get("previousTitle"):
            raw_title = strip_prefix(current_state["previousTitle"])
            if raw_title:
                restored_title = raw_title

        set_tab_state(
            title="\u2699\uFE0F" + restored_title,
            state="working",
            session_id=session_id,
        )
        print("[QuestionAnswered] Tab reset to working state (orange on inactive only)", file=sys.stderr)
    except Exception:
        print("[QuestionAnswered] Kitty remote control unavailable", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
