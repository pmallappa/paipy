#!/usr/bin/env python3
"""
pai - Personal AI CLI Tool

Comprehensive CLI for managing Claude Code with dynamic MCP loading,
updates, version checking, and profile management.

Usage:
  pai                  Launch Claude (default profile)
  pai -m bd            Launch with Bright Data MCP
  pai -m bd,ap         Launch with multiple MCPs
  pai -r / --resume    Resume last session
  pai --local          Stay in current directory (don't cd to ~/.claude)
  pai update           Update Claude Code
  pai version          Show version info
  pai profiles         List available profiles
  pai mcp list         List available MCPs
  pai mcp set <profile>  Set MCP profile
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

# ============================================================================
# Configuration
# ============================================================================

CLAUDE_DIR = Path.home() / ".claude"
MCP_DIR = CLAUDE_DIR / "MCPs"
ACTIVE_MCP = CLAUDE_DIR / ".mcp.json"
BANNER_SCRIPT = CLAUDE_DIR / "PAI" / "Tools" / "Banner.ts"
VOICE_SERVER = "http://localhost:8888/notify/personality"
WALLPAPER_DIR = Path.home() / "Projects" / "Wallpaper"

# MCP shorthand mappings
MCP_SHORTCUTS: dict[str, str] = {
    "bd": "Brightdata-MCP.json",
    "brightdata": "Brightdata-MCP.json",
    "ap": "Apify-MCP.json",
    "apify": "Apify-MCP.json",
    "cu": "ClickUp-MCP.json",
    "clickup": "ClickUp-MCP.json",
    "chrome": "chrome-enabled.mcp.json",
    "dev": "dev-work.mcp.json",
    "sec": "security.mcp.json",
    "security": "security.mcp.json",
    "research": "research.mcp.json",
    "full": "full.mcp.json",
    "min": "minimal.mcp.json",
    "minimal": "minimal.mcp.json",
    "none": "none.mcp.json",
}

# Profile descriptions
PROFILE_DESCRIPTIONS: dict[str, str] = {
    "none": "No MCPs (maximum performance)",
    "minimal": "Essential MCPs (content, daemon, Foundry)",
    "chrome-enabled": "Essential + Chrome DevTools",
    "dev-work": "Development tools (Shadcn, Codex, Supabase)",
    "security": "Security tools (httpx, naabu)",
    "research": "Research tools (Brightdata, Apify, Chrome)",
    "clickup": "Official ClickUp MCP (tasks, time tracking, docs)",
    "full": "All available MCPs",
}


# ============================================================================
# Utilities
# ============================================================================


def log(message: str, emoji: str = "") -> None:
    print(f"{emoji} {message}" if emoji else message)


def error(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def notify_voice(message: str) -> None:
    """Fire and forget voice notification."""
    # In Python conversion, voice notifications are stubbed out
    # since they depend on the local voice server
    pass


def display_banner() -> None:
    if BANNER_SCRIPT.exists():
        subprocess.run(
            ["bun", str(BANNER_SCRIPT)],
            stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr,
        )


def get_current_version() -> Optional[str]:
    try:
        result = subprocess.run(["claude", "--version"], capture_output=True, text=True)
        match = re.search(r"([0-9]+\.[0-9]+\.[0-9]+)", result.stdout)
        return match.group(1) if match else None
    except Exception:
        return None


def compare_versions(a: str, b: str) -> int:
    parts_a = [int(x) for x in a.split(".")]
    parts_b = [int(x) for x in b.split(".")]
    for i in range(3):
        pa = parts_a[i] if i < len(parts_a) else 0
        pb = parts_b[i] if i < len(parts_b) else 0
        if pa > pb:
            return 1
        if pa < pb:
            return -1
    return 0


def get_latest_version() -> Optional[str]:
    try:
        import httpx
        response = httpx.get(
            "https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases/latest",
            timeout=10,
        )
        version = response.text.strip()
        if re.match(r"^[0-9]+\.[0-9]+\.[0-9]+", version):
            return version
    except Exception:
        pass
    return None


# ============================================================================
# MCP Management
# ============================================================================


def get_mcp_profiles() -> list[str]:
    if not MCP_DIR.exists():
        return []
    return [
        f.stem.replace(".mcp", "")
        for f in MCP_DIR.iterdir()
        if f.name.endswith(".mcp.json")
    ]


def get_individual_mcps() -> list[str]:
    if not MCP_DIR.exists():
        return []
    return [
        f.name.replace("-MCP.json", "")
        for f in MCP_DIR.iterdir()
        if f.name.endswith("-MCP.json")
    ]


def get_current_profile() -> Optional[str]:
    if not ACTIVE_MCP.exists():
        return None
    try:
        if ACTIVE_MCP.is_symlink():
            realpath = ACTIVE_MCP.resolve()
            return realpath.stem.replace(".mcp", "")
        return "custom"
    except Exception:
        return None


def merge_mcp_configs(mcp_files: list[str]) -> dict:
    merged: dict = {"mcpServers": {}}
    for file in mcp_files:
        filepath = MCP_DIR / file
        if not filepath.exists():
            log(f"Warning: MCP file not found: {file}", "Warning:")
            continue
        try:
            config = json.loads(filepath.read_text())
            if "mcpServers" in config:
                merged["mcpServers"].update(config["mcpServers"])
        except Exception:
            log(f"Warning: Failed to parse {file}", "Warning:")
    return merged


def set_mcp_profile(profile: str) -> None:
    profile_file = MCP_DIR / f"{profile}.mcp.json"
    if not profile_file.exists():
        error(f"Profile '{profile}' not found")

    if ACTIVE_MCP.exists() or ACTIVE_MCP.is_symlink():
        ACTIVE_MCP.unlink()

    ACTIVE_MCP.symlink_to(profile_file)
    log(f"Switched to '{profile}' profile", "Done:")
    log("Restart Claude Code to apply", "Note:")


def set_mcp_custom(mcp_names: list[str]) -> None:
    files: list[str] = []
    for name in mcp_names:
        file = MCP_SHORTCUTS.get(name.lower())
        if file:
            files.append(file)
        else:
            direct_file = f"{name}-MCP.json"
            profile_file = f"{name}.mcp.json"
            if (MCP_DIR / direct_file).exists():
                files.append(direct_file)
            elif (MCP_DIR / profile_file).exists():
                files.append(profile_file)
            else:
                error(f"Unknown MCP: {name}")

    merged = merge_mcp_configs(files)

    if ACTIVE_MCP.exists() or ACTIVE_MCP.is_symlink():
        ACTIVE_MCP.unlink()
    ACTIVE_MCP.write_text(json.dumps(merged, indent=2))

    server_count = len(merged.get("mcpServers", {}))
    if server_count > 0:
        log(f"Configured {server_count} MCP server(s): {', '.join(mcp_names)}", "Done:")


# ============================================================================
# Wallpaper Management
# ============================================================================


def get_wallpapers() -> list[str]:
    if not WALLPAPER_DIR.exists():
        return []
    return sorted([
        f.name for f in WALLPAPER_DIR.iterdir()
        if re.search(r"\.(png|jpg|jpeg|webp)$", f.name, re.IGNORECASE)
    ])


def get_wallpaper_name(filename: str) -> str:
    return re.sub(r"\.(png|jpg|jpeg|webp)$", "", filename, flags=re.IGNORECASE)


def find_wallpaper(query: str) -> Optional[str]:
    wallpapers = get_wallpapers()
    query_lower = query.lower()

    # Exact match
    for w in wallpapers:
        if get_wallpaper_name(w).lower() == query_lower:
            return w

    # Partial match
    for w in wallpapers:
        if query_lower in get_wallpaper_name(w).lower():
            return w

    # Fuzzy: any word match
    words = re.split(r"[-_\s]+", query_lower)
    for w in wallpapers:
        name = get_wallpaper_name(w).lower()
        if any(word in name for word in words):
            return w

    return None


def set_wallpaper(filename: str) -> bool:
    full_path = WALLPAPER_DIR / filename
    if not full_path.exists():
        log(f"Wallpaper not found: {full_path}", "Error:")
        return False

    success = True

    # Set Kitty background
    try:
        result = subprocess.run(
            ["kitty", "@", "set-background-image", str(full_path)],
            capture_output=True,
        )
        if result.returncode == 0:
            log("Kitty background set", "Done:")
        else:
            log("Failed to set Kitty background", "Warning:")
            success = False
    except FileNotFoundError:
        log("Kitty not available", "Warning:")

    # Set macOS desktop background
    try:
        script = f'tell application "System Events" to tell every desktop to set picture to "{full_path}"'
        result = subprocess.run(["osascript", "-e", script], capture_output=True)
        if result.returncode == 0:
            log("macOS desktop set", "Done:")
        else:
            log("Failed to set macOS desktop", "Warning:")
            success = False
    except FileNotFoundError:
        log("Could not set macOS desktop", "Warning:")

    return success


def cmd_wallpaper(args: list[str]) -> None:
    wallpapers = get_wallpapers()
    if not wallpapers:
        error(f"No wallpapers found in {WALLPAPER_DIR}")

    if not args or args[0] in ("--list", "-l", "list"):
        log("Available wallpapers:", "")
        print()
        for i, w in enumerate(wallpapers):
            print(f"  {i + 1}. {get_wallpaper_name(w)}")
        print()
        log("Usage: k -w <name>", "Tip:")
        log("Example: k -w circuit-board", "Tip:")
        return

    query = " ".join(args)
    match = find_wallpaper(query)
    if not match:
        log(f'No wallpaper matching "{query}"', "Error:")
        print("\nAvailable wallpapers:")
        for w in wallpapers:
            print(f"  - {get_wallpaper_name(w)}")
        sys.exit(1)

    name = get_wallpaper_name(match)
    log(f"Switching to: {name}", "")
    success = set_wallpaper(match)
    if success:
        log(f"Wallpaper set to {name}", "Done:")
        notify_voice(f"Wallpaper changed to {name}")
    else:
        error("Failed to set wallpaper")


# ============================================================================
# Commands
# ============================================================================


def cmd_launch(
    mcp: Optional[str] = None,
    resume: bool = False,
    skip_perms: bool = False,
    local: bool = False,
) -> None:
    display_banner()
    args = ["claude"]

    if mcp:
        mcp_names = [s.strip() for s in mcp.split(",")]
        set_mcp_custom(mcp_names)

    if resume:
        args.append("--resume")

    if not local:
        os.chdir(str(CLAUDE_DIR))

    notify_voice("Ready to go.")

    result = subprocess.run(args, env=os.environ.copy())
    sys.exit(result.returncode)


def cmd_update() -> None:
    log("Checking for updates...", "")
    current = get_current_version()
    latest = get_latest_version()

    if not current:
        error("Could not detect current version")

    print(f"Current: v{current}")
    if latest:
        print(f"Latest:  v{latest}")

    if latest and compare_versions(current, latest) >= 0:
        log("Already up to date", "Done:")
        return

    log("Updating Claude Code...", "")

    log("Step 1/2: Updating Bun...", "")
    bun_result = subprocess.run(["brew", "upgrade", "bun"], capture_output=True)
    if bun_result.returncode != 0:
        log("Bun update skipped (may already be latest)", "Warning:")
    else:
        log("Bun updated", "Done:")

    log("Step 2/2: Installing latest Claude Code...", "")
    claude_result = subprocess.run(
        ["bash", "-c", "curl -fsSL https://claude.ai/install.sh | bash"],
        capture_output=True,
    )
    if claude_result.returncode != 0:
        error("Claude Code installation failed")
    log("Claude Code updated", "Done:")

    new_version = get_current_version()
    if new_version:
        print(f"Now running: v{new_version}")


def cmd_version() -> None:
    log("Checking versions...", "")
    current = get_current_version()
    latest = get_latest_version()

    if not current:
        error("Could not detect current version")

    print(f"Current: v{current}")
    if latest:
        print(f"Latest:  v{latest}")
        cmp = compare_versions(current, latest)
        if cmp >= 0:
            log("Up to date", "Done:")
        else:
            log("Update available (run 'k update')", "Note:")
    else:
        log("Could not fetch latest version", "Warning:")


def cmd_profiles() -> None:
    log("Available MCP Profiles:", "")
    print()

    current = get_current_profile()
    profiles = get_mcp_profiles()

    for profile in profiles:
        is_current = profile == current
        desc = PROFILE_DESCRIPTIONS.get(profile, "")
        marker = "-> " if is_current else "  "
        badge = " (active)" if is_current else ""
        print(f"{marker}{profile}{badge}")
        if desc:
            print(f"    {desc}")

    print()
    log("Usage: k mcp set <profile>", "Tip:")


def cmd_mcp_list() -> None:
    log("Available MCPs:", "")
    print()

    log("Individual MCPs (use with -m):", "")
    mcps = get_individual_mcps()
    for mcp in mcps:
        shortcuts = [
            k for k, v in MCP_SHORTCUTS.items()
            if v == f"{mcp}-MCP.json"
        ]
        shortcuts_str = f" ({', '.join(shortcuts)})" if shortcuts else ""
        print(f"  {mcp}{shortcuts_str}")

    print()
    log("Profiles (use with 'k mcp set'):", "")
    profiles = get_mcp_profiles()
    for profile in profiles:
        desc = PROFILE_DESCRIPTIONS.get(profile, "")
        print(f"  {profile}{f' - {desc}' if desc else ''}")

    print()
    log("Examples:", "Tip:")
    print("  k -m bd          # Bright Data only")
    print("  k -m bd,ap       # Bright Data + Apify")
    print("  k mcp set research  # Full research profile")


def cmd_prompt(prompt: str) -> None:
    args = ["claude", "-p", prompt]
    os.chdir(str(CLAUDE_DIR))
    result = subprocess.run(args, env=os.environ.copy())
    sys.exit(result.returncode)


def cmd_help() -> None:
    print("""
