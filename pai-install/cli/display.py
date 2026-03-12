"""
PAI Installer v4.0 -- CLI Display Helpers
ANSI colors, progress bars, banners, and formatted output.
"""

from __future__ import annotations

import sys
from typing import List

from engine.types import DetectionResult, InstallSummary, ValidationCheck

# -- ANSI Colors ---------------------------------------------------------------

c = {
    "reset": "\x1b[0m",
    "bold": "\x1b[1m",
    "dim": "\x1b[2m",
    "italic": "\x1b[3m",
    "blue": "\x1b[38;2;59;130;246m",
    "lightBlue": "\x1b[38;2;147;197;253m",
    "navy": "\x1b[38;2;30;58;138m",
    "green": "\x1b[38;2;34;197;94m",
    "yellow": "\x1b[38;2;234;179;8m",
    "red": "\x1b[38;2;239;68;68m",
    "gray": "\x1b[38;2;100;116;139m",
    "steel": "\x1b[38;2;51;65;85m",
    "silver": "\x1b[38;2;203;213;225m",
    "white": "\x1b[38;2;203;213;225m",
    "cyan": "\x1b[36m",
}


def print_text(text: str) -> None:
    """Print text with newline."""
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def print_success(text: str) -> None:
    """Print a success message."""
    print_text(f"  {c['green']}v{c['reset']} {text}")


def print_error(text: str) -> None:
    """Print an error message."""
    print_text(f"  {c['red']}x{c['reset']} {text}")


def print_warning(text: str) -> None:
    """Print a warning message."""
    print_text(f"  {c['yellow']}!{c['reset']} {text}")


def print_info(text: str) -> None:
    """Print an info message."""
    print_text(f"  {c['blue']}i{c['reset']} {text}")


def print_step(num: int, total: int, name: str) -> None:
    """Print a step header."""
    sep = "-" * 52
    print_text("")
    print_text(f"{c['gray']}{sep}{c['reset']}")
    print_text(f"{c['bold']} Step {num}/{total}: {name}{c['reset']}")
    print_text(f"{c['gray']}{sep}{c['reset']}")
    print_text("")


# -- Progress Bar ---------------------------------------------------------------


def progress_bar(percent: int, width: int = 30) -> str:
    """Generate a progress bar string."""
    filled = round((percent / 100) * width)
    empty = width - filled
    bar_filled = "#" * filled
    bar_empty = "." * empty
    return f"{c['blue']}{bar_filled}{c['gray']}{bar_empty}{c['reset']} {percent}%"


# -- Banner ---------------------------------------------------------------------


def print_banner() -> None:
    """Print the PAI installer banner."""
    sep = f"{c['steel']}|{c['reset']}"
    bar = f"{c['steel']}------------------------{c['reset']}"

    print_text("")
    print_text(f"{c['steel']}+----------------------------------------------------------------------+{c['reset']}")
    print_text("")
    print_text(f"                      {c['navy']}P{c['reset']}{c['blue']}A{c['reset']}{c['lightBlue']}I{c['reset']} {c['steel']}|{c['reset']} {c['gray']}Personal AI Infrastructure{c['reset']}")
    print_text("")
    print_text(f"                     {c['italic']}{c['lightBlue']}\"Magnifying human capabilities...\"{c['reset']}")
    print_text("")
    print_text("")
    print_text(f"           {c['navy']}################{'':4}{c['lightBlue']}####{c['reset']}   {sep}  {c['gray']}\"{c['reset']}{c['lightBlue']}{{DAIDENTITY.NAME}} here, ready to go{c['reset']}{c['gray']}...\"{c['reset']}")
    print_text(f"           {c['navy']}################{'':4}{c['lightBlue']}####{c['reset']}   {sep}  {bar}")
    print_text(f"           {c['navy']}####{'':8}####{c['reset']}{c['lightBlue']}####{c['reset']}   {sep}  {c['navy']}*{c['reset']}  {c['gray']}PAI v4.0{c['reset']}")
    print_text(f"           {c['navy']}####{'':8}####{c['reset']}{c['lightBlue']}####{c['reset']}   {sep}  {c['navy']}*{c['reset']}  {c['gray']}Algo{c['reset']}      {c['silver']}v3.5.0{c['reset']}")
    print_text(f"           {c['navy']}################{'':4}{c['lightBlue']}####{c['reset']}   {sep}  {c['lightBlue']}*{c['reset']}  {c['gray']}Installer{c['reset']} {c['silver']}v4.0{c['reset']}")
    print_text(f"           {c['navy']}################{'':4}{c['lightBlue']}####{c['reset']}   {sep}  {bar}")
    print_text(f"           {c['navy']}####{'':8}{c['blue']}####{c['reset']}{c['lightBlue']}####{c['reset']}   {sep}")
    print_text(f"           {c['navy']}####{'':8}{c['blue']}####{c['reset']}{c['lightBlue']}####{c['reset']}   {sep}  {c['lightBlue']}*  Lean and Mean{c['reset']}")
    print_text(f"           {c['navy']}####{'':8}{c['blue']}####{c['reset']}{c['lightBlue']}####{c['reset']}   {sep}")
    print_text(f"           {c['navy']}####{'':8}{c['blue']}####{c['reset']}{c['lightBlue']}####{c['reset']}   {sep}")
    print_text("")
    print_text("")
    print_text(f"                       {c['steel']}->{c['reset']} {c['blue']}github.com/danielmiessler/PAI{c['reset']}")
    print_text("")
    print_text(f"{c['steel']}+----------------------------------------------------------------------+{c['reset']}")
    print_text("")


