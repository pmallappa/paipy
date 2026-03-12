#!/usr/bin/env python3
"""
update_tab_title.py -- Tab Title on Prompt Receipt (UserPromptSubmit).

TRIGGER: UserPromptSubmit

PRIME DIRECTIVE:
Show what this session is working on, at a glance, across multiple tabs.

TITLE RULES (enforced by is_valid_working_title):
1. Starts with a gerund (-ing verb)
2. 2-4 words total (ONE sentence)
3. Ends with a period
4. Grammatically complete
5. Specific -- names the actual object being acted on
6. No generic garbage
7. No first-person pronouns

FLOW:
1. Extract quick title from prompt (deterministic, instant) -> purple (thinking)
2. Show validated title -> orange (working)

NOTE: Inference-based summarization is stubbed (requires Inference tool port).
Voice announcements are omitted in the Python port.
"""

import json
import re
import sys
from typing import Optional, Set

from paipy import (
    is_valid_working_title,
    get_working_fallback,
    trim_to_valid_title,
    set_tab_state,
    get_session_one_word,
)

# Common imperative -> gerund mappings
GERUND_MAP = {
    "fix": "Fixing", "update": "Updating", "add": "Adding", "remove": "Removing",
    "delete": "Deleting", "check": "Checking", "create": "Creating", "build": "Building",
    "deploy": "Deploying", "debug": "Debugging", "test": "Testing", "review": "Reviewing",
    "refactor": "Refactoring", "implement": "Implementing", "write": "Writing",
    "read": "Reading", "find": "Finding", "search": "Searching", "install": "Installing",
    "configure": "Configuring", "run": "Running", "start": "Starting", "stop": "Stopping",
    "restart": "Restarting", "open": "Opening", "close": "Closing", "move": "Moving",
    "rename": "Renaming", "merge": "Merging", "revert": "Reverting", "clean": "Cleaning",
    "show": "Showing", "list": "Listing", "get": "Getting", "set": "Setting",
    "make": "Making", "change": "Changing", "modify": "Modifying", "adjust": "Adjusting",
    "improve": "Improving", "optimize": "Optimizing", "analyze": "Analyzing",
    "research": "Researching", "investigate": "Investigating", "explain": "Explaining",
    "push": "Pushing", "pull": "Pulling", "commit": "Committing", "design": "Designing",
}

# Words ending in 'ing' that are NOT gerunds
FALSE_GERUNDS: Set[str] = {
    "something", "nothing", "anything", "everything",
    "morning", "evening", "string", "king", "ring", "thing",
    "bring", "spring", "swing", "wing", "cling", "fling", "sting",
    "during", "using", "being", "ceiling", "feeling",
}

# Words to filter from prompts
FILTER_WORDS: Set[str] = {
    "the", "a", "an", "i", "my", "we", "you", "your", "this", "that", "it",
    "is", "are", "was", "were", "do", "does", "did", "can", "could", "should",
    "would", "will", "have", "has", "had", "just", "also", "need", "want",
    "please", "why", "how", "what", "when", "where", "which", "who", "think",
}


def _extract_prompt_title(prompt: str) -> Optional[str]:
    """Extract a quick title from the prompt text. Deterministic, instant."""
    text = re.sub(r"<[^>]*>", " ", prompt.strip())
    text = re.sub(r"\s+", " ", text)[:200]
    words = [w for w in text.split(" ") if len(w) > 1]
    if not words:
        return None

    first_lower = re.sub(r"[^a-z]", "", words[0].lower())

    if first_lower.endswith("ing") and len(first_lower) > 4 and first_lower not in FALSE_GERUNDS:
        return trim_to_valid_title(words, is_valid_working_title)

    gerund = GERUND_MAP.get(first_lower)
    if gerund:
        rest = " ".join(words[1:3])
        result = f"{gerund} {rest}" if rest else gerund
        return result if result.endswith(".") else result + "."

    return None


def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
        prompt = data.get("prompt", "")

        if not prompt or len(prompt) < 3:
            sys.exit(0)

        # Skip ratings (1-10)
        if re.match(r"^([1-9]|10)$", prompt.strip()):
            sys.exit(0)

        session_id = data.get("session_id")
        session_label = get_session_one_word(session_id) if session_id else None
        prefix = f"{session_label} | " if session_label else ""

        # Phase 1: Immediate deterministic title (purple = thinking)
        quick_title = _extract_prompt_title(prompt)
        thinking_title = quick_title or get_working_fallback()
        set_tab_state(
            title=f"\U0001F9E0 {prefix}{thinking_title}",
            state="thinking",
            session_id=session_id,
        )

        # Phase 2: In the Python port, inference is skipped.
        # Use the deterministic title directly for the working state.
        final_title = quick_title if quick_title and is_valid_working_title(quick_title) else get_working_fallback()
        set_tab_state(
            title=f"\u2699\uFE0F {prefix}{final_title}",
            state="working",
            session_id=session_id,
        )

        print(f'[UpdateTabTitle] "{final_title}"', file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"[UpdateTabTitle] Error: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
