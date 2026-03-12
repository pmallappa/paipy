#!/usr/bin/env python3
"""
NeofetchBanner - PAI System Banner in Neofetch Style

Layout:
  LEFT:   Isometric PAI cube logo (ASCII/Braille art)
  RIGHT:  System stats as key-value pairs
  BOTTOM: PAI header, quote, sentiment histogram, PAI name, GitHub URL

Aesthetic: Cyberpunk/hacker with Tokyo Night colors
  - Hex addresses (0x7A2F)
  - Binary streams
  - Targeting reticle elements
  - Neon glow feel
"""

import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path

HOME = os.environ.get("HOME", "")
CLAUDE_DIR = Path(HOME) / ".claude"

# ═══════════════════════════════════════════════════════════════════════
# Terminal Width Detection
# ═══════════════════════════════════════════════════════════════════════


def get_terminal_width() -> int:
    width = None

    # Tier 1: Kitty IPC
    kitty_window_id = os.environ.get("KITTY_WINDOW_ID")
    if kitty_window_id:
        try:
            result = subprocess.run(["kitten", "@", "ls"], capture_output=True, text=True)
            if result.stdout:
                data = json.loads(result.stdout)
                for os_window in data:
                    for tab in os_window.get("tabs", []):
                        for win in tab.get("windows", []):
                            if win.get("id") == int(kitty_window_id):
                                width = win.get("columns")
                                break
        except Exception:
            pass

    # Tier 2: Direct TTY query
    if not width or width <= 0:
        try:
            result = subprocess.run(
                ["sh", "-c", "stty size </dev/tty 2>/dev/null"],
                capture_output=True, text=True,
            )
            if result.stdout:
                cols = int(result.stdout.strip().split()[1])
                if cols > 0:
                    width = cols
        except Exception:
            pass

    # Tier 3: tput fallback
    if not width or width <= 0:
        try:
            result = subprocess.run(["tput", "cols"], capture_output=True, text=True)
            if result.stdout:
                cols = int(result.stdout.strip())
                if cols > 0:
                    width = cols
        except Exception:
            pass

    # Tier 4: Environment variable fallback
    if not width or width <= 0:
        width = int(os.environ.get("COLUMNS", "100")) or 100

    return width


def get_display_mode() -> str:
    width = get_terminal_width()
    if width < 80:
        return "compact"
    if width < 120:
        return "normal"
    return "wide"


# ═══════════════════════════════════════════════════════════════════════
# ANSI & Tokyo Night Color System
# ═══════════════════════════════════════════════════════════════════════

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
ITALIC = "\x1b[3m"


def rgb(r: int, g: int, b: int) -> str:
    return f"\x1b[38;2;{r};{g};{b}m"


def bg_rgb(r: int, g: int, b: int) -> str:
    return f"\x1b[48;2;{r};{g};{b}m"


COLORS = {
    "blue": rgb(122, 162, 247),
    "magenta": rgb(187, 154, 247),
    "cyan": rgb(125, 207, 255),
    "neonCyan": rgb(0, 255, 255),
    "neonPurple": rgb(180, 100, 255),
    "neonPink": rgb(255, 100, 200),
    "green": rgb(158, 206, 106),
    "orange": rgb(255, 158, 100),
    "red": rgb(247, 118, 142),
    "yellow": rgb(224, 175, 104),
    "frame": rgb(59, 66, 97),
    "text": rgb(169, 177, 214),
    "subtext": rgb(86, 95, 137),
    "bright": rgb(192, 202, 245),
    "dark": rgb(36, 40, 59),
    "teal": rgb(45, 130, 130),
}

# ═══════════════════════════════════════════════════════════════════════
# Unicode Elements
# ═══════════════════════════════════════════════════════════════════════

RETICLE = {
    "topLeft": "\u231C",
    "topRight": "\u231D",
    "bottomLeft": "\u231E",
    "bottomRight": "\u231F",
    "crosshair": "\u25CE",
    "target": "\u25C9",
}

BOX = {
    "horizontal": "\u2500",
    "vertical": "\u2502",
    "topLeft": "\u256D",
    "topRight": "\u256E",
    "bottomLeft": "\u2570",
    "bottomRight": "\u256F",
    "leftT": "\u251C",
    "rightT": "\u2524",
    "cross": "\u253C",
}

SPARK = ["\u2581", "\u2582", "\u2583", "\u2584", "\u2585", "\u2586", "\u2587", "\u2588"]

