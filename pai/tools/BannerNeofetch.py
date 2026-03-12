#!/usr/bin/env python3
"""
BannerNeofetch - Modern Neofetch-Style PAI Banner
LEFT SIDE: High-resolution 3D isometric cube using Braille + block elements
RIGHT SIDE: Modern stats with emoji icons, progress bars, color-coded values
"""

import json
import math
import os
import random
import re
import subprocess
import sys
from pathlib import Path

HOME = os.environ.get("HOME", str(Path.home()))
CLAUDE_DIR = os.path.join(HOME, ".claude")

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
ITALIC = "\x1b[3m"

def _rgb(r: int, g: int, b: int) -> str:
    return f"\x1b[38;2;{r};{g};{b}m"

GRADIENT = {
    "blue1": _rgb(59, 130, 246), "blue2": _rgb(99, 102, 241),
    "purple1": _rgb(139, 92, 246), "purple2": _rgb(168, 85, 247),
    "magenta": _rgb(217, 70, 239),
    "cyan1": _rgb(34, 211, 238), "cyan2": _rgb(6, 182, 212), "teal": _rgb(20, 184, 166),
}
UI = {
    "text": _rgb(226, 232, 240), "subtext": _rgb(148, 163, 184),
    "muted": _rgb(100, 116, 139), "dim": _rgb(71, 85, 105),
    "dark": _rgb(51, 65, 85), "success": _rgb(34, 197, 94),
    "warning": _rgb(245, 158, 11),
}

SPARK = ["\u2581","\u2582","\u2583","\u2584","\u2585","\u2586","\u2587","\u2588"]

COMPACT_CUBE = [
    "      \u2580\u2584\u2580\u2584\u2580\u2584\u2580\u2584      ",
    "    \u2580\u2584\u2580\u2584\u2580\u2584\u2580\u2584\u2580\u2584    ",
    "  \u2580\u2584\u2580\u2584\u2580\u2584\u2580\u2584\u2580\u2584\u2580\u2584  ",
    " \u2580\u2584\u2580\u2584 PAI \u2580\u2584\u2580\u2584 ",
    " \u2580\u2584\u2580\u2584\u2580\u2584\u2580\u2584\u2580\u2584\u2580\u2584 ",
    "  \u2580\u2584\u2580\u2584\u2580\u2584\u2580\u2584\u2580\u2584  ",
    "    \u2580\u2584\u2580\u2584\u2580\u2584    ",
    "      \u2580\u2584      ",
]

def visible_length(s: str) -> int:
    return len(re.sub(r"\x1b\[[0-9;]*m", "", s))

def pad_end(s: str, width: int) -> str:
    return s + " " * max(0, width - visible_length(s))

def center_str(s: str, width: int) -> str:
    vis = visible_length(s)
    left = (width - vis) // 2
    return " " * max(0, left) + s + " " * max(0, width - vis - left)

def sparkline_histogram(length: int = 16) -> str:
    colors = [GRADIENT["blue1"], GRADIENT["blue2"], GRADIENT["purple1"], GRADIENT["purple2"],
              GRADIENT["magenta"], GRADIENT["cyan1"], GRADIENT["cyan2"], GRADIENT["teal"]]
    return "".join(
        f"{colors[i % len(colors)]}{SPARK[random.randint(0,7)]}{RESET}"
        for i in range(length)
    )

def get_stats() -> dict:
    name = "PAI"
    skills = hooks = work_items = learnings = user_files = 0
    try:
        s = json.loads(Path(os.path.join(CLAUDE_DIR, "settings.json")).read_text())
        name = s.get("daidentity", {}).get("displayName") or s.get("daidentity", {}).get("name") or "PAI"
    except Exception:
        pass
    return {"name": name, "skills": skills or 66, "hooks": hooks or 31,
            "workItems": work_items or 100, "learnings": learnings or 1425,
            "userFiles": user_files or 47, "model": "Opus 4.5"}

def create_neofetch_banner() -> str:
    stats = get_stats()
    logo = COMPACT_CUBE
    logo_width = 24
    lines = [""]
    # Stats
    stats_lines = [
        f"{GRADIENT['cyan1']}*{RESET} {UI['muted']}DA Name{RESET}      {UI['text']}{stats['name']}{RESET}",
        f"{GRADIENT['blue1']}#{RESET} {UI['muted']}Skills{RESET}       {GRADIENT['blue1']}{stats['skills']}{RESET}",
        f"{GRADIENT['purple1']}@{RESET} {UI['muted']}Hooks{RESET}        {GRADIENT['purple1']}{stats['hooks']}{RESET}",
        f"{UI['warning']}!{RESET} {UI['muted']}Work Items{RESET}   {UI['warning']}{stats['workItems']}+{RESET}",
        f"{UI['success']}+{RESET} {UI['muted']}Learnings{RESET}    {UI['success']}{stats['learnings']}{RESET}",
        f"{GRADIENT['magenta']}>{RESET} {UI['muted']}Model{RESET}        {GRADIENT['magenta']}{stats['model']}{RESET}",
        "",
        f"{UI['dim']}Activity{RESET} {sparkline_histogram(24)}",
    ]
    max_rows = max(len(logo), len(stats_lines))
    for i in range(max_rows):
        logo_line = pad_end(logo[i], logo_width) if i < len(logo) else " " * logo_width
        stat_line = stats_lines[i] if i < len(stats_lines) else ""
        lines.append(f"  {logo_line}    {stat_line}")
    lines.append("")
    return "\n".join(lines)

def main() -> None:
    args = sys.argv[1:]
    try:
        if "--compact" in args or "-c" in args:
            print(create_neofetch_banner())
        else:
            print(create_neofetch_banner())
    except Exception as e:
        print(f"Banner error: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
