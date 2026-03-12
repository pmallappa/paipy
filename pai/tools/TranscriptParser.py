#!/usr/bin/env python3
"""
TranscriptParser - Claude transcript parsing utilities

Shared library for extracting content from Claude Code transcript files.
Used by Stop hooks for voice, tab state, and response capture.

CLI Usage:
  python TranscriptParser.py <transcript_path>
  python TranscriptParser.py <transcript_path> --voice
  python TranscriptParser.py <transcript_path> --plain
  python TranscriptParser.py <transcript_path> --structured
  python TranscriptParser.py <transcript_path> --state

Module Usage:
  from TranscriptParser import parse_transcript, get_last_assistant_message
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# DA identity name - simplified (in TS version this comes from identity module)
DA_NAME = "PAI"


# ============================================================================
# Types
# ============================================================================


@dataclass
class StructuredResponse:
    date: Optional[str] = None
    summary: Optional[str] = None
    analysis: Optional[str] = None
    actions: Optional[str] = None
    results: Optional[str] = None
    status: Optional[str] = None
    next: Optional[str] = None
    completed: Optional[str] = None


@dataclass
class ParsedTranscript:
    raw: str = ""
    last_message: str = ""
    current_response_text: str = ""
    voice_completion: str = ""
    plain_completion: str = ""
    structured: StructuredResponse = field(default_factory=StructuredResponse)
    response_state: str = "completed"  # 'awaitingInput' | 'completed' | 'error'


# ============================================================================
# Core Parsing Functions
# ============================================================================


def content_to_text(content: Any) -> str:
    """Safely convert Claude content (string or array of blocks) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, str):
                parts.append(c)
            elif isinstance(c, dict):
                if c.get("text"):
                    parts.append(c["text"])
                elif c.get("content"):
                    parts.append(content_to_text(c["content"]))
        return " ".join(parts).strip()
    return ""


def parse_last_assistant_message(transcript_content: str) -> str:
    """Parse last assistant message from transcript content."""
    last_message = ""
    for line in transcript_content.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if entry.get("type") == "assistant" and entry.get("message", {}).get("content"):
                text = content_to_text(entry["message"]["content"])
                if text:
                    last_message = text
        except (json.JSONDecodeError, KeyError):
            continue
    return last_message


def collect_current_response_text(transcript_content: str) -> str:
    """
    Collect assistant text from the CURRENT response turn only.
    A 'turn' is everything after the last human message in the transcript.
    """
    lines = transcript_content.strip().splitlines()
    last_human_index = -1

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if entry.get("type") in ("human", "user"):
                content = entry.get("message", {}).get("content")
                if isinstance(content, str):
                    last_human_index = i
                elif isinstance(content, list):
                    has_text = any(
                        isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip()
                        for b in content
                    )
                    if has_text:
                        last_human_index = i
        except (json.JSONDecodeError, KeyError):
            continue

    text_parts: list[str] = []
    for i in range(last_human_index + 1, len(lines)):
        line = lines[i].strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if entry.get("type") == "assistant" and entry.get("message", {}).get("content"):
                text = content_to_text(entry["message"]["content"])
                if text:
                    text_parts.append(text)
        except (json.JSONDecodeError, KeyError):
            continue

    return "\n".join(text_parts)


def get_last_assistant_message(transcript_path: str) -> str:
    """Get last assistant message from transcript file."""
    try:
        content = Path(transcript_path).read_text()
        return parse_last_assistant_message(content)
    except Exception as e:
        print(f"[TranscriptParser] Error reading transcript: {e}", file=sys.stderr)
        return ""


# ============================================================================
# Extraction Functions
# ============================================================================


def extract_voice_completion(text: str) -> str:
    """Extract voice completion line for TTS. Uses LAST match."""
    text = re.sub(r"<system-reminder>[\s\S]*?</system-reminder>", "", text)

    patterns = [
        re.compile(rf"\U0001F5E3\uFE0F?\s*\*{{0,2}}{re.escape(DA_NAME)}:?\*{{0,2}}\s*(.+?)(?:\n|$)", re.IGNORECASE),
        re.compile(r"\U0001F3AF\s*\*{0,2}COMPLETED:?\*{0,2}\s*(.+?)(?:\n|$)", re.IGNORECASE),
    ]

    for pattern in patterns:
        matches = list(pattern.finditer(text))
        if matches:
            last_match = matches[-1]
            completed = last_match.group(1).strip()
            completed = re.sub(r"^\[AGENT:\w+\]\s*", "", completed, flags=re.IGNORECASE)
            return completed.strip()

    return ""


