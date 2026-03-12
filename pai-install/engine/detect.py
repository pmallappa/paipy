"""
PAI Installer v4.0 -- System Detection
Detects OS, tools, existing PAI installation, and environment.
All detection is read-only and non-destructive.
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

from engine.types import (
    BrewInfo,
    DetectionResult,
    ExistingInfo,
    OSInfo,
    ShellInfo,
    ToolInfo,
    ToolsInfo,
)


def _try_exec(cmd: str, timeout: int = 5) -> Optional[str]:
    """Run a command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def _detect_os() -> OSInfo:
    """Detect operating system."""
    plat = "darwin" if platform.system() == "Darwin" else "linux"
    arch = platform.machine()
    version = ""
    name = ""

    if plat == "darwin":
        sw_vers = _try_exec("sw_vers -productVersion")
        version = sw_vers or ""
        name = f"macOS {version}"
    else:
        release = _try_exec(
            "cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"'"
        )
        name = release or "Linux"
        version = _try_exec("uname -r") or ""

    return OSInfo(platform=plat, arch=arch, version=version, name=name)


def _detect_shell() -> ShellInfo:
    """Detect shell."""
    shell_path = os.environ.get("SHELL", "/bin/sh")
    shell_name = Path(shell_path).name
    version = _try_exec(f"{shell_path} --version 2>&1 | head -1") or ""

    return ShellInfo(name=shell_name, version=version, path=shell_path)


def _detect_tool(name: str, version_cmd: str) -> ToolInfo:
    """Detect a specific tool."""
    path = _try_exec(f"which {name}")
    if not path:
        return ToolInfo(installed=False)

    version_output = _try_exec(version_cmd)
    version = None
    if version_output:
        match = re.search(r"(\d+\.\d+[\.\d]*)", version_output)
        version = match.group(1) if match else version_output

    return ToolInfo(installed=True, version=version, path=path)


def _detect_existing(
    home: str, pai_dir: str, config_dir: str
) -> ExistingInfo:
    """Detect existing PAI installation."""
    result = ExistingInfo(
        pai_installed=False,
        has_api_keys=False,
        eleven_labs_key_found=False,
        backup_paths=[],
    )

    # Check for existing PAI installation
    settings_path = os.path.join(pai_dir, "settings.json")
    if os.path.exists(settings_path):
        result.pai_installed = True
        result.settings_path = settings_path

        try:
            with open(settings_path, "r") as f:
                settings = json.load(f)
            result.pai_version = (
                settings.get("pai", {}).get("version")
                or settings.get("paiVersion")
                or "unknown"
            )
        except Exception:
            result.pai_version = "unknown"

    # Check for existing PAI skill
    skill_path = os.path.join(pai_dir, "skills", "PAI", "SKILL.md")
    if os.path.exists(skill_path):
        result.pai_installed = True

    # Check for API keys in env file
    env_path = os.path.join(config_dir, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r") as f:
                env_content = f.read()
            result.eleven_labs_key_found = "ELEVENLABS_API_KEY=" in env_content
            result.has_api_keys = result.eleven_labs_key_found
        except Exception:
            pass

    # Check for backup directories
    backup_patterns = [
        os.path.join(home, ".claude-backup"),
        os.path.join(home, ".claude-old"),
        os.path.join(home, ".claude-BACKUP"),
    ]
    for bp in backup_patterns:
        if os.path.exists(bp):
            result.backup_paths.append(bp)

    return result


def detect_system() -> DetectionResult:
    """Run full system detection. Safe, read-only, non-destructive."""
    home = str(Path.home())
    pai_dir = os.path.join(home, ".claude")
    config_dir = os.environ.get("PAI_CONFIG_DIR", os.path.join(home, ".config", "PAI"))

    brew_path = _try_exec("which brew")

    return DetectionResult(
        os=_detect_os(),
        shell=_detect_shell(),
        tools=ToolsInfo(
            bun=_detect_tool("bun", "bun --version"),
            git=_detect_tool("git", "git --version"),
            claude=_detect_tool("claude", "claude --version 2>&1"),
            node=_detect_tool("node", "node --version"),
            brew=BrewInfo(
                installed=brew_path is not None,
                path=brew_path or None,
            ),
        ),
        existing=_detect_existing(home, pai_dir, config_dir),
        timezone=time.tzname[0],
        home_dir=home,
        pai_dir=pai_dir,
        config_dir=config_dir,
    )


async def validate_eleven_labs_key(key: str) -> dict:
    """Validate an ElevenLabs API key."""
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(
            "https://api.elevenlabs.io/v1/user",
            headers={"xi-api-key": key},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                return {"valid": True}
            return {"valid": False, "error": f"HTTP {response.status}"}
    except urllib.error.HTTPError as e:
        return {"valid": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"valid": False, "error": str(e)}