# ═══════════════════════════════════════════════════════════════════════
# PAI Cube Logo
# ═══════════════════════════════════════════════════════════════════════

PAI_CUBE_ASCII = [
    "         \u256D\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u256E",
    "        \u2571     P     \u2571\u2502",
    "       \u2571\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2571 \u2502",
    "      \u2571           \u2571  \u2502",
    "     \u256D\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u256E   \u2502",
    "     \u2502     A     \u2502   I",
    "     \u2502           \u2502  \u2571",
    "     \u2502           \u2502 \u2571",
    "     \u2570\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u256F\u2571",
]

# PAI Block Letters (5 rows)
LETTERS = {
    "P": [
        "\u2588\u2588\u2588\u2588\u2588\u2588\u2557 ",
        "\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557",
        "\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255D",
        "\u2588\u2588\u2554\u2550\u2550\u2550\u255D ",
        "\u2588\u2588\u2551    ",
    ],
    "A": [
        " \u2588\u2588\u2588\u2588\u2588\u2557 ",
        "\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557",
        "\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2551",
        "\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2551",
        "\u2588\u2588\u2551  \u2588\u2588\u2551",
    ],
    "I": [
        "\u2588\u2588\u2557",
        "\u2588\u2588\u2551",
        "\u2588\u2588\u2551",
        "\u2588\u2588\u2551",
        "\u2588\u2588\u2551",
    ],
    " ": ["   ", "   ", "   ", "   ", "   "],
}


# ═══════════════════════════════════════════════════════════════════════
# Dynamic Stats Collection
# ═══════════════════════════════════════════════════════════════════════


def read_da_identity() -> str:
    settings_path = CLAUDE_DIR / "settings.json"
    try:
        settings = json.loads(settings_path.read_text())
        return (
            settings.get("daidentity", {}).get("displayName")
            or settings.get("daidentity", {}).get("name")
            or settings.get("env", {}).get("DA")
            or "PAI"
        )
    except Exception:
        return "PAI"


def count_skills() -> int:
    skills_dir = CLAUDE_DIR / "skills"
    if not skills_dir.exists():
        return 0
    count = 0
    try:
        for entry in skills_dir.iterdir():
            if entry.is_dir() and (entry / "SKILL.md").exists():
                count += 1
    except Exception:
        pass
    return count


def count_hooks() -> int:
    hooks_dir = CLAUDE_DIR / "hooks"
    if not hooks_dir.exists():
        return 0
    count = 0
    try:
        for entry in hooks_dir.iterdir():
            if entry.is_file() and entry.name.endswith(".ts"):
                count += 1
    except Exception:
        pass
    return count


def count_work_items() -> str:
    work_dir = CLAUDE_DIR / "MEMORY" / "WORK"
    if not work_dir.exists():
        return "0"
    count = 0
    try:
        for entry in work_dir.iterdir():
            if entry.is_dir():
                count += 1
    except Exception:
        pass
    return "100+" if count > 100 else str(count)


def count_learnings() -> int:
    learnings_dir = CLAUDE_DIR / "MEMORY" / "LEARNING"
    if not learnings_dir.exists():
        return 0
    count = 0

    def count_recursive(d: Path) -> None:
        nonlocal count
        try:
            for entry in d.iterdir():
                if entry.is_dir():
                    count_recursive(entry)
                elif entry.is_file() and entry.name.endswith(".md"):
                    count += 1
        except Exception:
            pass

    count_recursive(learnings_dir)
    return count


def count_user_files() -> int:
    user_dir = CLAUDE_DIR / "PAI" / "USER"
    if not user_dir.exists():
        return 0
    count = 0

    def count_recursive(d: Path) -> None:
        nonlocal count
        try:
            for entry in d.iterdir():
                if entry.is_dir():
                    count_recursive(entry)
                elif entry.is_file():
                    count += 1
        except Exception:
            pass

    count_recursive(user_dir)
    return count


def get_stats() -> dict[str, str | int]:
    return {
        "DA_NAME": read_da_identity(),
        "skills": count_skills(),
        "hooks": count_hooks(),
        "workItems": count_work_items(),
        "learnings": count_learnings(),
        "userFiles": count_user_files(),
        "model": "Opus 4.5",
    }


# ═══════════════════════════════════════════════════════════════════════
# Utility Functions
# ═══════════════════════════════════════════════════════════════════════


