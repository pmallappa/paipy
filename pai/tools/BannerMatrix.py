#!/usr/bin/env python3
"""
BannerMatrix - Matrix Digital Rain PAI Banner
Neofetch-style layout with The Matrix aesthetic
"""

import json
import os
import random
import subprocess
import sys
from pathlib import Path

HOME = os.environ.get("HOME", str(Path.home()))
CLAUDE_DIR = os.path.join(HOME, ".claude")

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"

def rgb(r: int, g: int, b: int) -> str:
    return f"\x1b[38;2;{r};{g};{b}m"

MATRIX = {
    "bright": rgb(0, 255, 0), "primary": rgb(0, 220, 0),
    "mid": rgb(0, 180, 0), "dim": rgb(0, 140, 0),
    "dark": rgb(0, 100, 0), "darkest": rgb(0, 60, 0),
    "white": rgb(255, 255, 255), "cyan": rgb(0, 255, 180),
    "frame": rgb(0, 80, 0), "frameDim": rgb(0, 50, 0),
}

KATAKANA = list("アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン")
MATRIX_CHARS = list("0123456789:;<>=?@#$%&*+-/\\|^~ABCDEF")
HALFWIDTH_KANA = list("ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖ")

def random_katakana() -> str:
    return random.choice(KATAKANA)

def random_matrix_char() -> str:
    pool = MATRIX_CHARS + HALFWIDTH_KANA
    return random.choice(pool)

def random_hex(length: int = 4) -> str:
    return "".join(f"{random.randint(0,15):X}" for _ in range(length))

def get_terminal_width() -> int:
    try:
        result = subprocess.run(["sh", "-c", "stty size </dev/tty 2>/dev/null"],
                                capture_output=True, text=True)
        if result.stdout:
            cols = int(result.stdout.strip().split()[1])
            if cols > 0:
                return cols
    except Exception:
        pass
    return int(os.environ.get("COLUMNS", "80")) or 80

def get_display_mode() -> str:
    w = get_terminal_width()
    if w < 40: return "nano"
    if w < 60: return "micro"
    if w < 85: return "mini"
    return "normal"

def get_stats() -> dict:
    name = "PAI"
    settings_path = os.path.join(CLAUDE_DIR, "settings.json")
    try:
        settings = json.loads(Path(settings_path).read_text())
        name = (settings.get("daidentity", {}).get("displayName")
                or settings.get("daidentity", {}).get("name") or "PAI")
    except Exception:
        pass
    skills = hooks = work_items = learnings = user_files = 0
    try:
        skills_dir = os.path.join(CLAUDE_DIR, "skills")
        if os.path.isdir(skills_dir):
            for e in os.listdir(skills_dir):
                fp = os.path.join(skills_dir, e)
                if os.path.isdir(fp) and os.path.isfile(os.path.join(fp, "SKILL.md")):
                    skills += 1
    except Exception:
        pass
    return {"name": name, "skills": skills, "hooks": hooks,
            "workItems": work_items, "learnings": learnings,
            "userFiles": user_files, "model": "Opus 4.5"}

def create_nano_banner(stats: dict) -> str:
    g = MATRIX["bright"]; d = MATRIX["dim"]; w = MATRIX["white"]
    return f"{d}ｱ{RESET}{g}PAI{RESET}{d}ｲ{RESET} {w}{stats['name']}{RESET} {g}[ON]{RESET}"

def create_mini_banner(stats: dict) -> str:
    width = get_terminal_width()
    g = MATRIX["bright"]; p = MATRIX["primary"]; d = MATRIX["dim"]
    dk = MATRIX["darkest"]; w = MATRIX["white"]; f = MATRIX["frame"]
    lines = []
    rain = "".join(
        f"{g if random.random() > 0.7 else d}{random_matrix_char()}{RESET}"
        for _ in range(width)
    )
    lines.append(rain)
    lines.append(f"{f}{BOLD}{'='*width}{RESET}")
    lines.append(f"{d} > {RESET}{p}DA_NAME{RESET}{d}.......: {RESET}{w}{BOLD}{stats['name']}{RESET}")
    lines.append(f"{d} > {RESET}{p}SKILLS_COUNT{RESET}{d}.: {RESET}{g}{stats['skills']}{RESET}")
    lines.append(f"{d} > {RESET}{p}STATUS{RESET}{d}.......: {RESET}{g}{BOLD}[ONLINE]{RESET}")
    lines.append(f"{f}{BOLD}{'='*width}{RESET}")
    lines.append(rain[::-1] if len(rain) < 500 else rain)
    return "\n".join(lines)

def create_normal_banner(stats: dict) -> str:
    width = get_terminal_width()
    g = MATRIX["bright"]; p = MATRIX["primary"]; d = MATRIX["dim"]
    dk = MATRIX["darkest"]; w = MATRIX["white"]; f = MATRIX["frame"]
    m = MATRIX["mid"]
    lines = []
    def make_rain(length: int) -> str:
        return "".join(
            f"{[dk,d,m,p,g,w][min(5,int(random.random()*6))]}{random_matrix_char()}{RESET}"
            for _ in range(length)
        )
    lines.append(make_rain(width))
    lines.append(make_rain(width))
    lines.append(f"{f}{BOLD}{'='*width}{RESET}")
    lines.append(f"{d} > {RESET}{p}DA_NAME{RESET}{d}.......: {RESET}{w}{BOLD}{stats['name']}{RESET}")
    lines.append(f"{d} > {RESET}{p}SKILLS_COUNT{RESET}{d}.: {RESET}{g}{stats['skills']}{RESET}")
    lines.append(f"{d} > {RESET}{p}MODEL{RESET}{d}........: {RESET}{g}{stats['model']}{RESET}")
    lines.append(f"{d} > {RESET}{p}STATUS{RESET}{d}.......: {RESET}{g}{BOLD}[ONLINE]{RESET}")
    lines.append(f"{f}{BOLD}{'='*width}{RESET}")
    lines.append(make_rain(width))
    lines.append(make_rain(width))
    return "\n".join(lines)

def create_banner(force_mode: str | None = None) -> str:
    mode = force_mode or get_display_mode()
    stats = get_stats()
    if mode == "nano": return create_nano_banner(stats)
    if mode == "micro": return create_mini_banner(stats)
    if mode == "mini": return create_mini_banner(stats)
    return create_normal_banner(stats)

def main() -> None:
    args = sys.argv[1:]
    test_mode = "--test" in args
    mode_arg = None
    for a in args:
        if a.startswith("--mode="):
            mode_arg = a.split("=")[1]
    try:
        if test_mode:
            for mode in ["nano", "micro", "mini", "normal"]:
                print(f"\n{'='*60}\n  MODE: {mode.upper()}\n{'='*60}")
                print(create_banner(mode))
        else:
            print()
            print(create_banner(mode_arg))
            print()
    except Exception as e:
        print(f"Banner error: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
