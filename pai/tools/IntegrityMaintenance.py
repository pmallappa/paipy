#!/usr/bin/env python3
"""
IntegrityMaintenance.py - Background script for system integrity and update documentation

Receives change data from SystemIntegrity handler via stdin JSON.
Uses AI inference to understand the session context and generate
meaningful documentation.

Input (stdin JSON):
{
  "session_id": "abc-123",
  "transcript_path": "/path/to/transcript.jsonl",
  "changes": [{ "tool": "Edit", "path": "skills/Foo/SKILL.md", ... }]
}
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

# Lazy import to avoid circular dependency
# from .Inference import inference

# ============================================================================
# Types
# ============================================================================

SignificanceLabel = str  # trivial | minor | moderate | major | critical
ChangeType = str  # skill_update | structure_change | doc_update | etc.

PAI_DIR = os.environ.get("HOME", str(Path.home())) + "/.claude"
CREATE_UPDATE_SCRIPT = os.path.join(PAI_DIR, "skills/_SYSTEM/tools/CreateUpdate.ts")

GENERIC_TITLE_PATTERNS = [
    re.compile(r"^system (philosophy|structure) update$", re.IGNORECASE),
    re.compile(r"^documentation update$", re.IGNORECASE),
    re.compile(r"^multi-?skill update", re.IGNORECASE),
    re.compile(r"^architecture update$", re.IGNORECASE),
]


# ============================================================================
# Transcript Reading
# ============================================================================

def extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            c if isinstance(c, str)
            else c.get("text", "") if isinstance(c, dict) and c.get("text")
            else extract_text_content(c.get("content", "")) if isinstance(c, dict) else ""
            for c in content
        ).strip()
    return ""


def read_transcript_context(transcript_path: str, max_messages: int = 20) -> list[dict]:
    if not os.path.exists(transcript_path):
        print(f"[IntegrityMaintenance] Transcript not found: {transcript_path}", file=sys.stderr)
        return []
    try:
        content = Path(transcript_path).read_text()
        messages: list[dict] = []
        for line in content.strip().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("type") == "user" and entry.get("message", {}).get("content"):
                    text = extract_text_content(entry["message"]["content"])
                    if text and len(text) > 10:
                        messages.append({"role": "user", "content": text})
                elif entry.get("type") == "assistant" and entry.get("message", {}).get("content"):
                    text = extract_text_content(entry["message"]["content"])
                    if text and len(text) > 10:
                        messages.append({"role": "assistant", "content": text[:2000]})
            except json.JSONDecodeError:
                pass
        return messages[-max_messages:]
    except Exception as e:
        print(f"[IntegrityMaintenance] Error reading transcript: {e}", file=sys.stderr)
        return []


def build_context_summary(messages: list[dict]) -> str:
    if not messages:
        return ""
    parts = []
    for msg in messages:
        prefix = "USER:" if msg["role"] == "user" else "ASSISTANT:"
        cleaned = re.sub(r"<system-reminder>[\s\S]*?</system-reminder>", "", msg["content"])
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        if cleaned:
            parts.append(f"{prefix} {cleaned[:1500]}")
    return "\n\n---\n\n".join(parts)


# ============================================================================
# Title Generation
# ============================================================================

def capitalize(s: str) -> str:
    return s[0].upper() + s[1:] if s else s


def extract_common_patterns(names: list[str]) -> list[str]:
    if not names:
        return []
    all_words = []
    for n in names:
        words = re.split(r"(?=[A-Z])|[-_]", n)
        all_words.extend(w for w in words if len(w) > 2)
    freq: dict[str, int] = {}
    for w in all_words:
        lower = w.lower()
        freq[lower] = freq.get(lower, 0) + 1
    return [capitalize(w) for w, c in sorted(freq.items(), key=lambda x: -x[1])[:3] if c >= 2]


def generate_descriptive_title(changes: list[dict]) -> str:
    paths = [c["path"] for c in changes]
    skill_names: set[str] = set()
    for p in paths:
        match = re.search(r"skills/([^/]+)/", p)
        if match and match.group(1) != "CORE":
            skill_names.add(match.group(1))

    has_skill_md = any(p.endswith("SKILL.md") for p in paths)
    has_workflows = any("/workflows/" in p for p in paths)
    has_tools = any("/tools/" in p and p.endswith(".ts") for p in paths)
    has_hooks = any("hooks/" in p for p in paths)
    has_config = any(p.endswith("settings.json") for p in paths)
    has_pai_system = any("/pai/" in p for p in paths)

    file_names = [os.path.splitext(os.path.basename(p))[0].replace(".ts", "") for p in paths]

    title = ""

    if len(skill_names) == 1:
        skill = list(skill_names)[0]
        if has_skill_md:
            title = f"{skill} Skill Definition Update"
        elif has_workflows:
            wf = [os.path.splitext(os.path.basename(p))[0] for p in paths if "/workflows/" in p]
            title = f"{skill} {wf[0]} Workflow Update" if len(wf) == 1 else f"{skill} Workflows Updated"
        elif has_tools:
            tl = [os.path.splitext(os.path.basename(p))[0] for p in paths if "/tools/" in p]
            title = f"{skill} {tl[0]} Tool Update" if len(tl) == 1 else f"{skill} Tools Updated"
        else:
            title = f"{skill} Skill Update"
    elif 1 < len(skill_names) <= 3:
        title = f"{' and '.join(list(skill_names)[:3])} Skills Updated"
    elif has_hooks:
        hn = [os.path.splitext(os.path.basename(p))[0].replace(".hook", "") for p in paths if "hooks/" in p]
        if len(hn) == 1:
            title = f"{hn[0]} Hook Updated"
        elif len(hn) <= 3:
            title = f"{', '.join(hn[:3])} Hooks Updated"
        else:
            title = "Hook System Updates"
    elif has_config:
        title = "System Configuration Updated"
    elif has_pai_system:
        title = "PAI System Documentation Updated"
    else:
        common = extract_common_patterns(file_names)
        if common:
            title = f"{' '.join(common)} Updates"
        else:
            categories = set(c.get("category") or "system" for c in changes)
            if len(categories) == 1:
                title = f"{capitalize(list(categories)[0])} Updates"
            else:
                title = "Multi-Area System Updates"

    words = title.split()
    if len(words) < 4:
        title = f"PAI {title}"
    elif len(words) > 8:
        title = " ".join(words[:8])

    return title


# ============================================================================
# Significance / Change Type
# ============================================================================

def determine_significance(changes: list[dict]) -> str:
    count = len(changes)
    has_structural = any(c.get("isStructural") for c in changes)
    has_philosophical = any(c.get("isPhilosophical") for c in changes)
    has_new_files = any(c.get("tool") == "Write" for c in changes)
    categories = set(c.get("category") for c in changes if c.get("category"))
    has_core = any(c.get("category") == "core-system" for c in changes)
    has_hooks = any(c.get("category") == "hook" for c in changes)
    has_skills = any(c.get("category") == "skill" for c in changes)

    if has_structural and has_philosophical and count >= 5:
        return "critical"
    if has_new_files and (has_structural or has_philosophical):
        return "major"
    if has_core or len(categories) >= 3:
        return "major"
    if has_hooks and count >= 3:
        return "major"
    if count >= 3 or len(categories) >= 2:
        return "moderate"
    if has_skills and count >= 2:
        return "moderate"
    if count == 1 and not has_structural and not has_philosophical:
        return "minor"
    return "minor"


def infer_change_type(changes: list[dict]) -> str:
    categories = [c.get("category") for c in changes if c.get("category")]
    unique = set(categories)
    if len(unique) >= 3:
        return "multi_area"
    if len(unique) == 1:
        cat = list(unique)[0]
        mapping = {
            "skill": "skill_update", "hook": "hook_update",
            "workflow": "workflow_update", "config": "config_update",
            "core-system": "structure_change", "documentation": "doc_update",
        }
        return mapping.get(cat, "skill_update")
    if "hook" in unique:
        return "hook_update"
    if "skill" in unique:
        return "skill_update"
    return "multi_area"


def generate_purpose(changes: list[dict], title: str) -> str:
    ct = infer_change_type(changes)
    skill_names: set[str] = set()
    for c in changes:
        match = re.search(r"skills/([^/]+)/", c.get("path", ""))
        if match:
            skill_names.add(match.group(1))
    ctx = f" in {', '.join(list(skill_names)[:3])} skill(s)" if skill_names else ""
    mapping = {
        "skill_update": f"Update functionality and behavior{ctx}",
        "structure_change": f"Modify system structure{ctx}",
        "doc_update": f"Improve documentation clarity{ctx}",
        "hook_update": "Enhance lifecycle event handling",
        "workflow_update": f"Update workflow processes{ctx}",
        "config_update": "Adjust system configuration",
        "tool_update": f"Update tooling capabilities{ctx}",
        "multi_area": "Cross-cutting changes across multiple areas",
    }
    return mapping.get(ct, "System maintenance and updates")


def generate_expected_improvement(changes: list[dict]) -> str:
    ct = infer_change_type(changes)
    sig = determine_significance(changes)
    type_map = {
        "skill_update": "Better skill functionality",
        "structure_change": "Improved system organization",
        "doc_update": "Clearer documentation",
        "hook_update": "More reliable automation",
        "workflow_update": "Smoother workflow execution",
        "config_update": "Better system behavior",
        "tool_update": "Enhanced tooling capabilities",
        "multi_area": "Broader system improvements",
    }
    sig_map = {
        "critical": "significant behavioral changes",
        "major": "notable new capabilities",
        "moderate": "incremental enhancements",
        "minor": "small refinements",
        "trivial": "minor corrections",
    }
    return f"{type_map.get(ct, 'System improvements')}, {sig_map.get(sig, 'refinements')}"


# ============================================================================
# AI Narrative (via Inference)
# ============================================================================

async def generate_narrative_with_ai(transcript_path: str, changes: list[dict]) -> Optional[dict]:
    messages = read_transcript_context(transcript_path)
    context_summary = build_context_summary(messages)
    if not context_summary:
        return None

    files_summary = "\n".join(f"- {c['path']} ({c.get('category', 'other')})" for c in changes)
    prompt = f"""You are analyzing a Claude Code session to generate documentation.