def random_hex(length: int = 4) -> str:
    return "".join(f"{random.randint(0, 15):X}" for _ in range(length))


def generate_sentiment_histogram() -> str:
    weights = [1, 2, 3, 4, 6, 8, 10, 8]
    total_weight = sum(weights)
    result = ""
    for _ in range(16):
        rand = random.random() * total_weight
        idx = 0
        for j, w in enumerate(weights):
            rand -= w
            if rand <= 0:
                idx = j
                break
        result += SPARK[idx]
    return result


def generate_binary(length: int = 8) -> str:
    return "".join(str(random.randint(0, 1)) for _ in range(length))


def strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


def visible_length(s: str) -> int:
    return len(strip_ansi(s))


def pad_right(s: str, length: int) -> str:
    visible = visible_length(s)
    return s + " " * max(0, length - visible)


def center_str(s: str, width: int) -> str:
    visible = visible_length(s)
    left_pad = (width - visible) // 2
    right_pad = width - visible - left_pad
    return " " * max(0, left_pad) + s + " " * max(0, right_pad)


# ═══════════════════════════════════════════════════════════════════════
# Generate PAI ASCII Art
# ═══════════════════════════════════════════════════════════════════════


def generate_pai_art() -> list[str]:
    name = "PAI"
    letter_colors = [COLORS["blue"], COLORS["magenta"], COLORS["cyan"]]
    rows = ["", "", "", "", ""]

    for char_idx, char in enumerate(name):
        letter_art = LETTERS.get(char, LETTERS[" "])
        color = letter_colors[char_idx % len(letter_colors)]
        for row in range(5):
            rows[row] += f"{BOLD}{color}{letter_art[row]}{RESET} "

    return [r.rstrip() for r in rows]


# ═══════════════════════════════════════════════════════════════════════
# PAI Cube Logo with Gradient Coloring
# ═══════════════════════════════════════════════════════════════════════


def color_logo(lines: list[str]) -> list[str]:
    b = COLORS["blue"]
    nc = COLORS["neonCyan"]
    np = COLORS["neonPurple"]
    c = COLORS["cyan"]
    m = COLORS["magenta"]
    f = COLORS["frame"]

    result = []
    for line in lines:
        colored = line
        colored = colored.replace("P", f"{RESET}{BOLD}{nc}P{RESET}{b}", 1)
        colored = colored.replace("A", f"{RESET}{BOLD}{np}A{RESET}{c}", 1)
        colored = colored.replace("I", f"{RESET}{BOLD}{c}I{RESET}{m}", 1)
        result.append(f"{f}{colored}{RESET}")
    return result


# ═══════════════════════════════════════════════════════════════════════
# Main Banner Generator
# ═══════════════════════════════════════════════════════════════════════


