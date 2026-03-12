"""
PAI Installer v4.0 -- Install Actions
Pure action functions called by both CLI and web frontends.
Each action takes state + event emitter, performs work, returns result.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from engine.types import (
    DetectionResult,
    EngineEventHandler,
    InstallState,
)
from engine.detect import detect_system, validate_eleven_labs_key
from engine.config_gen import generate_settings_json


# ── Helpers ──────────────────────────────────────────────────────


def _find_existing_env_key(key_name: str) -> str:
    """
    Search existing .claude directories and config locations for a given env key.
    Returns the value if found, or empty string.
    """
    home = str(Path.home())
    search_paths: List[str] = []

    # Check ~/.config/pai/.env
    search_paths.append(os.path.join(home, ".config", "PAI", ".env"))

    # Check ~/.claude/.env
    search_paths.append(os.path.join(home, ".claude", ".env"))

    # Check any .claude* directories in home (old versions, backups)
    try:
        for entry in os.listdir(home):
            if entry.startswith(".claude") and entry != ".claude":
                search_paths.append(os.path.join(home, entry, ".env"))
                search_paths.append(os.path.join(home, entry, ".config", "PAI", ".env"))
    except Exception:
        pass

    for env_path in search_paths:
        try:
            if os.path.exists(env_path):
                with open(env_path, "r") as f:
                    content = f.read()
                match = re.search(rf"^{re.escape(key_name)}=(.+)$", content, re.MULTILINE)
                if match and match.group(1).strip():
                    return match.group(1).strip()
        except Exception:
            pass

    # Also check current environment
    return os.environ.get(key_name, "")


def _find_existing_voice_config() -> Optional[Dict[str, str]]:
    """
    Search existing .claude directories for settings.json voice configuration.
    Returns {voice_id, ai_name, source} if found, or None.
    """
    home = str(Path.home())
    candidates: List[str] = []

    # Primary location first
    candidates.append(os.path.join(home, ".claude", "settings.json"))

    # Scan all .claude* directories (backups, renamed, etc.)
    try:
        for entry in os.listdir(home):
            if entry.startswith(".claude") and entry != ".claude":
                candidates.append(os.path.join(home, entry, "settings.json"))
    except Exception:
        pass

    for settings_path in candidates:
        try:
            if not os.path.exists(settings_path):
                continue
            with open(settings_path, "r") as f:
                settings = json.load(f)
            voice_id = (
                settings.get("daidentity", {}).get("voices", {}).get("main", {}).get("voiceId")
                or settings.get("daidentity", {}).get("voiceId")
            )
            if voice_id and not re.match(r"^\{.+\}$", voice_id):
                dir_name = os.path.basename(os.path.dirname(settings_path))
                return {
                    "voice_id": voice_id,
                    "ai_name": settings.get("daidentity", {}).get("name", ""),
                    "source": dir_name,
                }
        except Exception:
            pass

    return None


def _try_exec(cmd: str, timeout: int = 30) -> Optional[str]:
    """Execute a command and return stdout, or None on failure."""
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


# ── User Context Migration (v2.5/v3.0 -> v4.x) ─────────────────
#
# In v2.5-v3.0, user context (ABOUTME.md, TELOS/, CONTACTS.md, etc.)
# lived at skills/pai/user/ (or skills/CORE/USER/ in v2.4).
# In v4.0, user context moved to pai/user/ and CONTEXT_ROUTING.md
# points there. But the installer never migrated existing files,
# leaving user data stranded at the old path while the new path
# stayed empty. This function copies user files to the canonical
# location and replaces the legacy directory with a symlink so
# both routing systems resolve to the same place.


def _copy_missing(src: str, dst: str) -> int:
    """
    Recursively copy files from src to dst, skipping files that
    already exist at the destination. Only copies regular files.
    """
    copied = 0
    if not os.path.exists(src):
        return copied

    for entry in os.scandir(src):
        src_path = entry.path
        dst_path = os.path.join(dst, entry.name)

        if entry.is_dir(follow_symlinks=False):
            os.makedirs(dst_path, exist_ok=True)
            copied += _copy_missing(src_path, dst_path)
        elif entry.is_file(follow_symlinks=False):
            if not os.path.exists(dst_path):
                try:
                    shutil.copy2(src_path, dst_path)
                    copied += 1
                except Exception:
                    pass
    return copied


async def _migrate_user_context(
    pai_dir: str,
    emit: EngineEventHandler,
) -> None:
    """
    Migrate user context from legacy skills/pai/user or skills/CORE/USER
    to the canonical pai/user location. Replaces the legacy directory
    with a symlink so the skill's relative USER/ paths still resolve.
    """
    new_user_dir = os.path.join(pai_dir, "PAI", "USER")
    if not os.path.exists(new_user_dir):
        return  # pai/user/ not set up yet

    legacy_paths = [
        os.path.join(pai_dir, "skills", "PAI", "USER"),   # v2.5-v3.0
        os.path.join(pai_dir, "skills", "CORE", "USER"),  # v2.4 and earlier
    ]

    for legacy_dir in legacy_paths:
        if not os.path.exists(legacy_dir):
            continue

        # Skip if already a symlink (migration already ran)
        try:
            if os.path.islink(legacy_dir):
                continue
        except Exception:
            continue

        label = "skills/CORE/USER" if "CORE" in legacy_dir else "skills/pai/user"
        await emit({
            "event": "progress",
            "step": "repository",
            "percent": 70,
            "detail": f"Migrating user context from {label}...",
        })

        copied = _copy_missing(legacy_dir, new_user_dir)
        if copied > 0:
            await emit({
                "event": "message",
                "content": f"Migrated {copied} user context files from {label} to pai/user.",
            })

        # Replace legacy dir with symlink so skill-relative paths still work
        try:
            shutil.rmtree(legacy_dir)
            # Symlink target is relative: from skills/pai/ or skills/CORE/ -> ../../pai/user
            os.symlink(os.path.join("..", "..", "PAI", "USER"), legacy_dir)
            await emit({
                "event": "message",
                "content": f"Replaced {label} with symlink to pai/user.",
            })
        except Exception:
            await emit({
                "event": "message",
                "content": f"Could not replace {label} with symlink. User files were copied but old directory remains.",
            })


# ── Step 1: System Detection ────────────────────────────────────


async def run_system_detect(
    state: InstallState,
    emit: EngineEventHandler,
) -> DetectionResult:
    """Step 1: Detect system environment."""
    await emit({"event": "step_start", "step": "system-detect"})
    await emit({"event": "progress", "step": "system-detect", "percent": 10, "detail": "Detecting operating system..."})

    detection = detect_system()
    state.detection = detection

    await emit({"event": "progress", "step": "system-detect", "percent": 50, "detail": "Checking installed tools..."})

    # Determine install type
    if detection.existing.pai_installed:
        state.install_type = "upgrade"
        await emit({
            "event": "message",
            "content": f"Existing PAI installation detected (v{detection.existing.pai_version or 'unknown'}). This will upgrade your installation.",
        })
    else:
        state.install_type = "fresh"
        await emit({"event": "message", "content": "No existing PAI installation found. Starting fresh install."})

    # Pre-fill collected data from existing installation
    def is_placeholder(v: str) -> bool:
        return bool(re.match(r"^\{.+\}$", v))

    if detection.existing.pai_installed and detection.existing.settings_path:
        try:
            with open(detection.existing.settings_path, "r") as f:
                settings = json.load(f)
            pn = settings.get("principal", {}).get("name", "")
            if pn and not is_placeholder(pn):
                state.collected.principal_name = pn
            tz = settings.get("principal", {}).get("timezone", "")
            if tz and not is_placeholder(tz):
                state.collected.timezone = tz
            ai = settings.get("daidentity", {}).get("name", "")
            if ai and not is_placeholder(ai):
                state.collected.ai_name = ai
            cp = settings.get("daidentity", {}).get("startupCatchphrase", "")
            if cp and not is_placeholder(cp):
                state.collected.catchphrase = cp
            pd = settings.get("env", {}).get("PROJECTS_DIR", "")
            if pd and not is_placeholder(pd):
                state.collected.projects_dir = pd
            tu = settings.get("preferences", {}).get("temperatureUnit")
            if tu:
                state.collected.temperature_unit = tu
        except Exception:
            pass

    await emit({"event": "progress", "step": "system-detect", "percent": 100, "detail": "Detection complete"})
    await emit({"event": "step_complete", "step": "system-detect"})
    return detection


# ── Step 2: Prerequisites ───────────────────────────────────────


async def run_prerequisites(
    state: InstallState,
    emit: EngineEventHandler,
) -> None:
    """Step 2: Install prerequisite tools."""
    await emit({"event": "step_start", "step": "prerequisites"})
    det = state.detection
    assert det is not None

    # Install Git if missing
    if not det.tools.git.installed:
        await emit({"event": "progress", "step": "prerequisites", "percent": 10, "detail": "Installing Git..."})

        if det.os.platform == "darwin":
            if det.tools.brew.installed:
                result = _try_exec("brew install git", timeout=120)
                if result is not None:
                    await emit({"event": "message", "content": "Git installed via Homebrew."})
                else:
                    await emit({"event": "message", "content": "Xcode Command Line Tools should include Git. Run: xcode-select --install"})
            else:
                await emit({"event": "message", "content": "Please install Git: xcode-select --install"})
        else:
            # Linux
            pkg_mgr = "apt-get" if _try_exec("which apt-get") else ("yum" if _try_exec("which yum") else None)
            if pkg_mgr:
                _try_exec(f"sudo {pkg_mgr} install -y git", timeout=120)
                await emit({"event": "message", "content": f"Git installed via {pkg_mgr}."})
    else:
        await emit({"event": "progress", "step": "prerequisites", "percent": 20, "detail": f"Git found: v{det.tools.git.version}"})

    # Bun should already be installed by bootstrap script, but verify
    if not det.tools.bun.installed:
        await emit({"event": "progress", "step": "prerequisites", "percent": 40, "detail": "Installing Bun..."})
        result = _try_exec("curl -fsSL https://bun.sh/install | bash", timeout=60)
        if result is not None:
            bun_bin = os.path.join(str(Path.home()), ".bun", "bin")
            os.environ["PATH"] = f"{bun_bin}:{os.environ.get('PATH', '')}"
            await emit({"event": "message", "content": "Bun installed successfully."})
    else:
        await emit({"event": "progress", "step": "prerequisites", "percent": 50, "detail": f"Bun found: v{det.tools.bun.version}"})

    # Install Claude Code if missing
    if not det.tools.claude.installed:
        await emit({"event": "progress", "step": "prerequisites", "percent": 70, "detail": "Installing Claude Code..."})

        npm_result = _try_exec("npm install -g @anthropic-ai/claude-code", timeout=120)
        if npm_result is not None:
            await emit({"event": "message", "content": "Claude Code installed via npm."})
        else:
            bun_result = _try_exec("bun install -g @anthropic-ai/claude-code", timeout=120)
            if bun_result is not None:
                await emit({"event": "message", "content": "Claude Code installed via bun."})
            else:
                await emit({
                    "event": "message",
                    "content": "Could not install Claude Code automatically. Please install manually: npm install -g @anthropic-ai/claude-code",
                })
    else:
        await emit({"event": "progress", "step": "prerequisites", "percent": 80, "detail": f"Claude Code found: v{det.tools.claude.version}"})

    await emit({"event": "progress", "step": "prerequisites", "percent": 100, "detail": "All prerequisites ready"})
    await emit({"event": "step_complete", "step": "prerequisites"})


# ── Step 3: API Keys (passthrough -- key collection moved to Voice Setup) ──


async def run_api_keys(
    state: InstallState,
    emit: EngineEventHandler,
    _get_input: Callable[..., Any],
    _get_choice: Callable[..., Any],
) -> None:
    """Step 3: API Keys (passthrough -- collection moved to Voice Setup)."""
    await emit({"event": "step_start", "step": "api-keys"})
    await emit({"event": "message", "content": "API keys will be collected during Voice Setup."})
    await emit({"event": "step_complete", "step": "api-keys"})


# ── Step 4: Identity ────────────────────────────────────────────


async def run_identity(
    state: InstallState,
    emit: EngineEventHandler,
    get_input: Callable[..., Any],
) -> None:
    """Step 4: Configure identity."""
    await emit({"event": "step_start", "step": "identity"})

    # Name
    default_name = state.collected.principal_name or ""
    name_prompt = (
        f"What is your name? (Press Enter to keep: {default_name})"
        if default_name
        else "What is your name?"
    )
    name = await get_input("principal-name", name_prompt, "text", "Your name")
    state.collected.principal_name = name.strip() or default_name or "User"

    # Timezone
    detected_tz = (state.detection.timezone if state.detection else None) or time.tzname[0]
    tz = await get_input(
        "timezone",
        f"Detected timezone: {detected_tz}. Press Enter to confirm or type a different one.",
        "text",
        detected_tz,
    )
    state.collected.timezone = tz.strip() or detected_tz

    # Temperature unit
    default_temp_unit = state.collected.temperature_unit or "fahrenheit"
    temp_unit = await get_input(
        "temperature-unit",
        f"Temperature unit? Type F for Fahrenheit or C for Celsius. (Default: {'C' if default_temp_unit == 'celsius' else 'F'})",
        "text",
        "C" if default_temp_unit == "celsius" else "F",
    )
    trimmed_unit = temp_unit.strip().lower()
    state.collected.temperature_unit = "celsius" if trimmed_unit in ("c", "celsius") else "fahrenheit"

    # AI Name
    default_ai = state.collected.ai_name or ""
    ai_prompt = (
        f"What would you like to name your AI assistant? (Press Enter to keep: {default_ai})"
        if default_ai
        else "What would you like to name your AI assistant?"
    )
    ai_name = await get_input("ai-name", ai_prompt, "text", "e.g., Atlas, Nova, Sage")
    state.collected.ai_name = ai_name.strip() or default_ai or "PAI"

    # Catchphrase
    default_catch = state.collected.catchphrase or f"{state.collected.ai_name} here, ready to go"
    catchphrase = await get_input(
        "catchphrase",
        f"Startup catchphrase for {state.collected.ai_name}?",
        "text",
        default_catch,
    )
    state.collected.catchphrase = catchphrase.strip() or default_catch

    # Projects directory (optional)
    default_projects = state.collected.projects_dir or ""
    proj_dir = await get_input(
        "projects-dir",
        "Projects directory (optional, press Enter to skip):",
        "text",
        default_projects or "~/Projects",
    )
    if proj_dir.strip():
        state.collected.projects_dir = proj_dir.strip().replace("~", str(Path.home()))

    await emit({
        "event": "message",
        "content": f"Identity configured: {state.collected.principal_name} with AI assistant {state.collected.ai_name}.",
        "speak": True,
    })
    await emit({"event": "step_complete", "step": "identity"})


# ── Step 5: Repository ──────────────────────────────────────────


async def run_repository(
    state: InstallState,
    emit: EngineEventHandler,
) -> None:
    """Step 5: Clone or update the PAI repository."""
    await emit({"event": "step_start", "step": "repository"})
    home = str(Path.home())
    pai_dir = state.detection.pai_dir if state.detection else os.path.join(home, ".claude")

    if state.install_type == "upgrade":
        await emit({"event": "progress", "step": "repository", "percent": 20, "detail": "Existing installation found, updating..."})

        is_git_repo = os.path.exists(os.path.join(pai_dir, ".git"))
        if is_git_repo:
            pull_result = _try_exec(f'cd "{pai_dir}" && git pull origin main 2>&1', timeout=60)
            if pull_result is not None:
                await emit({"event": "message", "content": "PAI repository updated from GitHub."})
            else:
                await emit({"event": "message", "content": "Could not pull updates. Continuing with existing files."})
        else:
            await emit({"event": "message", "content": "Existing installation is not a git repo. Preserving current files."})
    else:
        # Fresh install -- clone repo
        await emit({"event": "progress", "step": "repository", "percent": 20, "detail": "Cloning PAI repository..."})

        os.makedirs(pai_dir, exist_ok=True)

        clone_result = _try_exec(
            f'git clone https://github.com/danielmiessler/PAI.git "{pai_dir}" 2>&1',
            timeout=120,
        )

        if clone_result is not None:
            await emit({"event": "message", "content": "PAI repository cloned successfully."})
        else:
            await emit({"event": "progress", "step": "repository", "percent": 50, "detail": "Directory exists, trying alternative approach..."})

            init_result = _try_exec(
                f'cd "{pai_dir}" && git init && git remote add origin https://github.com/danielmiessler/PAI.git && git fetch origin && git checkout -b main origin/main 2>&1',
                timeout=120,
            )
            if init_result is not None:
                await emit({"event": "message", "content": "PAI repository initialized and synced."})
            else:
                await emit({
                    "event": "message",
                    "content": "Could not clone PAI repo automatically. You can clone it manually later: git clone https://github.com/danielmiessler/PAI.git ~/.claude",
                })

    # Create required directories regardless of clone result
    required_dirs = [
        "MEMORY",
        os.path.join("MEMORY", "STATE"),
        os.path.join("MEMORY", "LEARNING"),
        os.path.join("MEMORY", "WORK"),
        os.path.join("MEMORY", "RELATIONSHIP"),
        os.path.join("MEMORY", "VOICE"),
        "Plans",
        "hooks",
        "skills",
        "tasks",
    ]

    for d in required_dirs:
        full_path = os.path.join(pai_dir, d)
        os.makedirs(full_path, exist_ok=True)

    # Migrate user context from v2.5/v3.0 location to v4.x canonical location
    if state.install_type == "upgrade":
        await _migrate_user_context(pai_dir, emit)

    await emit({"event": "progress", "step": "repository", "percent": 100, "detail": "Repository ready"})
    await emit({"event": "step_complete", "step": "repository"})


# ── Step 6: Configuration ───────────────────────────────────────


async def run_configuration(
    state: InstallState,
    emit: EngineEventHandler,
) -> None:
    """Step 6: Generate configuration files."""
    await emit({"event": "step_start", "step": "configuration"})
    home = str(Path.home())
    pai_dir = state.detection.pai_dir if state.detection else os.path.join(home, ".claude")
    config_dir = state.detection.config_dir if state.detection else os.path.join(home, ".config", "PAI")

    # Generate settings.json
    await emit({"event": "progress", "step": "configuration", "percent": 20, "detail": "Generating settings.json..."})

    from engine.types import PAIConfig

    config = generate_settings_json(PAIConfig(
        principal_name=state.collected.principal_name or "User",
        timezone=state.collected.timezone or time.tzname[0],
        ai_name=state.collected.ai_name or "PAI",
        catchphrase=state.collected.catchphrase or "Ready to go",
        projects_dir=state.collected.projects_dir,
        temperature_unit=state.collected.temperature_unit,
        voice_type=state.collected.voice_type,
        voice_id=state.collected.custom_voice_id,
        pai_dir=pai_dir,
        config_dir=config_dir,
    ))

    settings_path = os.path.join(pai_dir, "settings.json")

    # The release ships a complete settings.json with hooks, statusLine, spinnerVerbs, etc.
    # We only update user-specific fields -- never overwrite the whole file.
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r") as f:
                existing = json.load(f)
            # Merge only installer-managed fields; preserve everything else
            existing["env"] = {**existing.get("env", {}), **config.get("env", {})}
            existing["principal"] = {**existing.get("principal", {}), **config.get("principal", {})}
            existing["daidentity"] = {**existing.get("daidentity", {}), **config.get("daidentity", {})}
            existing["pai"] = {**existing.get("pai", {}), **config.get("pai", {})}
            existing["preferences"] = {**existing.get("preferences", {}), **config.get("preferences", {})}
            # Only set permissions/contextFiles/plansDirectory if not already present
            if "permissions" not in existing and "permissions" in config:
                existing["permissions"] = config["permissions"]
            if "contextFiles" not in existing and "contextFiles" in config:
                existing["contextFiles"] = config["contextFiles"]
            if "plansDirectory" not in existing and "plansDirectory" in config:
                existing["plansDirectory"] = config["plansDirectory"]
            with open(settings_path, "w") as f:
                json.dump(existing, f, indent=2)
        except Exception:
            # Existing file is corrupt -- write fresh as fallback
            with open(settings_path, "w") as f:
                json.dump(config, f, indent=2)
    else:
        with open(settings_path, "w") as f:
            json.dump(config, f, indent=2)

    await emit({"event": "message", "content": "settings.json generated."})

    # Update Algorithm LATEST version file (public repo may be behind)
    latest_dir = os.path.join(pai_dir, "skills", "PAI", "Components", "Algorithm")
    latest_path = os.path.join(latest_dir, "LATEST")
    if os.path.exists(latest_dir):
        try:
            with open(latest_path, "w") as f:
                f.write("v3.5.0\n")
        except Exception:
            pass

    # Calculate and write initial counts so banner shows real numbers on first launch
    await emit({"event": "progress", "step": "configuration", "percent": 35, "detail": "Calculating system counts..."})
    try:
        def count_files(directory: str, ext: Optional[str] = None) -> int:
            if not os.path.exists(directory):
                return 0
            count = 0
            for root, dirs, files in os.walk(directory):
                for name in files:
                    if ext is None or name.endswith(ext):
                        count += 1
            return count

        def count_dirs(directory: str, filter_fn: Optional[Callable[[str], bool]] = None) -> int:
            if not os.path.exists(directory):
                return 0
            try:
                entries = [
                    e for e in os.scandir(directory)
                    if e.is_dir() and (filter_fn is None or filter_fn(e.name))
                ]
                return len(entries)
            except Exception:
                return 0

        skills_dir = os.path.join(pai_dir, "skills")
        skill_count = count_dirs(
            skills_dir,
            lambda name: os.path.exists(os.path.join(skills_dir, name, "SKILL.md")),
        )
        hook_count = count_files(os.path.join(pai_dir, "hooks"), ".ts")
        signal_count = count_files(os.path.join(pai_dir, "MEMORY", "LEARNING"), ".md")
        file_count = count_files(os.path.join(pai_dir, "skills", "PAI", "USER"))

        # Count workflows by scanning skill Tools directories for .ts files
        workflow_count = 0
        if os.path.exists(skills_dir):
            try:
                for entry in os.scandir(skills_dir):
                    if entry.is_dir():
                        tools_dir = os.path.join(skills_dir, entry.name, "Tools")
                        if os.path.exists(tools_dir):
                            workflow_count += count_files(tools_dir, ".ts")
            except Exception:
                pass

        # Write counts to settings.json
        with open(settings_path, "r") as f:
            current_settings = json.load(f)
        current_settings["counts"] = {
            "skills": skill_count,
            "workflows": workflow_count,
            "hooks": hook_count,
            "signals": signal_count,
            "files": file_count,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
        with open(settings_path, "w") as f:
            json.dump(current_settings, f, indent=2)
    except Exception:
        # Non-fatal -- banner will just show 0 until first session ends
        pass

    # Create .env file for API keys
    await emit({"event": "progress", "step": "configuration", "percent": 50, "detail": "Setting up API keys..."})

    os.makedirs(config_dir, exist_ok=True)

    env_path = os.path.join(config_dir, ".env")
    env_content = ""

    if state.collected.eleven_labs_key:
        env_content += f"ELEVENLABS_API_KEY={state.collected.eleven_labs_key}\n"

    if env_content:
        with open(env_path, "w") as f:
            f.write(env_content)
        os.chmod(env_path, 0o600)
        await emit({"event": "message", "content": "API keys saved securely."})

    # Create symlinks so all consumers can find the .env
    if os.path.exists(env_path):
        symlink_paths = [
            os.path.join(pai_dir, ".env"),         # ~/.claude/.env
            os.path.join(home, ".env"),             # ~/.env (voice server reads this)
        ]
        for symlink_path in symlink_paths:
            try:
                if os.path.exists(symlink_path):
                    if os.path.islink(symlink_path):
                        os.unlink(symlink_path)
                    else:
                        continue  # Don't overwrite a real file
                os.symlink(env_path, symlink_path)
            except Exception:
                pass

    # Set up shell alias (detect bash/zsh/fish)
    await emit({"event": "progress", "step": "configuration", "percent": 80, "detail": "Setting up shell alias..."})

    user_shell = os.environ.get("SHELL", "/bin/zsh")
    if "bash" in user_shell:
        rc_file = ".bashrc"
    elif "fish" in user_shell:
        rc_file = os.path.join(".config", "fish", "config.fish")
    else:
        rc_file = ".zshrc"

    rc_path = os.path.join(home, rc_file)
    alias_line = f"alias pai='bun {os.path.join(pai_dir, 'PAI', 'Tools', 'pai.ts')}'"
    marker = "# PAI alias"

    if os.path.exists(rc_path):
        with open(rc_path, "r") as f:
            content = f.read()
        # Remove any existing pai alias
        content = re.sub(r"^#\s*(?:PAI|CORE)\s*alias.*\n.*alias pai=.*\n?", "", content, flags=re.MULTILINE)
        content = re.sub(r"^alias pai=.*\n?", "", content, flags=re.MULTILINE)
        # Add fresh alias
        content = content.rstrip() + f"\n\n{marker}\n{alias_line}\n"
        with open(rc_path, "w") as f:
            f.write(content)
    else:
        with open(rc_path, "w") as f:
            f.write(f"{marker}\n{alias_line}\n")

    # Fix permissions
    await emit({"event": "progress", "step": "configuration", "percent": 90, "detail": "Setting permissions..."})
    try:
        _try_exec(f'chmod -R 755 "{pai_dir}"', timeout=10)
    except Exception:
        pass

    await emit({"event": "progress", "step": "configuration", "percent": 100, "detail": "Configuration complete"})
    await emit({"event": "step_complete", "step": "configuration"})


# ── Voice Server Management ────────────────────────────────────


async def _is_voice_server_running() -> bool:
    """Check if voice server is running."""
    import urllib.request

    try:
        req = urllib.request.Request("http://localhost:8888/health")
        with urllib.request.urlopen(req, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


async def _stop_voice_server(emit: EngineEventHandler) -> None:
    """Stop existing voice server."""
    if not await _is_voice_server_running():
        return

    await emit({"event": "progress", "step": "voice", "percent": 15, "detail": "Stopping existing voice server..."})

    # Try graceful shutdown via the server's own endpoint
    import urllib.request

    try:
        req = urllib.request.Request("http://localhost:8888/shutdown", method="POST")
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass

    # Kill the process LISTENING on port 8888
    _try_exec("lsof -ti:8888 -sTCP:LISTEN | xargs kill -9 2>/dev/null", timeout=5)

    # Unload existing LaunchAgent if present
    home = str(Path.home())
    plist_path = os.path.join(home, "Library", "LaunchAgents", "com.pai.voice-server.plist")
    if os.path.exists(plist_path):
        _try_exec(f'launchctl unload "{plist_path}" 2>/dev/null', timeout=5)

    # Wait for it to actually stop
    for _ in range(6):
        await asyncio.sleep(0.5)
        if not await _is_voice_server_running():
            await emit({"event": "message", "content": "Existing voice server stopped."})
            return


async def _start_voice_server(pai_dir: str, emit: EngineEventHandler) -> bool:
    """Start the voice server."""
    voice_server_dir = os.path.join(pai_dir, "voice-server")
    install_script = os.path.join(voice_server_dir, "install.sh")
    start_script = os.path.join(voice_server_dir, "start.sh")
    server_ts = os.path.join(voice_server_dir, "server.ts")

    if not os.path.exists(voice_server_dir):
        await emit({"event": "message", "content": "Voice server not found in installation."})
        return False

    # Step 1: Stop any existing voice server
    await _stop_voice_server(emit)

    # Step 2: Install as LaunchAgent (auto-start on login)
    await emit({"event": "progress", "step": "voice", "percent": 20, "detail": "Installing voice server service..."})
    if os.path.exists(install_script):
        try:
            proc = subprocess.Popen(
                ["bash", install_script],
                cwd=voice_server_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                proc.stdin.write(b"y\nn\n")
                proc.stdin.flush()
            except Exception:
                pass
            try:
                proc.wait(timeout=30)
                install_ok = proc.returncode == 0
            except subprocess.TimeoutExpired:
                proc.kill()
                install_ok = False

            if install_ok:
                for _ in range(10):
                    await asyncio.sleep(0.5)
                    if await _is_voice_server_running():
                        await emit({"event": "message", "content": "Voice server installed and running."})
                        return True
        except Exception:
            pass

    # Step 3: Fallback -- try start.sh if LaunchAgent install failed
    if os.path.exists(start_script):
        await emit({"event": "progress", "step": "voice", "percent": 25, "detail": "Starting voice server..."})
        try:
            proc = subprocess.Popen(
                ["bash", start_script],
                cwd=voice_server_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception:
            pass

        for _ in range(10):
            await asyncio.sleep(0.5)
            if await _is_voice_server_running():
                await emit({"event": "message", "content": "Voice server started."})
                return True

    # Step 4: Last resort -- start server.ts directly in background
    if os.path.exists(server_ts):
        await emit({"event": "progress", "step": "voice", "percent": 30, "detail": "Starting voice server directly..."})
        try:
            proc = subprocess.Popen(
                ["bun", "run", server_ts],
                cwd=voice_server_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

            for _ in range(10):
                await asyncio.sleep(0.5)
                if await _is_voice_server_running():
                    await emit({"event": "message", "content": "Voice server started directly."})
                    return True
        except Exception:
            pass

    await emit({"event": "message", "content": "Could not start voice server. Voice will be configured but TTS test skipped."})
    return False


# ── Step 7: Voice Setup ─────────────────────────────────────────


async def run_voice_setup(
    state: InstallState,
    emit: EngineEventHandler,
    get_choice: Callable[..., Any],
    get_input: Callable[..., Any],
) -> None:
    """Step 7: Voice setup (handles key collection + voice selection + server test)."""
    await emit({"event": "step_start", "step": "voice"})

    # -- Collect ElevenLabs key if not already found --
    if not state.collected.eleven_labs_key:
        await emit({"event": "progress", "step": "voice", "percent": 5, "detail": "Searching for existing ElevenLabs key..."})
        eleven_labs_key = _find_existing_env_key("ELEVENLABS_API_KEY")

        if eleven_labs_key:
            await emit({"event": "message", "content": "Found existing ElevenLabs API key. Validating..."})
            result = await validate_eleven_labs_key(eleven_labs_key)
            if result.get("valid"):
                state.collected.eleven_labs_key = eleven_labs_key
                await emit({"event": "message", "content": "Existing ElevenLabs API key is valid."})
            else:
                await emit({"event": "message", "content": f"Existing key invalid: {result.get('error', 'unknown')}."})
                eleven_labs_key = ""

        if not eleven_labs_key:
            wants_voice = await get_choice(
                "voice-enable",
                "Voice requires an ElevenLabs API key. Get one free at elevenlabs.io",
                [
                    {"label": "I have a key", "value": "yes"},
                    {"label": "Skip voice for now", "value": "skip"},
                ],
            )

            if wants_voice == "yes":
                key = await get_input(
                    "elevenlabs-key",
                    "Enter your ElevenLabs API key:",
                    "key",
                    "sk_...",
                )

                if key.strip():
                    await emit({"event": "progress", "step": "voice", "percent": 15, "detail": "Validating ElevenLabs key..."})
                    result = await validate_eleven_labs_key(key.strip())
                    if result.get("valid"):
                        state.collected.eleven_labs_key = key.strip()
                        await emit({"event": "message", "content": "ElevenLabs API key verified."})
                    else:
                        await emit({"event": "message", "content": f"Key validation failed: {result.get('error', 'unknown')}. Skipping voice setup."})

    has_eleven_labs_key = bool(state.collected.eleven_labs_key)
    if not has_eleven_labs_key:
        await emit({
            "event": "message",
            "content": "No ElevenLabs key -- voice server will use macOS text-to-speech as fallback. You can add a key later in ~/.config/pai/.env",
        })

    # -- Start voice server (works with or without ElevenLabs key) --
    home = str(Path.home())
    pai_dir = state.detection.pai_dir if state.detection else os.path.join(home, ".claude")
    await emit({"event": "progress", "step": "voice", "percent": 25, "detail": "Starting voice server..."})
    voice_server_ready = await _start_voice_server(pai_dir, emit)

    # -- Digital Assistant Voice selection --
    await emit({"event": "progress", "step": "voice", "percent": 40, "detail": "Checking for existing voice configuration..."})

    voice_ids = {
        "male": "pNInz6obpgDQGcFmaJgB",
        "female": "21m00Tcm4TlvDq8ikWAM",
    }

    selected_voice_id = ""

    # Check for existing voice config from previous installations
    existing_voice = _find_existing_voice_config()

    if existing_voice:
        source_label = (
            f"{existing_voice['ai_name']}'s voice ({existing_voice['voice_id'][:8]}...)"
            if existing_voice.get("ai_name")
            else f"Voice ID {existing_voice['voice_id'][:8]}..."
        )
        await emit({"event": "message", "content": f"Found existing voice configuration from ~/{existing_voice['source']}"})

        use_existing = await get_choice(
            "voice-existing",
            f"Your DA was using: {source_label}. Use the same voice?",
            [
                {"label": "Yes, keep this voice", "value": "keep", "description": f"Voice ID: {existing_voice['voice_id']}"},
                {"label": "No, pick a new voice", "value": "new", "description": "Choose from presets or enter a custom ID"},
            ],
        )

        if use_existing == "keep":
            selected_voice_id = existing_voice["voice_id"]
            state.collected.voice_type = "custom"
            state.collected.custom_voice_id = selected_voice_id

    # Voice selection (if not using existing)
    if not selected_voice_id:
        await emit({"event": "progress", "step": "voice", "percent": 45, "detail": "Choose your Digital Assistant's voice..."})

        voice_type = await get_choice(
            "voice-type",
            "Digital Assistant Voice -- Choose a voice for your AI assistant:",
            [
                {"label": "Female (Rachel)", "value": "female", "description": "Warm, articulate female voice"},
                {"label": "Male (Adam)", "value": "male", "description": "Clear, confident male voice"},
                {"label": "Custom Voice ID", "value": "custom", "description": "Enter your own ElevenLabs voice ID"},
            ],
        )

        if voice_type == "custom":
            custom_id = await get_input(
                "custom-voice-id",
                "Enter your ElevenLabs Voice ID:\nFind it at: elevenlabs.io/app/voice-library -> Your voice -> Voice ID",
                "text",
                "e.g., s3TPKV1kjDlVtZbl4Ksh",
            )
            selected_voice_id = custom_id.strip() or voice_ids["female"]
            state.collected.voice_type = "custom"
            state.collected.custom_voice_id = selected_voice_id
        else:
            selected_voice_id = voice_ids.get(voice_type, voice_ids["female"])
            state.collected.voice_type = voice_type

    # -- Update settings.json with voice ID --
    await emit({"event": "progress", "step": "voice", "percent": 60, "detail": "Saving voice configuration..."})
    settings_path = os.path.join(pai_dir, "settings.json")

    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r") as f:
                settings = json.load(f)
            if "daidentity" in settings:
                settings["daidentity"]["voiceId"] = selected_voice_id
                settings["daidentity"].setdefault("voices", {})
                settings["daidentity"]["voices"]["main"] = {
                    "voiceId": selected_voice_id,
                    "stability": 0.35,
                    "similarityBoost": 0.80,
                    "style": 0.90,
                    "speed": 1.1,
                }
                settings["daidentity"]["voices"]["algorithm"] = {
                    "voiceId": selected_voice_id,
                    "stability": 0.35,
                    "similarityBoost": 0.80,
                    "style": 0.90,
                    "speed": 1.1,
                }
            with open(settings_path, "w") as f:
                json.dump(settings, f, indent=2)
            await emit({"event": "message", "content": "Voice settings saved to settings.json."})
        except Exception:
            pass

    # -- Save ElevenLabs key to .env (if provided) --
    if has_eleven_labs_key:
        config_dir = state.detection.config_dir if state.detection else os.path.join(home, ".config", "PAI")
        env_path = os.path.join(config_dir, ".env")
        os.makedirs(config_dir, exist_ok=True)

        env_content = ""
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                env_content = f.read()

        if "ELEVENLABS_API_KEY=" in env_content:
            env_content = re.sub(
                r"ELEVENLABS_API_KEY=.*",
                f"ELEVENLABS_API_KEY={state.collected.eleven_labs_key}",
                env_content,
            )
        else:
            env_content = env_content.strip() + f"\nELEVENLABS_API_KEY={state.collected.eleven_labs_key}\n"

        with open(env_path, "w") as f:
            f.write(env_content.strip() + "\n")
        os.chmod(env_path, 0o600)

        # Ensure symlinks exist at both ~/.claude/.env and ~/.env
        symlink_targets = [
            os.path.join(pai_dir, ".env"),
            os.path.join(home, ".env"),
        ]
        for sp in symlink_targets:
            try:
                if os.path.exists(sp):
                    if os.path.islink(sp):
                        os.unlink(sp)
                    else:
                        continue
                os.symlink(env_path, sp)
            except Exception:
                pass

    # -- Test TTS and confirm with user --
    if voice_server_ready:
        import urllib.request

        voice_confirmed = False
        while not voice_confirmed:
            await emit({"event": "progress", "step": "voice", "percent": 80, "detail": "Testing voice output..."})
            try:
                ai_name = state.collected.ai_name or "PAI"
                user_name = state.collected.principal_name or "there"
                test_data = json.dumps({
                    "message": f"Hello {user_name}, this is {ai_name}. My voice system is online and ready to assist you.",
                    "voice_id": selected_voice_id,
                    "voice_settings": {"stability": 0.35, "similarity_boost": 0.80, "style": 0.90, "speed": 1.1, "use_speaker_boost": True},
                }).encode("utf-8")

                req = urllib.request.Request(
                    "http://localhost:8888/notify",
                    data=test_data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    test_ok = response.status == 200

                if test_ok:
                    await emit({"event": "message", "content": f"Voice test sent -- listen for {ai_name} speaking...", "speak": False})

                    confirm = await get_choice(
                        "voice-confirm",
                        "Did you hear the voice? Does it sound good?",
                        [
                            {"label": "Sounds great!", "value": "yes"},
                            {"label": "Pick a different voice", "value": "change"},
                            {"label": "Skip voice for now", "value": "skip"},
                        ],
                    )

                    if confirm in ("yes", "skip"):
                        voice_confirmed = True
                    else:
                        # Let them pick again
                        new_voice = await get_choice(
                            "voice-type-retry",
                            "Choose a different voice:",
                            [
                                {"label": "Female (Rachel)", "value": "female", "description": "Warm, articulate female voice"},
                                {"label": "Male (Adam)", "value": "male", "description": "Clear, confident male voice"},
                                {"label": "Custom Voice ID", "value": "custom", "description": "Enter your own ElevenLabs voice ID"},
                            ],
                        )
                        if new_voice == "custom":
                            new_id = await get_input(
                                "custom-voice-id-retry",
                                "Enter your ElevenLabs Voice ID:",
                                "text",
                                "e.g., s3TPKV1kjDlVtZbl4Ksh",
                            )
                            selected_voice_id = new_id.strip() or selected_voice_id
                            state.collected.voice_type = "custom"
                            state.collected.custom_voice_id = selected_voice_id
                        else:
                            selected_voice_id = voice_ids.get(new_voice, voice_ids["female"])
                            state.collected.voice_type = new_voice

                        # Update settings.json with new choice before re-testing
                        try:
                            with open(settings_path, "r") as f:
                                s = json.load(f)
                            if s.get("daidentity", {}).get("voices", {}).get("main"):
                                s["daidentity"]["voices"]["main"]["voiceId"] = selected_voice_id
                            if s.get("daidentity", {}).get("voices", {}).get("algorithm"):
                                s["daidentity"]["voices"]["algorithm"]["voiceId"] = selected_voice_id
                            with open(settings_path, "w") as f:
                                json.dump(s, f, indent=2)
                        except Exception:
                            pass
                else:
                    await emit({"event": "message", "content": "Voice test returned an error. Voice may need manual configuration."})
                    voice_confirmed = True
            except Exception:
                await emit({"event": "message", "content": "Voice test timed out. Server may still be initializing."})
                voice_confirmed = True

    voice_label = (
        f"Custom voice ({selected_voice_id[:8]}...)"
        if state.collected.voice_type == "custom"
        else state.collected.voice_type or "default"
    )
    await emit({"event": "message", "content": f"Digital Assistant voice configured: {voice_label}"})
    await emit({"event": "step_complete", "step": "voice"})