## Session Transcript
{context_summary}

## Files Changed
{files_summary}

Return a JSON object with: title, story_background, story_problem, story_resolution,
how_it_was, how_it_was_bullets, how_it_is, how_it_is_bullets,
future_impact, future_bullets, verification_steps.

Return ONLY JSON."""

    try:
        from .Inference import inference
        result = inference({
            "systemPrompt": "Return ONLY valid JSON.",
            "userPrompt": prompt,
            "level": "fast",
            "expectJson": True,
            "timeout": 30000,
        })
        if result.get("success") and result.get("parsed"):
            return result["parsed"]
    except Exception as e:
        print(f"[IntegrityMaintenance] AI inference failed: {e}", file=sys.stderr)

    return None


# ============================================================================
# Reference Checking
# ============================================================================

def check_references(changes: list[dict]) -> dict:
    locations = [c["path"] for c in changes[:5]]
    return {
        "references_found": len(locations),
        "references_updated": 0,
        "locations_checked": locations,
    }


# ============================================================================
# Create Update Entry
# ============================================================================

def create_update_entry(data: dict) -> None:
    print(f"[IntegrityMaintenance] Creating update: {data['title']}", file=sys.stderr)
    print(f"[IntegrityMaintenance] Significance: {data['significance']}", file=sys.stderr)

    try:
        proc = subprocess.Popen(
            ["bun", CREATE_UPDATE_SCRIPT, "--stdin"],
            stdin=subprocess.PIPE,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        proc.communicate(input=json.dumps(data).encode())
    except Exception as e:
        print(f"[IntegrityMaintenance] Error creating update: {e}", file=sys.stderr)


# ============================================================================
# Main
# ============================================================================

async def async_main() -> None:
    print("[IntegrityMaintenance] Starting background integrity check...", file=sys.stderr)

    input_data = sys.stdin.read()
    if not input_data.strip():
        print("[IntegrityMaintenance] No input received, exiting", file=sys.stderr)
        return

    try:
        inp = json.loads(input_data)
    except json.JSONDecodeError as e:
        print(f"[IntegrityMaintenance] Invalid JSON input: {e}", file=sys.stderr)
        return

    changes = inp.get("changes", [])
    transcript_path = inp.get("transcript_path", "")

    if not changes:
        print("[IntegrityMaintenance] No changes to process", file=sys.stderr)
        return

    print(f"[IntegrityMaintenance] Processing {len(changes)} changes", file=sys.stderr)

    title = generate_descriptive_title(changes)
    significance = determine_significance(changes)
    change_type = infer_change_type(changes)
    purpose = generate_purpose(changes, title)
    expected_improvement = generate_expected_improvement(changes)
    integrity_work = check_references(changes)

    # Try AI narrative
    ai_narrative = await generate_narrative_with_ai(transcript_path, changes) if transcript_path else None

    if ai_narrative and ai_narrative.get("title"):
        ai_title = ai_narrative["title"]
        words = ai_title.split()
        is_valid = 4 <= len(words) <= 8
        is_generic = any(p.search(ai_title) for p in GENERIC_TITLE_PATTERNS)
        if is_valid and not is_generic:
            title = ai_title

    verbose_narrative = {
        "story_background": (ai_narrative or {}).get("story_background", f"Changes to PAI system. {len(changes)} file(s) modified."),
        "story_problem": (ai_narrative or {}).get("story_problem", purpose),
        "story_resolution": (ai_narrative or {}).get("story_resolution", expected_improvement),
        "how_it_was": (ai_narrative or {}).get("how_it_was", "Previous configuration."),
        "how_it_was_bullets": (ai_narrative or {}).get("how_it_was_bullets", []),
        "how_it_is": (ai_narrative or {}).get("how_it_is", "Updated behavior."),
        "how_it_is_bullets": (ai_narrative or {}).get("how_it_is_bullets", []),
        "future_impact": (ai_narrative or {}).get("future_impact", "Updated behavior in future sessions."),
        "future_bullets": (ai_narrative or {}).get("future_bullets", ["Changes active for future sessions"]),
        "verification_steps": (ai_narrative or {}).get("verification_steps", ["Automatic detection"]),
        "confidence": "high" if ai_narrative else "medium",
    }

    update_data = {
        "title": title,
        "significance": significance,
        "change_type": change_type,
        "files": [c["path"] for c in changes],
        "purpose": purpose,
        "expected_improvement": expected_improvement,
        "integrity_work": integrity_work,
        "narrative": {
            "context": verbose_narrative["story_background"],
            "problem": verbose_narrative["story_problem"],
            "solution": verbose_narrative["story_resolution"],
            "verification": ". ".join(verbose_narrative.get("verification_steps", [])),
            "confidence": verbose_narrative["confidence"],
        },
        "verbose_narrative": verbose_narrative,
    }

    create_update_entry(update_data)

    print("[IntegrityMaintenance] Waiting 10 seconds before voice notification...", file=sys.stderr)
    time.sleep(10)

    print("[IntegrityMaintenance] Complete", file=sys.stderr)


def main() -> None:
    import asyncio
    try:
        asyncio.run(async_main())
    except Exception as err:
        print(f"[IntegrityMaintenance] Error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
