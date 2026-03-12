#!/usr/bin/env python3
"""PAI Migration Extractor - Extracts transferable content from existing installations."""
from __future__ import annotations
import json, shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

@dataclass
class ExtractedContent:
    settings: dict = field(default_factory=lambda: {"raw": None, "principal": None, "daidentity": None, "apiKeys": None})
    user_content: dict = field(default_factory=lambda: {"path": "", "files": [], "totalSize": 0})
    personal_skills: list[dict] = field(default_factory=list)
    agents: dict = field(default_factory=lambda: {"path": "", "files": []})
    memory_state: dict = field(default_factory=lambda: {"path": "", "files": []})
    plans: dict = field(default_factory=lambda: {"path": "", "files": []})
    hooks: dict = field(default_factory=lambda: {"path": "", "files": [], "customHooks": []})

def _list_files_relative(base: Path) -> list[str]:
    files = []
    skip = {"node_modules", ".git", "bun.lock"}
    def walk(d: Path):
        if not d.exists(): return
        try:
            for entry in d.iterdir():
                if entry.name in skip: continue
                if entry.is_dir(): walk(entry)
                elif entry.is_file(): files.append(str(entry.relative_to(base)))
        except PermissionError: pass
    walk(base)
    return files

def _calc_dir_size(path: Path) -> int:
    total = 0
    skip = {"node_modules", ".git"}
    def walk(d: Path):
        nonlocal total
        if not d.exists(): return
        try:
            for entry in d.iterdir():
                if entry.name in skip: continue
                if entry.is_dir(): walk(entry)
                elif entry.is_file(): total += entry.stat().st_size
        except PermissionError: pass
    walk(path)
    return total

def extract_content(source) -> ExtractedContent:
    result = ExtractedContent()
    if not source.exists: return result
    src = Path(source.path)
    # Settings
    settings_path = src / "settings.json"
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
            result.settings["raw"] = settings
            if settings.get("principal"):
                result.settings["principal"] = {"name": settings["principal"].get("name"), "timezone": settings["principal"].get("timezone")}
            if settings.get("daidentity"):
                result.settings["daidentity"] = {"name": settings["daidentity"].get("name"), "mainDAVoiceID": settings["daidentity"].get("mainDAVoiceID")}
            result.settings["apiKeys"] = {"elevenlabs": settings.get("apiKeys", {}).get("elevenlabs"), "anthropic": settings.get("apiKeys", {}).get("anthropic")}
        except Exception: pass
    # USER content
    user_path = src / "skills" / "PAI" / "USER"
    if user_path.exists():
        result.user_content = {"path": str(user_path), "files": _list_files_relative(user_path), "totalSize": _calc_dir_size(user_path)}
    # Personal skills
    for name in getattr(source, "components", type("", (), {"personal_skills": []})).personal_skills:
        sp = src / "skills" / name
        if sp.exists(): result.personal_skills.append({"name": name, "path": str(sp), "files": _list_files_relative(sp)})
    # Agents
    agents_path = src / "agents"
    if agents_path.exists(): result.agents = {"path": str(agents_path), "files": _list_files_relative(agents_path)}
    # Memory
    state_path = src / "MEMORY" / "STATE"
    if state_path.exists(): result.memory_state = {"path": str(state_path), "files": _list_files_relative(state_path)}
    # Plans
    plans_path = src / "Plans"
    if plans_path.exists(): result.plans = {"path": str(plans_path), "files": _list_files_relative(plans_path)}
    # Hooks
    hooks_path = src / "hooks"
    if hooks_path.exists(): result.hooks = {"path": str(hooks_path), "files": _list_files_relative(hooks_path), "customHooks": []}
    return result

def copy_extracted_content(content: ExtractedContent, target_dir: str, **opts) -> None:
    defaults = {"includeUserContent": True, "includePersonalSkills": True, "includeAgents": True, "includeMemoryState": True, "includePlans": True, "includeHooks": False}
    defaults.update(opts)
    target = Path(target_dir)
    if defaults["includeUserContent"] and content.user_content["files"]:
        dest = target / "skills" / "PAI" / "USER"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(content.user_content["path"], dest, dirs_exist_ok=True)
    if defaults["includePersonalSkills"]:
        for skill in content.personal_skills:
            dest = target / "skills" / skill["name"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(skill["path"], dest, dirs_exist_ok=True)
    if defaults["includeAgents"] and content.agents["files"]:
        dest = target / "agents"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(content.agents["path"], dest, dirs_exist_ok=True)

def format_extracted_content(content: ExtractedContent) -> str:
    lines = ["Extracted Content:"]
    if content.settings.get("principal", {}).get("name"): lines.append(f"  Principal: {content.settings['principal']['name']}")
    if content.settings.get("daidentity", {}).get("name"): lines.append(f"  AI Identity: {content.settings['daidentity']['name']}")
    if content.user_content["files"]: lines.append(f"  USER content: {len(content.user_content['files'])} files")
    if content.personal_skills: lines.append(f"  Personal skills: {', '.join(s['name'] for s in content.personal_skills)}")
    if content.agents["files"]: lines.append(f"  Agents: {len(content.agents['files'])} configurations")
    return "\n".join(lines)
