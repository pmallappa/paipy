#!/usr/bin/env python3
"""
BannerRetro - Retro BBS/DOS Terminal Banner for PAI
Neofetch-style layout with classic ASCII art aesthetic
"""

import json
import os
import subprocess
import sys
from pathlib import Path

HOME = os.environ.get("HOME", str(Path.home()))
CLAUDE_DIR = os.path.join(HOME, ".claude")

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
BLINK = "\x1b[5m"

def rgb(r: int, g: int, b: int) -> str:
    return f"\x1b[38;2;{r};{g};{b}m"

COLORS = {
    "greenBright": rgb(51, 255, 51), "greenNormal": rgb(0, 200, 0),
    "greenDim": rgb(0, 128, 0), "amberBright": rgb(255, 191, 0),
    "amberNormal": rgb(255, 140, 0), "amberDim": rgb(180, 100, 0),
    "frame": rgb(0, 140, 0), "highlight": rgb(100, 255, 100),
    "cyan": rgb(0, 255, 255), "blue": rgb(100, 150, 255), "purple": rgb(200, 100, 255),
}

BOX_D = {"tl": "\u2554", "tr": "\u2557", "bl": "\u255a", "br": "\u255d", "h": "\u2550", "v": "\u2551"}
BOX_S = {"tl": "\u250c", "tr": "\u2510", "bl": "\u2514", "br": "\u2518", "h": "\u2500", "v": "\u2502"}

def get_terminal_width() -> int:
    try:
        r = subprocess.run(["sh", "-c", "stty size </dev/tty 2>/dev/null"], capture_output=True, text=True)
        if r.stdout:
            return int(r.stdout.strip().split()[1])
    except Exception:
        pass
    return int(os.environ.get("COLUMNS", "80")) or 80

def get_stats() -> dict:
    name = "PAI"
    skills = hooks = work_items = learnings = user_files = 0
    try:
        s = json.loads(Path(os.path.join(CLAUDE_DIR, "settings.json")).read_text())
        name = s.get("daidentity", {}).get("displayName") or s.get("daidentity", {}).get("name") or "PAI"
    except Exception:
        pass
    return {"name": name, "skills": skills, "userFiles": user_files,
            "hooks": hooks, "workItems": work_items, "learnings": learnings, "model": "Opus 4.5"}

def generate_progress_bar(width: int, fill: float = 0.7) -> str:
    filled = int(width * fill)
    empty = width - filled
    return f"[\u2588" * filled + "\u2591" * empty + "]"

def create_retro_banner() -> str:
    stats = get_stats()
    g = COLORS["greenBright"]; gd = COLORS["greenDim"]
    h = COLORS["highlight"]; f = COLORS["frame"]
    a = COLORS["amberBright"]; c = COLORS["cyan"]

    lines = []
    logo = [
        "        .============.",
        "       /      P     /|",
        "      /    P   P   / |",
        "     /   PPPPPPP  /  |",
        "    /    P     P /   |",
        "   +=============+   |",
        "   |             | A |",
        "   |      A      |A A|",
        "   |     A A     +---+",
        "   |    AAAAA   /   /",
        "   |   A     A /   /",
        "   +----------+   /",
        "   |    III   |  /",
        "   |    III   | /",
        "   |    III   |/",
        "   +----------+",
    ]
    logo_width = 22
    gap = 4
    stats_box = [
        f"{f}{BOX_S['tl']}{BOX_S['h']*24}{BOX_S['tr']}{RESET}",
        f"{f}{BOX_S['v']}{RESET} {g}DA{RESET}{gd}..........{RESET}: {h}{stats['name']:<8}{RESET} {f}{BOX_S['v']}{RESET}",
        f"{f}{BOX_S['v']}{RESET} {g}Skills{RESET}{gd}......{RESET}: {h}{str(stats['skills']):<8}{RESET} {f}{BOX_S['v']}{RESET}",
        f"{f}{BOX_S['v']}{RESET} {g}Hooks{RESET}{gd}.......{RESET}: {h}{str(stats['hooks']):<8}{RESET} {f}{BOX_S['v']}{RESET}",
        f"{f}{BOX_S['v']}{RESET} {g}Model{RESET}{gd}.......{RESET}: {h}{stats['model']:<8}{RESET} {f}{BOX_S['v']}{RESET}",
        f"{f}{BOX_S['bl']}{BOX_S['h']*24}{BOX_S['br']}{RESET}",
    ]
    max_rows = max(len(logo), len(stats_box))
    logo_offset = 2
    for i in range(max_rows):
        logo_part = ""
        if i < len(logo):
            if i < 5:
                logo_part = f"{c}{logo[i]}{RESET}"
            elif i < 11:
                logo_part = f"{COLORS['blue']}{logo[i]}{RESET}"
            else:
                logo_part = f"{COLORS['purple']}{logo[i]}{RESET}"
            logo_part += " " * max(0, logo_width - len(logo[i]))
        else:
            logo_part = " " * logo_width
        si = i - logo_offset
        sp = stats_box[si] if 0 <= si < len(stats_box) else ""
        lines.append(logo_part + " " * gap + sp)

    lines.append("")
    bw = 38
    lines.append(f"{a}{BOX_D['tl']}{BOX_D['h']*bw}{BOX_D['tr']}{RESET}")
    lines.append(f"{a}{BOX_D['v']}{RESET} {g}{BOLD}PAI{RESET} {gd}|{RESET} {h}Personal AI Infrastructure{RESET}  {a}{BOX_D['v']}{RESET}")
    lines.append(f"{a}{BOX_D['bl']}{BOX_D['h']*bw}{BOX_D['br']}{RESET}")
    lines.append("")
    lines.append(f"  {gd}\"{RESET}{g}Magnifying human capabilities through intelligent assistance{RESET}{gd}\"{RESET}")
    lines.append("")
    lines.append(f"  {gd}{BOX_S['h']*40}{RESET}")
    lines.append(f"  {g}>{RESET} {h}github.com/danielmiessler/PAI{RESET}{BLINK}_{RESET}")
    lines.append(f"  {gd}{BOX_S['h']*40}{RESET}")
    return "\n".join(lines)

def main() -> None:
    args = sys.argv[1:]
    try:
        if "--test" in args:
            for mode in ["retro"]:
                print(f"\n{'='*60}\n  MODE: {mode.upper()}\n{'='*60}\n")
                print(create_retro_banner())
        else:
            print()
            print(create_retro_banner())
            print()
    except Exception as e:
        print(f"Banner error: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
