#!/usr/bin/env python3
"""
set_question_tab.py -- Tab Color for User Input (PreToolUse).

PURPOSE:
Changes the terminal tab color to teal when Claude invokes the
AskUserQuestion tool. Parses the question's header field to show
a short summary of what needs answering.

TRIGGER: PreToolUse (matcher: AskUserQuestion)
"""

import json
import sys

from paipy import set_tab_state, read_tab_state, is_valid_question_title, get_question_fallback

FALLBACK_TITLE = get_question_fallback()


def _extract_summary(data: dict) -> str:
    """Extract a short summary from the AskUserQuestion tool_input."""
    try:
        questions = data.get("tool_input", {}).get("questions", [])
        if not isinstance(questions, list) or not questions:
            return FALLBACK_TITLE

        q = questions[0]

        # Prefer the header field
        if q.get("header") and isinstance(q["header"], str) and q["header"].strip():
            return q["header"].strip()

        # Fallback: first 3 words of the question text
        if q.get("question") and isinstance(q["question"], str):
            words = q["question"].strip().split()[:3]
            return " ".join(words).rstrip("?")
    except Exception:
        pass
    return FALLBACK_TITLE


def main() -> None:
    summary = FALLBACK_TITLE
    session_id = None

    try:
        raw = sys.stdin.read()
        if raw.strip():
            parsed = json.loads(raw)
            summary = _extract_summary(parsed)
            session_id = parsed.get("session_id")
    except Exception:
        pass

    if not is_valid_question_title(summary):
        summary = FALLBACK_TITLE

    try:
        current_state = read_tab_state(session_id)
        previous_title = current_state.get("title") if current_state else None

        set_tab_state(
            title=summary,
            state="question",
            previous_title=previous_title,
            session_id=session_id,
        )
        print(f'[SetQuestionTab] Tab set to teal with summary: "{summary}"', file=sys.stderr)
    except Exception:
        print("[SetQuestionTab] Kitty remote control unavailable", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
