#!/usr/bin/env python3
"""
FailureCapture.py - Full Context Failure Analysis System

Creates comprehensive context dumps for low-sentiment events (ratings 1-3)
to enable retroactive learning system analysis.

Usage:
  python FailureCapture.py <transcript_path> <rating> <sentiment_summary> [detailed_context]
  python FailureCapture.py --migrate
"""

import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Defer import to avoid circular dependency at module level
# from .Inference import inference  # imported lazily below

PAI_DIR = os.environ.get("PAI_DIR", os.path.join(os.environ.get("HOME", str(Path.home())), ".claude"))


def content_to_text(content: Any) -> str:
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
        return "\n".join(parts).strip()
    return ""


def parse_transcript(transcript_path: str) -> dict:
    entries = []
    tool_calls = []
    conversations = []

    try:
        content = Path(transcript_path).read_text()
        for line in content.strip().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                entries.append(entry)

                if entry.get("type") == "user" and entry.get("message", {}).get("content"):
                    text = content_to_text(entry["message"]["content"])
                    if text:
                        conversations.append({
                            "role": "user", "content": text,
                            "timestamp": entry.get("timestamp"),
                        })

                if entry.get("type") == "assistant" and entry.get("message", {}).get("content"):
                    text = content_to_text(entry["message"]["content"])
                    if text:
                        conversations.append({
                            "role": "assistant", "content": text,
                            "timestamp": entry.get("timestamp"),
                        })

                    msg_content = entry["message"]["content"]
                    if isinstance(msg_content, list):
                        for block in msg_content:
                            if isinstance(block, dict) and block.get("type") == "tool_use":
                                tool_calls.append({
                                    "name": block.get("name"),
                                    "input": block.get("input"),
                                    "timestamp": entry.get("timestamp"),
                                })

                if entry.get("type") in ("tool_result", "tool_output"):
                    if tool_calls and not tool_calls[-1].get("output"):
                        tool_calls[-1]["output"] = content_to_text(
                            entry.get("content") or entry.get("output", "")
                        )
            except json.JSONDecodeError:
                pass
    except Exception as err:
        print(f"[FailureCapture] Error parsing transcript: {err}", file=sys.stderr)

    return {"entries": entries, "toolCalls": tool_calls, "conversations": conversations}


async def generate_description(
    sentiment_summary: str,
    conversations: list[dict],
    tool_calls: list[dict],
) -> str:
    recent_convos = "\n".join(
        f"{c['role'].upper()}: {c['content'][:200]}"
        for c in conversations[-6:]
    )
    recent_tools = ", ".join(t["name"] for t in tool_calls[-5:] if t.get("name"))

    system_prompt = (
        "Generate a SHORT, SPECIFIC description of what went wrong. "
        "EXACTLY 8 words in lowercase kebab-case. Return ONLY the description."
    )
    user_prompt = (
        f"SENTIMENT: {sentiment_summary}\n\n"
        f"RECENT CONVERSATION:\n{recent_convos}\n\n"
        f"TOOLS USED: {recent_tools or 'none'}\n\n"
        "Generate the 8-word description:"
    )

    try:
        from .Inference import inference
        result = await inference({
            "systemPrompt": system_prompt,
            "userPrompt": user_prompt,
            "level": "fast",
            "timeout": 10000,
        })
        if result.get("success") and result.get("output"):
            desc = result["output"].strip().lower()
            desc = re.sub(r"[^a-z0-9\s-]", "", desc)
            desc = re.sub(r"\s+", "-", desc)
            words = [w for w in desc.split("-") if w]
            if len(words) > 10:
                desc = "-".join(words[:8])
            elif len(words) < 5:
                desc = f"low-rating-failure-{'-'.join(words)}"
            return desc
    except Exception as err:
        print(f"[FailureCapture] Inference error: {err}", file=sys.stderr)

    fallback = re.sub(r"[^a-z0-9\s]", "", sentiment_summary.lower())
    return "-".join(fallback.split()[:8]) or "unspecified-failure-needs-manual-review"


def get_pst_components() -> dict[str, str]:
    try:
        from datetime import timezone, timedelta
        pst = timezone(timedelta(hours=-8))
        now = datetime.now(pst)
    except Exception:
        now = datetime.now()

    return {
        "year": str(now.year),
        "month": f"{now.month:02d}",
        "day": f"{now.day:02d}",
        "hours": f"{now.hour:02d}",
        "minutes": f"{now.minute:02d}",
        "seconds": f"{now.second:02d}",
    }