def extract_completion_plain(text: str) -> str:
    """Extract plain completion text for display/tab titles. Uses LAST match."""
    text = re.sub(r"<system-reminder>[\s\S]*?</system-reminder>", "", text)

    patterns = [
        re.compile(rf"\U0001F5E3\uFE0F?\s*\*{{0,2}}{re.escape(DA_NAME)}:?\*{{0,2}}\s*(.+?)(?:\n|$)", re.IGNORECASE),
        re.compile(r"\U0001F3AF\s*\*{0,2}COMPLETED:?\*{0,2}\s*(.+?)(?:\n|$)", re.IGNORECASE),
    ]

    for pattern in patterns:
        matches = list(pattern.finditer(text))
        if matches:
            last_match = matches[-1]
            completed = last_match.group(1).strip()
            completed = re.sub(r"^\[AGENT:\w+\]\s*", "", completed, flags=re.IGNORECASE)
            completed = re.sub(r"\[.*?\]", "", completed)
            completed = completed.replace("**", "").replace("*", "")
            # Remove emojis
            completed = re.sub(r"[\U00010000-\U0010ffff]", "", completed)
            completed = re.sub(r"\s+", " ", completed).strip()
            return completed

    # Fallback: summary line
    summary_match = re.search(r"\U0001F4CB\s*\*{0,2}SUMMARY:?\*{0,2}\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
    if summary_match:
        summary = summary_match.group(1).strip()[:30]
        return summary[:27] + "\u2026" if len(summary) > 27 else summary

    return ""


def extract_structured_sections(text: str) -> StructuredResponse:
    """Extract structured sections from response."""
    result = StructuredResponse()
    text = re.sub(r"<system-reminder>[\s\S]*?</system-reminder>", "", text)

    patterns: dict[str, re.Pattern] = {
        "date": re.compile(r"\U0001F4C5\s*(.+?)(?:\n|$)", re.IGNORECASE),
        "summary": re.compile(r"\U0001F4CB\s*SUMMARY:\s*(.+?)(?:\n|$)", re.IGNORECASE),
        "analysis": re.compile(r"\U0001F50D\s*ANALYSIS:\s*(.+?)(?:\n|$)", re.IGNORECASE),
        "actions": re.compile(r"\u26A1\s*ACTIONS:\s*(.+?)(?:\n|$)", re.IGNORECASE),
        "results": re.compile(r"\u2705\s*RESULTS:\s*(.+?)(?:\n|$)", re.IGNORECASE),
        "status": re.compile(r"\U0001F4CA\s*STATUS:\s*(.+?)(?:\n|$)", re.IGNORECASE),
        "next": re.compile(r"\u27A1\uFE0F?\s*NEXT:\s*(.+?)(?:\n|$)", re.IGNORECASE),
        "completed": re.compile(
            rf"(?:\U0001F5E3\uFE0F?\s*{re.escape(DA_NAME)}:|\U0001F3AF\s*COMPLETED:)\s*(.+?)(?:\n|$)",
            re.IGNORECASE,
        ),
    }

    for key, pattern in patterns.items():
        match = pattern.search(text)
        if match:
            setattr(result, key, match.group(1).strip())

    return result


# ============================================================================
# State Detection
# ============================================================================


def detect_response_state(last_message: str, transcript_content: str) -> str:
    """Detect response state for tab coloring."""
    try:
        last_assistant_entry = None
        for line in transcript_content.strip().splitlines():
            try:
                entry = json.loads(line)
                if entry.get("type") == "assistant" and entry.get("message", {}).get("content"):
                    last_assistant_entry = entry
            except (json.JSONDecodeError, KeyError):
                continue

        if last_assistant_entry and last_assistant_entry.get("message", {}).get("content"):
            content = last_assistant_entry["message"]["content"]
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "AskUserQuestion":
                        return "awaitingInput"
    except Exception as e:
        print(f"[TranscriptParser] Error detecting response state: {e}", file=sys.stderr)

    if re.search(r"\U0001F4CA\s*STATUS:.*(?:error|failed|broken|problem|issue)", last_message, re.IGNORECASE):
        return "error"

    has_error_keyword = bool(re.search(r"\b(?:error|failed|exception|crash|broken)\b", last_message, re.IGNORECASE))
    has_error_emoji = bool(re.search(r"\u274C|\U0001F6A8|\u26A0\uFE0F", last_message))
    if has_error_keyword and has_error_emoji:
        return "error"

    return "completed"


# ============================================================================
# Unified Parser
# ============================================================================


def parse_transcript(transcript_path: str) -> ParsedTranscript:
    """Parse transcript and extract all relevant data in one pass."""
    try:
        raw = Path(transcript_path).read_text()
        last_message = parse_last_assistant_message(raw)
        current_response_text = collect_current_response_text(raw)

        return ParsedTranscript(
            raw=raw,
            last_message=last_message,
            current_response_text=current_response_text,
            voice_completion=extract_voice_completion(current_response_text),
            plain_completion=extract_completion_plain(current_response_text),
            structured=extract_structured_sections(current_response_text),
            response_state=detect_response_state(last_message, raw),
        )
    except Exception as e:
        print(f"[TranscriptParser] Error parsing transcript: {e}", file=sys.stderr)
        return ParsedTranscript()


# ============================================================================
# CLI
# ============================================================================


def main() -> None:
    args = sys.argv[1:]
    transcript_path = next((a for a in args if not a.startswith("-")), None)

    if not transcript_path:
        print("""Usage: python TranscriptParser.py <transcript_path> [options]

Options:
  --voice       Output voice completion (for TTS)
  --plain       Output plain completion (for tab titles)
  --structured  Output structured sections as JSON
  --state       Output response state
  --all         Output full parsed transcript as JSON (default)
""")
        sys.exit(1)

    parsed = parse_transcript(transcript_path)

    if "--voice" in args:
        print(parsed.voice_completion)
    elif "--plain" in args:
        print(parsed.plain_completion)
    elif "--structured" in args:
        structured_dict = {
            k: v for k, v in parsed.structured.__dict__.items() if v is not None
        }
        print(json.dumps(structured_dict, indent=2))
    elif "--state" in args:
        print(parsed.response_state)
    else:
        result = {
            "lastMessage": parsed.last_message,
            "currentResponseText": parsed.current_response_text,
            "voiceCompletion": parsed.voice_completion,
            "plainCompletion": parsed.plain_completion,
            "structured": {k: v for k, v in parsed.structured.__dict__.items() if v is not None},
            "responseState": parsed.response_state,
        }
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
