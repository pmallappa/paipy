#!/usr/bin/env python3
"""PAI Migration Scanner - Detects existing PAI installations."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

HOME = Path.home()
STANDARD_LOCATIONS = [HOME / ".claude", HOME / ".claude-BACKUP", HOME / ".claude-old"]

@dataclass
class InstallationComponents:
    settings: bool = False
    skills: bool = False
    core_skill: bool = False
    user_content: bool = False
    personal_skills: list[str] = field(default_factory=list)
    agents: bool = False
    agent_count: int = 0
    memory: bool = False
    hooks: bool = False
    hook_count: int = 0

@dataclass
class InstallationStats:
    total_files: int = 0
    total_size: int = 0
    skill_count: int = 0

@dataclass
class InstallationInfo:
    path: str
    exists: bool
    is_complete: bool = False
    version: Optional[str] = None
    components: InstallationComponents = field(default_factory=InstallationComponents)
    stats: InstallationStats = field(default_factory=InstallationStats)

def _calculate_stats(path: Path) -> InstallationStats:
    total_files, total_size, skill_count = 0, 0, 0
    skip = {"node_modules", ".git", "bun.lock"}
    def walk(d: Path):
        nonlocal total_files, total_size
        if not d.exists(): return
        try:
            for entry in d.iterdir():
                if entry.name in skip: continue
                if entry.is_dir(): walk(entry)
                elif entry.is_file():
                    total_files += 1
                    total_size += entry.stat().st_size
        except PermissionError: pass
    walk(path)
    skills_dir = path / "skills"
    if skills_dir.exists():
        try: skill_count = sum(1 for s in skills_dir.iterdir() if s.is_dir())
        except Exception: pass
    return InstallationStats(total_files=total_files, total_size=total_size, skill_count=skill_count)

def scan_installation(path_str: str) -> InstallationInfo:
    path = Path(path_str)
    info = InstallationInfo(path=str(path), exists=path.exists())
    if not info.exists: return info
    settings_path = path / "settings.json"
    if settings_path.exists():
        info.components.settings = True
        try:
            settings = json.loads(settings_path.read_text())
            info.version = settings.get("paiVersion") or settings.get("version")
        except Exception: pass
    skills_dir = path / "skills"
    if skills_dir.exists():
        info.components.skills = True
        try:
            skills = [s.name for s in skills_dir.iterdir() if s.is_dir()]
            info.stats.skill_count = len(skills)
            info.components.personal_skills = [s for s in skills if s.startswith("_") and s == s.upper()]
            info.components.core_skill = (skills_dir / "PAI" / "SKILL.md").exists()
            info.components.user_content = (skills_dir / "PAI" / "USER").exists()
        except Exception: pass
    agents_dir = path / "agents"
    if agents_dir.exists():
        info.components.agents = True
        try: info.components.agent_count = len(list(agents_dir.iterdir()))
        except Exception: pass
    info.components.memory = (path / "MEMORY").exists()
    hooks_dir = path / "hooks"
    if hooks_dir.exists():
        info.components.hooks = True
        try: info.components.hook_count = sum(1 for f in hooks_dir.iterdir() if f.suffix in (".ts", ".py"))
        except Exception: pass
    info.stats = _calculate_stats(path)
    info.is_complete = info.components.settings and info.components.core_skill and info.components.skills
    return info

def find_installations() -> list[InstallationInfo]:
    return [info for info in (scan_installation(str(loc)) for loc in STANDARD_LOCATIONS) if info.exists]

def find_best_migration_source() -> Optional[InstallationInfo]:
    installations = find_installations()
    if not installations: return None
    def sort_key(inst):
        return (inst.components.user_content, len(inst.components.personal_skills) > 0, inst.is_complete, inst.stats.total_files)
    installations.sort(key=sort_key, reverse=True)
    return installations[0]

def format_installation_info(info: InstallationInfo) -> str:
    lines = [f"Installation: {info.path}", f"  Version: {info.version or 'Unknown'}",
        f"  Complete: {'Yes' if info.is_complete else 'No'}", "  Components:",
        f"    - settings.json: {'Yes' if info.components.settings else 'No'}",
        f"    - PAI skill: {'Yes' if info.components.core_skill else 'No'}",
        f"    - USER content: {'Yes' if info.components.user_content else 'No'}",
        f"    - Skills: {info.stats.skill_count}", f"    - Agents: {info.components.agent_count}",
        f"    - Hooks: {info.components.hook_count}",
        f"  Stats: {info.stats.total_files} files, {_fmt_bytes(info.stats.total_size)}"]
    return "\n".join(lines)

def _fmt_bytes(b: int) -> str:
    if b < 1024: return f"{b} B"
    if b < 1024*1024: return f"{b/1024:.1f} KB"
    return f"{b/1024/1024:.1f} MB"