def create_neofetch_banner() -> str:
    width = get_terminal_width()
    stats = get_stats()

    f = COLORS["frame"]
    s = COLORS["subtext"]
    t = COLORS["text"]
    b = COLORS["blue"]
    m = COLORS["magenta"]
    c = COLORS["cyan"]
    g = COLORS["green"]
    o = COLORS["orange"]
    nc = COLORS["neonCyan"]
    np = COLORS["neonPurple"]
    tl = COLORS["teal"]

    lines: list[str] = []

    hex1, hex2, hex3, hex4 = random_hex(), random_hex(), random_hex(), random_hex()
    binary1, binary2 = generate_binary(), generate_binary()

    # TOP BORDER
    top_border = f"{f}{RETICLE['topLeft']}{RESET} {s}0x{hex1}{RESET} {f}{BOX['horizontal'] * (width - 24)}{RESET} {s}0x{hex2}{RESET} {f}{RETICLE['topRight']}{RESET}"
    lines.append(top_border)
    lines.append("")

    # LEFT: Logo | RIGHT: Stats
    logo = color_logo(PAI_CUBE_ASCII)
    logo_width = 26
    stats_gap = 2

    stat_items = [
        {"key": "DA Name", "value": str(stats["DA_NAME"]), "color": nc},
        {"key": "Skills", "value": str(stats["skills"]), "color": g},
        {"key": "Hooks", "value": str(stats["hooks"]), "color": c},
        {"key": "Work Items", "value": str(stats["workItems"]), "color": o},
        {"key": "Learnings", "value": str(stats["learnings"]), "color": m},
        {"key": "User Files", "value": str(stats["userFiles"]), "color": b},
        {"key": "Model", "value": str(stats["model"]), "color": np},
    ]

    max_stat_rows = max(len(logo), len(stat_items))
    logo_offset = (max_stat_rows - len(logo)) // 2
    stats_offset = (max_stat_rows - len(stat_items)) // 2

    for i in range(max_stat_rows):
        logo_idx = i - logo_offset
        stats_idx = i - stats_offset

        logo_line = " " * logo_width
        if 0 <= logo_idx < len(logo):
            logo_line = pad_right(logo[logo_idx], logo_width)

        stats_line = ""
        if 0 <= stats_idx < len(stat_items):
            stat = stat_items[stats_idx]
            stats_line = f"{s}{stat['key']}:{RESET} {BOLD}{stat['color']}{stat['value']}{RESET}"

        lines.append(f"  {logo_line}{' ' * stats_gap}{stats_line}")

    lines.append("")

    # DIVIDER
    divider_width = min(width - 4, 80)
    divider_pad = (width - divider_width) // 2
    divider_half = (divider_width - 16) // 2
    divider = f"{' ' * divider_pad}{s}{binary1}{RESET}{f}{BOX['horizontal'] * divider_half}{c}{BOX['cross']}{RESET}{f}{BOX['horizontal'] * divider_half}{RESET}{s}{binary2}{RESET}"
    lines.append(divider)
    lines.append("")

    # BOTTOM SECTION
    pai_header = f"{BOLD}{nc}P{RESET}{BOLD}{np}A{RESET}{BOLD}{c}I{RESET} {f}|{RESET} {t}Personal AI Infrastructure{RESET}"
    lines.append(center_str(pai_header, width))
    lines.append("")

    quote = f'{s}"Magnifying human capabilities..."{RESET}'
    lines.append(center_str(quote, width))
    lines.append("")

    histogram = generate_sentiment_histogram()
    histogram_line = f"{s}Sentiment:{RESET} {o}{histogram}{RESET}"
    lines.append(center_str(histogram_line, width))
    lines.append("")

    pai_art = generate_pai_art()
    for row in pai_art:
        lines.append(center_str(row, width))
    lines.append("")

    github_url = f"{f}{RETICLE['topLeft']}{RESET} {tl}github.com/danielmiessler/PAI{RESET} {f}{RETICLE['topRight']}{RESET}"
    lines.append(center_str(github_url, width))

    # BOTTOM BORDER
    lines.append("")
    bottom_border = f"{f}{RETICLE['bottomLeft']}{RESET} {s}0x{hex3}{RESET} {f}{BOX['horizontal'] * (width - 24)}{RESET} {s}0x{hex4}{RESET} {f}{RETICLE['bottomRight']}{RESET}"
    lines.append(bottom_border)

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# Compact Banner for Narrow Terminals
# ═══════════════════════════════════════════════════════════════════════


def create_compact_banner() -> str:
    stats = get_stats()
    f = COLORS["frame"]
    s = COLORS["subtext"]
    c = COLORS["cyan"]
    m = COLORS["magenta"]
    b = COLORS["blue"]
    g = COLORS["green"]
    nc = COLORS["neonCyan"]

    hex_val = random_hex()
    spark = generate_sentiment_histogram()[:8]

    lines = [
        f"{f}{RETICLE['topLeft']}{s}0x{hex_val}{f}{RETICLE['topRight']}{RESET}",
        f"{nc}{RETICLE['crosshair']}{RESET} {BOLD}{b}P{m}A{c}I{RESET} {g}{RETICLE['target']}{RESET}",
        f"{s}Skills:{g}{stats['skills']}{RESET} {s}Hooks:{c}{stats['hooks']}{RESET}",
        f"{s}{spark}{RESET}",
        f"{f}{RETICLE['bottomLeft']}{s}PAI{f}{RETICLE['bottomRight']}{RESET}",
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════════


def main() -> None:
    args = sys.argv[1:]
    mode = get_display_mode()

    test_mode = "--test" in args
    compact_mode = "--compact" in args or mode == "compact"

    try:
        if test_mode:
            print("\n=== COMPACT MODE ===\n")
            print(create_compact_banner())
            print("\n=== NORMAL MODE ===\n")
            print(create_neofetch_banner())
        elif compact_mode:
            print(create_compact_banner())
        else:
            print()
            print(create_neofetch_banner())
            print()
    except Exception as e:
        print(f"Banner error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
