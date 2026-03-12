#!/usr/bin/env python3
"""
PAI Banner - Dynamic Multi-Design Neofetch Banner
Randomly selects from curated designs based on terminal size

Large terminals (85+ cols): Navy, Electric, Teal, Ice themes
Small terminals (<85 cols): Minimal, Vertical, Wrapping layouts
"""

import json
import math
import os
import random
import subprocess
import sys
from pathlib import Path

HOME = os.environ.get("HOME", str(Path.home()))
CLAUDE_DIR = os.path.join(HOME, ".claude")

# ANSI Helpers
RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
ITALIC = "\x1b[3m"


def rgb(r: int, g: int, b: int) -> str:
    return f"\x1b[38;2;{r};{g};{b}m"


# Sparkline characters
SPARK = ["\u2581", "\u2582", "\u2583", "\u2584", "\u2585", "\u2586", "\u2587", "\u2588"]

# Box drawing
BOX = {"tl": "\u256d", "tr": "\u256e", "bl": "\u2570", "br": "\u256f",
       "h": "\u2500", "v": "\u2502", "dh": "\u2550"}


def get_terminal_width() -> int:
    width = None
    kitty_wid = os.environ.get("KITTY_WINDOW_ID")
    if kitty_wid:
        try:
            result = subprocess.run(["kitten", "@", "ls"], capture_output=True, text=True)
            if result.stdout:
                data = json.loads(result.stdout)
                for os_window in data:
                    for tab in os_window.get("tabs", []):
                        for win in tab.get("windows", []):
                            if win.get("id") == int(kitty_wid):
                                width = win.get("columns")
        except Exception:
            pass

    if not width or width <= 0:
        try:
            result = subprocess.run(["sh", "-c", "stty size </dev/tty 2>/dev/null"],
                                    capture_output=True, text=True)
            if result.stdout:
                cols = int(result.stdout.strip().split()[1])
                if cols > 0:
                    width = cols
        except Exception:
            pass

    if not width or width <= 0:
        try:
            result = subprocess.run(["tput", "cols"], capture_output=True, text=True)
            if result.stdout:
                cols = int(result.stdout.strip())
                if cols > 0:
                    width = cols
        except Exception:
            pass

    if not width or width <= 0:
        width = int(os.environ.get("COLUMNS", "100")) or 100

    return width


def get_stats() -> dict:
    name = "PAI"
    pai_version = "4.0.0"
    algorithm_version = "0.2"
    catchphrase = "{name} here, ready to go"
    repo_url = "github.com/danielmiessler/PAI"

    settings_path = os.path.join(CLAUDE_DIR, "settings.json")
    skills = 0
    workflows = 0
    hooks = 0
    learnings = 0
    user_files = 0
    sessions = 0

    try:
        settings = json.loads(Path(settings_path).read_text())
        name = (settings.get("daidentity", {}).get("displayName")
                or settings.get("daidentity", {}).get("name") or "PAI")
        pai_version = settings.get("pai", {}).get("version", "2.0")
        av = settings.get("pai", {}).get("algorithmVersion", algorithm_version)
        algorithm_version = av.lstrip("vV") if isinstance(av, str) else str(av)
        catchphrase = settings.get("daidentity", {}).get("startupCatchphrase", catchphrase)
        repo_url = settings.get("pai", {}).get("repoUrl", repo_url)
        counts = settings.get("counts", {})
        skills = counts.get("skills", 0)
        workflows = counts.get("workflows", 0)
        hooks = counts.get("hooks", 0)
        learnings = counts.get("signals", 0)
        user_files = counts.get("files", 0)
    except Exception:
        skills = 65
        workflows = 339
        hooks = 18
        learnings = 3000
        user_files = 172

    catchphrase = catchphrase.replace("{name}", name).replace("{Name}", name)

    try:
        history_file = os.path.join(CLAUDE_DIR, "history.jsonl")
        if os.path.exists(history_file):
            content = Path(history_file).read_text()
            sessions = len([l for l in content.splitlines() if l.strip()])
    except Exception:
        pass

    platform = "macOS" if sys.platform == "darwin" else sys.platform
    arch = os.uname().machine

    cc_version = "2.0"
    try:
        result = subprocess.run(["claude", "--version"], capture_output=True, text=True)
        if result.stdout:
            import re
            match = re.search(r"(\d+\.\d+\.\d+)", result.stdout)
            if match:
                cc_version = match.group(1)
    except Exception:
        pass

    return {
        "name": name, "catchphrase": catchphrase, "repoUrl": repo_url,
        "skills": skills, "workflows": workflows, "hooks": hooks,
        "learnings": learnings, "userFiles": user_files, "sessions": sessions,
        "model": "Opus 4.5", "platform": platform, "arch": arch,
        "ccVersion": cc_version, "paiVersion": pai_version,
        "algorithmVersion": algorithm_version,
    }


def visible_length(s: str) -> int:
    import re
    return len(re.sub(r"\x1b\[[0-9;]*m", "", s))