# -- Detection Display ----------------------------------------------------------


def print_detection(det: DetectionResult) -> None:
    """Print detection results."""
    print_success(f"Operating System: {det.os.name} ({det.os.arch})")
    print_success(f"Shell: {det.shell.name} {f'v{det.shell.version[:20]}' if det.shell.version else ''}")

    if det.tools.bun.installed:
        print_success(f"Bun: v{det.tools.bun.version}")
    else:
        print_error("Bun: not found -- will install")

    if det.tools.git.installed:
        print_success(f"Git: v{det.tools.git.version}")
    else:
        print_error("Git: not found -- will install")

    if det.tools.claude.installed:
        print_success(f"Claude Code: v{det.tools.claude.version}")
    else:
        print_warning("Claude Code: not found -- will install")

    if det.existing.pai_installed:
        print_info(f"Existing PAI: v{det.existing.pai_version} (upgrade mode)")
    else:
        print_info("Existing PAI: not detected (fresh install)")

    print_info(f"Timezone: {det.timezone}")


# -- Validation Display ----------------------------------------------------------


def print_validation(checks: List[ValidationCheck]) -> None:
    """Print validation results."""
    print_text("")
    print_text(f"{c['bold']}  Validation Results{c['reset']}")
    print_text(f"{c['gray']}  {'-' * 40}{c['reset']}")

    for check in checks:
        if check.passed:
            print_success(f"{check.name}: {check.detail}")
        elif check.critical:
            print_error(f"{check.name}: {check.detail}")
        else:
            print_warning(f"{check.name}: {check.detail}")


def print_summary(summary: InstallSummary) -> None:
    """Print install summary."""
    def pad(s: str, width: int = 33) -> str:
        return " " * max(0, width - len(s))

    voice_text = summary.voice_mode if summary.voice_enabled else "Disabled"

    print_text("")
    print_text(f"{c['navy']}+==================================================+{c['reset']}")
    print_text(f"{c['navy']}|{c['reset']}  {c['green']}{c['bold']}SYSTEM ONLINE{c['reset']}                                    {c['navy']}|{c['reset']}")
    print_text(f"{c['navy']}+==================================================+{c['reset']}")
    print_text(f"{c['navy']}|{c['reset']}  PAI Version:  {c['white']}v{summary.pai_version}{c['reset']}{pad(summary.pai_version)}{c['navy']}|{c['reset']}")
    print_text(f"{c['navy']}|{c['reset']}  Principal:    {c['white']}{summary.principal_name}{c['reset']}{pad(summary.principal_name)}{c['navy']}|{c['reset']}")
    print_text(f"{c['navy']}|{c['reset']}  AI Name:      {c['white']}{summary.ai_name}{c['reset']}{pad(summary.ai_name)}{c['navy']}|{c['reset']}")
    print_text(f"{c['navy']}|{c['reset']}  Timezone:     {c['white']}{summary.timezone}{c['reset']}{pad(summary.timezone)}{c['navy']}|{c['reset']}")
    print_text(f"{c['navy']}|{c['reset']}  Voice:        {c['white']}{voice_text}{c['reset']}{pad(voice_text)}{c['navy']}|{c['reset']}")
    print_text(f"{c['navy']}|{c['reset']}  Install Type: {c['white']}{summary.install_type}{c['reset']}{pad(summary.install_type)}{c['navy']}|{c['reset']}")
    print_text(f"{c['navy']}+==================================================+{c['reset']}")
    print_text(f"{c['navy']}|{c['reset']}                                                  {c['navy']}|{c['reset']}")
    print_text(f"{c['navy']}|{c['reset']}  {c['lightBlue']}Run: {c['bold']}source ~/.zshrc && pai{c['reset']}                      {c['navy']}|{c['reset']}")
    print_text(f"{c['navy']}|{c['reset']}                                                  {c['navy']}|{c['reset']}")
    print_text(f"{c['navy']}+==================================================+{c['reset']}")
    print_text("")
