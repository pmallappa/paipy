#!/usr/bin/env python3
"""PAI Migration Merger - Merges extracted content from old installations with new PAI system."""
from __future__ import annotations
import json, shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass
class MergeOptions:
    settings_strategy: str = "merge"  # keep-old | keep-new | merge
    migrate_user_content: bool = True
    migrate_personal_skills: bool = True
    migrate_agents: bool = True
    migrate_memory_state: bool = True
    migrate_plans: bool = True
    on_conflict: str = "backup"  # skip | overwrite | backup

@dataclass
class MergeResult:
    success: bool = True
    merged: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

def _deep_merge(target: dict, source: dict) -> dict:
    result = dict(target)
    for key, value in source.items():
        if value is None: continue
        if isinstance(value, dict) and not isinstance(value, list):
            result[key] = _deep_merge(result.get(key, {}), value)
        else:
            result[key] = value
    return result

def _merge_directory(source_path: str, target_path: str, on_conflict: str) -> dict:
    result = {"merged": [], "skipped": [], "conflicts": []}
    src, tgt = Path(source_path), Path(target_path)
    if not src.exists(): return result
    tgt.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(str(src), str(tgt), dirs_exist_ok=(on_conflict == "overwrite"))
        result["merged"] = [str(f.relative_to(src)) for f in src.rglob("*") if f.is_file() and f.name not in ("node_modules", ".git")]
    except Exception:
        for f in src.rglob("*"):
            if not f.is_file() or f.name in ("node_modules", ".git"): continue
            rel = str(f.relative_to(src))
            tf = tgt / rel
            if tf.exists(): result["conflicts"].append(rel)
            else: result["merged"].append(rel)
    return result

def merge_content(content, target_dir: str, options: MergeOptions = None) -> MergeResult:
    opts = options or MergeOptions()
    result = MergeResult()
    try:
        # Settings merge
        if content.settings.get("raw"):
            target_path = Path(target_dir) / "settings.json"
            try:
                target_settings = json.loads(target_path.read_text()) if target_path.exists() else {}
                if opts.settings_strategy == "keep-old":
                    final = content.settings["raw"]
                elif opts.settings_strategy == "keep-new":
                    final = {**target_settings, "principal": content.settings.get("principal") or target_settings.get("principal"),
                        "daidentity": {**target_settings.get("daidentity", {}), **(content.settings.get("daidentity") or {})}}
                else:
                    final = _deep_merge(target_settings, {"principal": content.settings.get("principal"),
                        "daidentity": content.settings.get("daidentity"), "apiKeys": content.settings.get("apiKeys")})
                final["paiVersion"] = final.get("paiVersion", "4.0.0")
                target_path.write_text(json.dumps(final, indent=2))
                result.merged.append("settings.json")
            except Exception as e:
                result.errors.append(f"settings.json: {e}"); result.success = False
        # User content
        if opts.migrate_user_content and content.user_content.get("files"):
            r = _merge_directory(content.user_content["path"], str(Path(target_dir) / "skills" / "PAI" / "USER"), opts.on_conflict)
            result.merged.extend(f"USER/{f}" for f in r["merged"])
            result.conflicts.extend(f"USER/{f}" for f in r["conflicts"])
        # Personal skills
        if opts.migrate_personal_skills:
            for skill in content.personal_skills:
                r = _merge_directory(skill["path"], str(Path(target_dir) / "skills" / skill["name"]), opts.on_conflict)
                result.merged.extend(f"skills/{skill['name']}/{f}" for f in r["merged"])
        # Agents
        if opts.migrate_agents and content.agents.get("files"):
            r = _merge_directory(content.agents["path"], str(Path(target_dir) / "agents"), opts.on_conflict)
            result.merged.extend(f"agents/{f}" for f in r["merged"])
    except Exception as e:
        result.success = False; result.errors.append(f"Merge failed: {e}")
    return result

def format_merge_result(result: MergeResult) -> str:
    lines = [f"Merge {'Successful' if result.success else 'Failed'}", ""]
    if result.merged: lines.append(f"Merged ({len(result.merged)}):" + "".join(f"\n  + {f}" for f in result.merged[:10]))
    if result.conflicts: lines.append(f"\nConflicts ({len(result.conflicts)}):" + "".join(f"\n  ! {f}" for f in result.conflicts))
    if result.errors: lines.append(f"\nErrors:" + "".join(f"\n  ! {e}" for e in result.errors))
    return "\n".join(lines)