async def capture_failure(
    transcript_path: str,
    rating: int,
    sentiment_summary: str,
    detailed_context: str = "",
    session_id: str = "",
) -> Optional[str]:
    if rating > 3:
        print(f"[FailureCapture] Rating {rating} is above threshold (1-3), skipping", file=sys.stderr)
        return None

    if not os.path.exists(transcript_path):
        print(f"[FailureCapture] Transcript not found: {transcript_path}", file=sys.stderr)
        return None

    parsed = parse_transcript(transcript_path)
    entries = parsed["entries"]
    tool_calls = parsed["toolCalls"]
    conversations = parsed["conversations"]

    description = await generate_description(sentiment_summary, conversations, tool_calls)

    t = get_pst_components()
    timestamp = f"{t['year']}-{t['month']}-{t['day']}-{t['hours']}{t['minutes']}{t['seconds']}"
    dir_name = f"{timestamp}_{description}"
    year_month = f"{t['year']}-{t['month']}"

    failures_dir = os.path.join(PAI_DIR, "MEMORY", "LEARNING", "FAILURES", year_month)
    failure_dir = os.path.join(failures_dir, dir_name)
    os.makedirs(failure_dir, exist_ok=True)

    # Copy transcript
    shutil.copy2(transcript_path, os.path.join(failure_dir, "transcript.jsonl"))

    # sentiment.json
    sentiment_data = {
        "rating": rating,
        "summary": sentiment_summary,
        "detailed_context": detailed_context,
        "session_id": session_id,
        "captured_at": datetime.utcnow().isoformat() + "Z",
        "transcript_source": os.path.basename(transcript_path),
    }
    Path(os.path.join(failure_dir, "sentiment.json")).write_text(
        json.dumps(sentiment_data, indent=2)
    )

    # tool-calls.json
    Path(os.path.join(failure_dir, "tool-calls.json")).write_text(
        json.dumps(tool_calls, indent=2)
    )

    # CONTEXT.md
    conv_summary = "\n\n".join(
        f"**{c['role'].upper()}:** {c['content'][:500]}{'...' if len(c['content']) > 500 else ''}"
        for c in conversations[-10:]
    )
    tool_summary = "\n".join(
        f"- **{tc['name']}**: {json.dumps(tc['input'])[:200]}..."
        for tc in tool_calls[-10:]
    ) if tool_calls else "No tool calls recorded"

    context_md = f"""---
capture_type: FAILURE_ANALYSIS
timestamp: {t['year']}-{t['month']}-{t['day']} {t['hours']}:{t['minutes']}:{t['seconds']} PST
rating: {rating}
description: {description}
session_id: {session_id or 'unknown'}
---

# Failure Analysis: {description.replace('-', ' ')}

**Date:** {t['year']}-{t['month']}-{t['day']}
**Rating:** {rating}/10
**Summary:** {sentiment_summary}

---

## What Happened

{detailed_context or 'No detailed analysis available. Review the transcript for context.'}

---

## Conversation Summary

{conv_summary}

---

## Tool Calls ({len(tool_calls)} total)

{tool_summary}

---

## Files in This Capture

| File | Description |
|------|-------------|
| `CONTEXT.md` | This analysis document |
| `transcript.jsonl` | Full raw conversation ({len(entries)} entries) |
| `sentiment.json` | Sentiment analysis metadata |
| `tool-calls.json` | Extracted tool invocations ({len(tool_calls)} calls) |

---

## Learning System Notes

This failure has been captured for retroactive analysis.

**Action Required:** This capture needs manual review to extract learnings.
"""
    Path(os.path.join(failure_dir, "CONTEXT.md")).write_text(context_md)

    print(f"[FailureCapture] Created failure capture at: {failure_dir}", file=sys.stderr)
    return failure_dir


def main() -> None:
    import asyncio

    args = sys.argv[1:]

    if not args:
        print("Usage:")
        print("  python FailureCapture.py <transcript_path> <rating> <sentiment_summary> [detailed_context]")
        print("  python FailureCapture.py --migrate")
        sys.exit(1)

    if args[0] == "--migrate":
        print("[FailureCapture] Migration not implemented in Python version yet")
        sys.exit(0)

    if len(args) >= 3:
        transcript_path, rating_str, sentiment_summary = args[0], args[1], args[2]
        detailed_context = args[3] if len(args) > 3 else ""
        result = asyncio.run(capture_failure(
            transcript_path, int(rating_str), sentiment_summary, detailed_context
        ))
        if result:
            print(result)
        else:
            sys.exit(1)
    else:
        print("Error: insufficient arguments", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