pai - Personal AI CLI Tool (v2.0.0)

USAGE:
  k                        Launch Claude (no MCPs, max performance)
  k -m <mcp>               Launch with specific MCP(s)
  k -m bd,ap               Launch with multiple MCPs
  k -r, --resume           Resume last session
  k -l, --local            Stay in current directory (don't cd to ~/.claude)

COMMANDS:
  k update                 Update Claude Code to latest version
  k version, -v            Show version information
  k profiles               List available MCP profiles
  k mcp list               List all available MCPs
  k mcp set <profile>      Set MCP profile permanently
  k prompt "<text>"        One-shot prompt execution
  k -w, --wallpaper        List/switch wallpapers (Kitty + macOS)
  k help, -h               Show this help

MCP SHORTCUTS:
  bd, brightdata           Bright Data scraping
  ap, apify                Apify automation
  cu, clickup              Official ClickUp (tasks, time tracking, docs)
  chrome                   Chrome DevTools
  dev                      Development tools
  sec, security            Security tools
  research                 Research tools (BD + Apify + Chrome)
  full                     All MCPs
  min, minimal             Essential MCPs only
  none                     No MCPs

EXAMPLES:
  k                        Start with current profile
  k -m bd                  Start with Bright Data
  k -m bd,ap,chrome        Start with multiple MCPs
  k -r                     Resume last session
  k mcp set research       Switch to research profile
  k update                 Update Claude Code
  k prompt "What time is it?"   One-shot prompt
  k -w                     List available wallpapers
  k -w circuit-board       Switch wallpaper (Kitty + macOS)
""")


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    args = sys.argv[1:]

    if not args:
        cmd_launch()
        return

    mcp: Optional[str] = None
    resume = False
    skip_perms = True
    local = False
    command: Optional[str] = None
    sub_command: Optional[str] = None
    sub_arg: Optional[str] = None
    prompt_text: Optional[str] = None
    wallpaper_args: list[str] = []

    i = 0
    while i < len(args):
        arg = args[i]

        if arg in ("-m", "--mcp"):
            next_arg = args[i + 1] if i + 1 < len(args) else None
            if not next_arg or next_arg.startswith("-") or next_arg in ("0", ""):
                mcp = "none"
                if next_arg in ("0", ""):
                    i += 1
            else:
                i += 1
                mcp = args[i]
        elif arg in ("-r", "--resume"):
            resume = True
        elif arg == "--safe":
            skip_perms = False
        elif arg in ("-l", "--local"):
            local = True
        elif arg in ("-v", "--version", "version"):
            command = "version"
        elif arg in ("-h", "--help", "help"):
            command = "help"
        elif arg == "update":
            command = "update"
        elif arg == "profiles":
            command = "profiles"
        elif arg == "mcp":
            command = "mcp"
            i += 1
            sub_command = args[i] if i < len(args) else None
            i += 1
            sub_arg = args[i] if i < len(args) else None
        elif arg in ("prompt", "-p"):
            command = "prompt"
            prompt_text = " ".join(args[i + 1:])
            i = len(args)
        elif arg in ("-w", "--wallpaper"):
            command = "wallpaper"
            wallpaper_args = args[i + 1:]
            i = len(args)
        else:
            if not arg.startswith("-"):
                error(f"Unknown command: {arg}. Use 'k help' for usage.")

        i += 1

    if command == "version":
        cmd_version()
    elif command == "help":
        cmd_help()
    elif command == "update":
        cmd_update()
    elif command == "profiles":
        cmd_profiles()
    elif command == "mcp":
        if sub_command == "list":
            cmd_mcp_list()
        elif sub_command == "set" and sub_arg:
            set_mcp_profile(sub_arg)
        else:
            error("Usage: k mcp list | k mcp set <profile>")
    elif command == "prompt":
        if not prompt_text:
            error('Usage: k prompt "your prompt here"')
        cmd_prompt(prompt_text)
    elif command == "wallpaper":
        cmd_wallpaper(wallpaper_args)
    else:
        cmd_launch(mcp=mcp, resume=resume, skip_perms=skip_perms, local=local)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
