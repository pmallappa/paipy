#!/usr/bin/env python3
"""
Stop: Cache the last assistant response for RatingCapture.
Writes to memory/state/last-response.txt.
"""
import sys

from paipy import read_stdin, memory

MAX_CHARS = 2000


def extract_last_response(data: dict) -> str:
    # Direct field (Claude Code Stop event)
    msg = data.get("last_assistant_message") or data.get("message") or ""
    if msg:
        return str(msg)[:MAX_CHARS]

    # Fall back to transcript
    transcript_path = data.get("transcript_path", "")
    if transcript_path:
        p = Path(transcript_path)
        if p.exists():
            try:
                lines = p.read_text().splitlines()
                # Find last assistant message
                for line in reversed(lines):
                    try:
                        entry = __import__("json").loads(line)
                        if entry.get("role") == "assistant":
                            content = entry.get("content", "")
                            if isinstance(content, list):
                                for block in content:
                                    if isinstance(block, dict) and block.get("type") == "text":
                                        return block.get("text", "")[:MAX_CHARS]
                            elif isinstance(content, str):
                                return content[:MAX_CHARS]
                    except Exception:
                        continue
            except Exception:
                pass
    return ""


def main():
    data = read_stdin()
    response = extract_last_response(data)
    if response:
        state_dir = memory("STATE")
        (state_dir / "last-response.txt").write_text(response)


if __name__ == "__main__":
    main()
