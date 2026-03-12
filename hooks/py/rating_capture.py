#!/usr/bin/env python3
"""
UserPromptSubmit: Capture explicit ratings (1-10) from user prompts.
Writes to memory/learning/SIGNALS/ratings.jsonl.
"""
import json
import re
import sys
from pathlib import Path

from paipy import read_stdin, allow, memory, data_dir, now_iso, now_filename, now_ym, now_date

RATING_PATTERN = re.compile(
    r"(?:^|\s)(?:rating[:\s]+)?([1-9]|10)(?:/10)?(?:\s|$|[,.])",
    re.IGNORECASE,
)

LOW_RATING_THRESHOLD = 4


def extract_rating(prompt: str) -> int | None:
    m = RATING_PATTERN.search(prompt)
    if m:
        return int(m.group(1))
    return None


def last_response() -> str:
    p = memory("STATE") / "last-response.txt"
    return p.read_text() if p.exists() else ""


def write_low_rating_learning(rating: int, prompt: str, response_snippet: str):
    d = memory("LEARNING") / "SIGNALS" / now_ym()
    d.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": now_iso(),
        "date": now_date(),
        "rating": rating,
        "prompt_snippet": prompt[:300],
        "response_snippet": response_snippet[:500],
        "type": "low_rating",
    }
    fn = d / f"{now_filename()}_low_rating_{rating}.json"
    fn.write_text(json.dumps(entry, indent=2))


def main():
    data = read_stdin()
    prompt = data.get("prompt", "")

    rating = extract_rating(prompt)
    if rating is not None:
        signals_dir = memory("LEARNING") / "SIGNALS"
        signals_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": now_iso(),
            "date": now_date(),
            "session_id": data.get("session_id", ""),
            "rating": rating,
            "prompt_snippet": prompt[:200],
        }
        with open(signals_dir / "ratings.jsonl", "a") as f:
            f.write(json.dumps(entry) + "\n")

        if rating <= LOW_RATING_THRESHOLD:
            response = last_response()
            write_low_rating_learning(rating, prompt, response)

    allow()


if __name__ == "__main__":
    main()
