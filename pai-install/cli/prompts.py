"""
PAI Installer v4.0 -- CLI Interactive Prompts
asyncio-compatible input collection.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Dict, List, Optional

from cli.display import c, print_text


async def prompt_text(
    question: str,
    default_value: Optional[str] = None,
) -> str:
    """Prompt for text input with optional default value."""
    default_hint = f" {c['gray']}({default_value}){c['reset']}" if default_value else ""
    sys.stdout.write(f"  {question}{default_hint}\n  {c['blue']}>{c['reset']} ")
    sys.stdout.flush()

    loop = asyncio.get_event_loop()
    answer = await loop.run_in_executor(None, sys.stdin.readline)
    answer = answer.strip()
    return answer or default_value or ""


async def prompt_secret(
    question: str,
    placeholder: Optional[str] = None,
) -> str:
    """Prompt for a password/key (input visible -- paste your key)."""
    hint = f" {c['gray']}({placeholder}){c['reset']}" if placeholder else ""
    print_text(f"  {question}{hint}")
    print_text(f"  {c['dim']}(Input will be visible -- paste your key){c['reset']}")
    sys.stdout.write(f"  {c['blue']}>{c['reset']} ")
    sys.stdout.flush()

    loop = asyncio.get_event_loop()
    answer = await loop.run_in_executor(None, sys.stdin.readline)
    return answer.strip()


async def prompt_choice(
    question: str,
    choices: List[Dict[str, str]],
) -> str:
    """Prompt for a choice from a list."""
    print_text(f"  {question}")
    print_text("")

    for i, choice in enumerate(choices):
        desc = f" {c['gray']}-- {choice.get('description', '')}{c['reset']}" if choice.get("description") else ""
        print_text(f"    {c['blue']}{i + 1}{c['reset']}) {choice['label']}{desc}")

    print_text("")
    sys.stdout.write(f"  {c['blue']}>{c['reset']} ")
    sys.stdout.flush()

    loop = asyncio.get_event_loop()
    answer = await loop.run_in_executor(None, sys.stdin.readline)
    answer = answer.strip()

    try:
        idx = int(answer) - 1
        if 0 <= idx < len(choices):
            return choices[idx]["value"]
    except (ValueError, IndexError):
        pass

    # Default to first choice
    return choices[0]["value"]


async def prompt_confirm(
    question: str,
    default_yes: bool = True,
) -> bool:
    """Prompt for yes/no confirmation."""
    hint = f"{c['gray']}(Y/n){c['reset']}" if default_yes else f"{c['gray']}(y/N){c['reset']}"
    sys.stdout.write(f"  {question} {hint} ")
    sys.stdout.flush()

    loop = asyncio.get_event_loop()
    answer = await loop.run_in_executor(None, sys.stdin.readline)
    val = answer.strip().lower()

    if val == "":
        return default_yes
    return val in ("y", "yes")
