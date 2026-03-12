#!/usr/bin/env python3
"""
tab_state.py -- Terminal Tab State Manager.

Updates Kitty terminal tab title and color on response completion.
Converts the working title to past tense as primary strategy,
falls back to voice line extraction, then generic fallback.

Pure handler: receives pre-parsed data, updates Kitty tab.
"""

import re
import sys
from typing import Dict, Any, Optional

from paipy import (
    set_tab_state, read_tab_state, strip_prefix, set_phase_tab,
    is_valid_completion_title, gerund_to_past_tense, get_working_fallback, trim_to_valid_title,
    get_da_name,
)


def _extract_tab_title(voice_line: str) -> Optional[str]:
    """
    Extract tab title from voice line. Takes first sentence, caps at 4 words.
    Validates with is_valid_completion_title. Returns None if invalid.
    """
    if not voice_line or len(voice_line) < 3:
        return None

    cleaned = voice_line
    cleaned = re.sub(r"^\U0001F5E3\uFE0F\s*", "", cleaned)
    da_name = get_da_name()
    cleaned = re.sub(rf"^{re.escape(da_name)}:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(Done\.?\s*)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(I've\s+|I\s+)", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip()

    if not cleaned or len(cleaned) < 3:
        return None

    sentences = cleaned.split(". ")
    first_sentence = sentences[0].rstrip(".").strip()

    first_words = first_sentence.split()
    if len(first_words) == 1 and len(sentences) > 1:
        next_words = sentences[1].split()[:3]
        first_sentence = first_words[0] + " " + " ".join(next_words)

    words = first_sentence.split()
    if not words:
        return None

    return trim_to_valid_title(words, is_valid_completion_title)


def _extract_from_response_content(response_text: str) -> Optional[str]:
    """
    Extract a completion title from the response content.
    Tries TASK line, then SUMMARY section as fallback.
    """
    if not response_text or len(response_text) < 10:
        return None

    # Strategy 1: Extract from TASK line
    task_match = re.search(r"\U0001F4D2\s*TASK:\s*(.+?)(?:\n|$)", response_text, re.IGNORECASE)
    if task_match and task_match.group(1):
        task_desc = task_match.group(1).strip()
        words = task_desc.split()
        if len(words) >= 2:
            past_map = {
                "fix": "Fixed", "update": "Updated", "add": "Added", "remove": "Removed",
                "create": "Created", "build": "Built", "deploy": "Deployed", "debug": "Debugged",
                "test": "Tested", "review": "Reviewed", "refactor": "Refactored", "implement": "Implemented",
                "write": "Wrote", "find": "Found", "install": "Installed", "configure": "Configured",
                "run": "Ran", "check": "Checked", "clean": "Cleaned", "merge": "Merged",
                "change": "Changed", "improve": "Improved", "optimize": "Optimized", "analyze": "Analyzed",
                "research": "Researched", "investigate": "Investigated", "design": "Designed",
                "push": "Pushed", "pull": "Pulled", "commit": "Committed", "move": "Moved",
                "rename": "Renamed", "delete": "Deleted", "start": "Started", "stop": "Stopped",
                "restart": "Restarted", "set": "Set", "get": "Got", "make": "Made", "show": "Showed",
                "list": "Listed", "search": "Searched", "explain": "Explained", "modify": "Modified",
            }
            first_lower = words[0].lower()
            past = past_map.get(first_lower)
            if past:
                rest = " ".join(words[1:3])
                candidate = f"{past} {rest}."
                if is_valid_completion_title(candidate):
                    return candidate

    # Strategy 2: Extract from SUMMARY line
    summary_match = re.search(r"\U0001F4CB\s*SUMMARY:\s*(.+?)(?:\n|$)", response_text, re.IGNORECASE)
    if summary_match and summary_match.group(1):
        summary = re.sub(r"^\[?\d+\s*bullets?\]?\s*", "", summary_match.group(1).strip(), flags=re.IGNORECASE)
        words = summary.split()
        if len(words) >= 2:
            candidate = trim_to_valid_title(words, is_valid_completion_title)
            if candidate:
                return candidate

    return None


def handle_tab_state(
    voice_completion: str = "",
    response_state: str = "",
    current_response_text: str = "",
    session_id: Optional[str] = None,
) -> None:
    """Handle tab state update with parsed transcript data."""
    try:
        # Don't overwrite question state
        if response_state == "awaitingInput":
            return

        # PRIMARY: Convert working title to past tense
        short_title: Optional[str] = None
        current_state = read_tab_state(session_id)
        if current_state:
            raw_title = strip_prefix(current_state.get("title", ""))
            pipe_idx = raw_title.find(" | ")
            if pipe_idx != -1:
                raw_title = raw_title[pipe_idx + 3:]
            if raw_title and raw_title not in ("Done.", "Processing.", "Processing request.", get_working_fallback()) and not raw_title.endswith("ready\u2026"):
                words = raw_title.rstrip(".").split()
                if len(words) >= 2 and words[0].lower().endswith("ing"):
                    words[0] = gerund_to_past_tense(words[0])
                candidate = " ".join(words) + "."
                if is_valid_completion_title(candidate):
                    short_title = candidate

        # FALLBACK 1: Extract from voice line
        if not short_title:
            short_title = _extract_tab_title(voice_completion)

        # FALLBACK 2: Extract from response content
        if not short_title:
            short_title = _extract_from_response_content(current_response_text)
            if short_title:
                print(f'[TabState] Extracted title from response content: "{short_title}"', file=sys.stderr)

        # FALLBACK 3: Pass None -- let set_phase_tab use session name
        if not short_title:
            print("[TabState] All extraction strategies failed, deferring to session name", file=sys.stderr)

        if session_id:
            summary = short_title.rstrip(".") if short_title else None
            set_phase_tab("COMPLETE", session_id, summary)
            print(f'[TabState] Completion: "{short_title or "(session name fallback)"}"', file=sys.stderr)
        else:
            tab_title = f"\u2705 {short_title or 'Done.'}"
            print(f'[TabState] {response_state}: "{tab_title}"', file=sys.stderr)
            set_tab_state(title=tab_title, state="completed", session_id=None)
    except Exception as e:
        print(f"[TabState] Failed: {e}", file=sys.stderr)