def pad_end(s: str, width: int) -> str:
    return s + " " * max(0, width - visible_length(s))


def pad_start(s: str, width: int) -> str:
    return " " * max(0, width - visible_length(s)) + s


def center(s: str, width: int) -> str:
    vis = visible_length(s)
    left = (width - vis) // 2
    return " " * max(0, left) + s + " " * max(0, width - vis - left)


def random_hex(length: int = 4) -> str:
    return "".join(f"{random.randint(0, 15):X}" for _ in range(length))


def sparkline(length: int, colors: list[str] | None = None) -> str:
    result = ""
    for i in range(length):
        level = random.randint(0, 7)
        color = colors[i % len(colors)] if colors else ""
        result += f"{color}{SPARK[level]}{RESET}"
    return result


def create_navy_banner(stats: dict, width: int) -> str:
    C = {
        "navy": rgb(30, 58, 138), "medBlue": rgb(59, 130, 246),
        "lightBlue": rgb(147, 197, 253), "steel": rgb(51, 65, 85),
        "slate": rgb(100, 116, 139), "silver": rgb(203, 213, 225),
        "white": rgb(240, 240, 255), "muted": rgb(71, 85, 105),
        "deepNavy": rgb(30, 41, 82), "royalBlue": rgb(65, 105, 225),
        "skyBlue": rgb(135, 206, 235), "iceBlue": rgb(176, 196, 222),
        "periwinkle": rgb(140, 160, 220), "darkTeal": rgb(55, 100, 105),
    }
    B = "\u2588"
    logo = [
        f"{C['navy']}{B*16}{RESET}{C['lightBlue']}{B*4}{RESET}",
        f"{C['navy']}{B*16}{RESET}{C['lightBlue']}{B*4}{RESET}",
        f"{C['navy']}{B*4}{RESET}        {C['navy']}{B*4}{RESET}{C['lightBlue']}{B*4}{RESET}",
        f"{C['navy']}{B*4}{RESET}        {C['navy']}{B*4}{RESET}{C['lightBlue']}{B*4}{RESET}",
        f"{C['navy']}{B*16}{RESET}{C['lightBlue']}{B*4}{RESET}",
        f"{C['navy']}{B*16}{RESET}{C['lightBlue']}{B*4}{RESET}",
        f"{C['navy']}{B*4}{RESET}        {C['medBlue']}{B*4}{RESET}{C['lightBlue']}{B*4}{RESET}",
        f"{C['navy']}{B*4}{RESET}        {C['medBlue']}{B*4}{RESET}{C['lightBlue']}{B*4}{RESET}",
        f"{C['navy']}{B*4}{RESET}        {C['medBlue']}{B*4}{RESET}{C['lightBlue']}{B*4}{RESET}",
        f"{C['navy']}{B*4}{RESET}        {C['medBlue']}{B*4}{RESET}{C['lightBlue']}{B*4}{RESET}",
    ]
    LOGO_WIDTH = 20
    SEPARATOR = f"{C['steel']}{BOX['v']}{RESET}"

    info_lines = [
        f"{C['slate']}\"{RESET}{C['lightBlue']}{stats['catchphrase']}{RESET}{C['slate']}...\"{RESET}",
        f"{C['steel']}{BOX['h']*24}{RESET}",
        f"{C['navy']}\u2B22{RESET}  {C['slate']}PAI{RESET}       {C['silver']}{stats['paiVersion']}{RESET}",
        f"{C['navy']}\u2699{RESET}  {C['slate']}Algo{RESET}      {C['silver']}{stats['algorithmVersion']}{RESET}",
        f"{C['lightBlue']}\u2726{RESET}  {C['slate']}SK{RESET}        {C['silver']}{stats['skills']}{RESET}",
        f"{C['skyBlue']}\u21BB{RESET}  {C['slate']}WF{RESET}        {C['iceBlue']}{stats['workflows']}{RESET}",
        f"{C['royalBlue']}\u21AA{RESET}  {C['slate']}Hooks{RESET}     {C['periwinkle']}{stats['hooks']}{RESET}",
        f"{C['medBlue']}\u2726{RESET}  {C['slate']}Signals{RESET}   {C['skyBlue']}{stats['learnings']}{RESET}",
        f"{C['navy']}\u2261{RESET}  {C['slate']}Files{RESET}     {C['lightBlue']}{stats['userFiles']}{RESET}",
        f"{C['steel']}{BOX['h']*24}{RESET}",
    ]

    gap = "   "
    gap_after = "  "
    total_content_width = LOGO_WIDTH + len(gap) + 1 + len(gap_after) + 28
    left_pad = (width - total_content_width) // 2
    pad = " " * max(2, left_pad)
    empty_logo = " " * LOGO_WIDTH
    logo_top_pad = math.ceil((len(info_lines) - len(logo)) / 2)

    RETICLE = {"tl": "\u250F", "tr": "\u2513", "bl": "\u2517", "br": "\u251B", "h": "\u2501"}
    frame_width = 70
    frame_pad = " " * ((width - frame_width) // 2)

    lines = [""]
    top_border = f"{C['steel']}{RETICLE['tl']}{RETICLE['h']*(frame_width-2)}{RETICLE['tr']}{RESET}"
    lines.append(f"{frame_pad}{top_border}")
    lines.append("")

    pai_colored = f"{C['navy']}P{RESET}{C['medBlue']}A{RESET}{C['lightBlue']}I{RESET}"
    header_text = f"{pai_colored} {C['steel']}|{RESET} {C['slate']}Personal AI Infrastructure{RESET}"
    header_pad = " " * ((width - 33) // 2)
    lines.append(f"{header_pad}{header_text}")
    lines.append("")

    quote = f"{ITALIC}{C['lightBlue']}\"Magnifying human capabilities...\"{RESET}"
    quote_pad = " " * ((width - 35) // 2)
    lines.append(f"{quote_pad}{quote}")
    lines.append("")
    lines.append("")

    for i in range(len(info_lines)):
        logo_index = i - logo_top_pad
        logo_row = logo[logo_index] if 0 <= logo_index < len(logo) else empty_logo
        info_row = info_lines[i]
        lines.append(f"{pad}{pad_end(logo_row, LOGO_WIDTH)}{gap}{SEPARATOR}{gap_after}{info_row}")

    lines.append("")
    lines.append("")

    url_line = f"{C['steel']}\u2192{RESET} {C['medBlue']}{stats['repoUrl']}{RESET}"
    url_pad = " " * ((width - len(stats["repoUrl"]) - 3) // 2)
    lines.append(f"{url_pad}{url_line}")
    lines.append("")

    bottom_border = f"{C['steel']}{RETICLE['bl']}{RETICLE['h']*(frame_width-2)}{RETICLE['br']}{RESET}"
    lines.append(f"{frame_pad}{bottom_border}")
    lines.append("")

    return "\n".join(lines)


# Responsive Navy variants (simplified for brevity -- same logic as TS)

def get_navy_colors() -> dict:
    return {
        "navy": rgb(30, 58, 138), "medBlue": rgb(59, 130, 246),
        "lightBlue": rgb(147, 197, 253), "steel": rgb(51, 65, 85),
        "slate": rgb(100, 116, 139), "silver": rgb(203, 213, 225),
        "iceBlue": rgb(176, 196, 222), "periwinkle": rgb(140, 160, 220),
        "skyBlue": rgb(135, 206, 235), "royalBlue": rgb(65, 105, 225),
    }


def create_navy_ultra_compact_banner(stats: dict, width: int) -> str:
    C = get_navy_colors()
    pai_colored = f"{C['navy']}P{RESET}{C['medBlue']}A{RESET}{C['lightBlue']}I{RESET}"
    lines = [""]
    lines.append(center(pai_colored, width))
    lines.append(center(
        f"{C['lightBlue']}{stats['name']}{RESET}{C['slate']}@pai {stats['paiVersion']}{RESET} "
        f"{C['navy']}\u2699{RESET}{C['silver']}{stats['algorithmVersion']}{RESET}", width))
    bar_w = min(20, width - 4)
    lines.append(center(f"{C['steel']}{BOX['h']*bar_w}{RESET}", width))
    lines.append(center(
        f"{C['lightBlue']}\u2726{RESET}{C['silver']}{stats['skills']}{RESET} "
        f"{C['skyBlue']}\u21BB{RESET}{C['iceBlue']}{stats['workflows']}{RESET} "
        f"{C['royalBlue']}\u21AA{RESET}{C['periwinkle']}{stats['hooks']}{RESET}", width))
    lines.append("")
    return "\n".join(lines)


BREAKPOINTS = {"FULL": 85, "MEDIUM": 70, "COMPACT": 55, "MINIMAL": 45}


def create_banner(force_design: str | None = None) -> str:
    width = get_terminal_width()
    stats = get_stats()

    if force_design:
        if force_design == "navy":
            return create_navy_banner(stats, width)
        elif force_design == "navy-ultra":
            return create_navy_ultra_compact_banner(stats, width)
        # Other designs use navy as fallback
        return create_navy_banner(stats, width)

    if width >= BREAKPOINTS["FULL"]:
        return create_navy_banner(stats, width)
    else:
        return create_navy_ultra_compact_banner(stats, width)


def main() -> None:
    args = sys.argv[1:]
    test_mode = "--test" in args
    design_arg = None
    for a in args:
        if a.startswith("--design="):
            design_arg = a.split("=")[1]

    try:
        if test_mode:
            for design in ["navy", "navy-ultra"]:
                print(f"\n{'=' * 60}")
                print(f"  DESIGN: {design.upper()}")
                print(f"{'=' * 60}")
                print(create_banner(design))
        else:
            print(create_banner(design_arg))
    except Exception as e:
        print(f"Banner error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
