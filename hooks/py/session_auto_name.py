#!/usr/bin/env python3
"""
UserPromptSubmit: Generate a concise 4-word session name from the prompt.
Writes to memory/state/session-names.json.
"""
import json
import re
import sys
from paipy import read_stdin, allow, now_iso, memory

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "i", "you", "me", "my", "your", "we", "it", "this", "that", "can",
    "do", "does", "did", "will", "would", "could", "should", "please",
    "help", "make", "get", "let", "need", "want", "use", "how",
}


def make_name(prompt: str) -> str:
    # Strip punctuation, lowercase
    words = re.sub(r"[^\w\s]", " ", prompt.lower()).split()
    # Filter stop words, take first 4 meaningful words
    keywords = [w for w in words if w not in STOP_WORDS and len(w) > 2][:4]
    if not keywords:
        keywords = words[:4]
    return "-".join(keywords) if keywords else "unnamed-session"


def load_names() -> dict:
    p = memory("STATE") / "session-names.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {}


def save_names(names: dict):
    p = memory("STATE")
    p.mkdir(parents=True, exist_ok=True)
    (p / "session-names.json").write_text(json.dumps(names, indent=2))


def main():
    data = read_stdin()
    session_id = data.get("session_id", "")
    prompt = data.get("prompt", "")

    if not session_id or not prompt:
        allow()
        return

    names = load_names()

    # Only name once per session
    if session_id not in names:
        name = make_name(prompt)
        names[session_id] = {
            "name": name,
            "created_at": now_iso(),
            "prompt_snippet": prompt[:100],
        }
        save_names(names)

    allow()


if __name__ == "__main__":
    main()
