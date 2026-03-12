#!/usr/bin/env python3
"""
doc_cross_ref_integrity.py -- Hybrid doc integrity checker (deterministic + inference).

Two-layer approach:
Layer 1 (Deterministic): Grep-based pattern checks for broken refs, counts, timestamps
Layer 2 (Inference): AI analysis of semantic drift (stubbed -- requires Inference tool)

TRIGGER: Stop hook (via doc_integrity entry point)

PATTERN TYPES CHECKED (deterministic):
1. Hook file references (*.hook.ts) - diff against disk
2. Handler file references (handlers/*.ts) - diff against disk
3. Shared lib references (hooks/lib/*.ts) - diff against disk
4. SYSTEM doc path references - validate files exist
5. Numeric counts (e.g., "21 hooks active") - recount from disk
6. Last Updated timestamps - update on modification

AUDIT TRAIL: All operations logged to stderr via [DocAutoUpdate] prefix
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from paipy import memory

# Resolve paths
_pai_dir: Optional[str] = None


def _get_pai_dir() -> str:
    global _pai_dir
    if _pai_dir is None:
        raw = os.environ.get("PAI_DIR", os.path.join(str(Path.home()), ".claude"))
        _pai_dir = os.path.expandvars(raw).replace("~", str(Path.home()))
    return _pai_dir


def _pai_path(*segments: str) -> str:
    return os.path.join(_get_pai_dir(), *segments)


TAG = "[DocAutoUpdate]"


# Filesystem Inventory

def _list_files(directory: str, suffix: str) -> List[str]:
    try:
        if not os.path.isdir(directory):
            return []
        return sorted(f for f in os.listdir(directory) if f.endswith(suffix))
    except Exception:
        return []


def _get_hook_files_on_disk() -> List[str]:
    return _list_files(_pai_path("hooks"), ".hook.ts")


def _get_handler_files_on_disk() -> List[str]:
    return _list_files(os.path.join(_pai_path("hooks"), "handlers"), ".ts")


def _get_lib_files_on_disk() -> List[str]:
    return _list_files(os.path.join(_pai_path("hooks"), "lib"), ".ts")


def _get_system_docs_on_disk() -> List[str]:
    return _list_files(_pai_path("PAI"), ".md")


# Transcript Parsing

def _get_modified_files(transcript_path: str) -> Set[str]:
    modified: Set[str] = set()
    try:
        content = Path(transcript_path).read_text()
        for line in content.split("\n"):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("type") == "tool_use" and entry.get("name") in ("Write", "Edit"):
                    path = entry.get("input", {}).get("file_path", "")
                    if path:
                        modified.add(path)
                if entry.get("type") == "assistant" and entry.get("message", {}).get("content"):
                    blocks = entry["message"]["content"]
                    if not isinstance(blocks, list):
                        blocks = []
                    for block in blocks:
                        if block.get("type") == "tool_use" and block.get("name") in ("Write", "Edit"):
                            path = block.get("input", {}).get("file_path", "")
                            if path:
                                modified.add(path)
            except Exception:
                pass
    except Exception as e:
        print(f"{TAG} Failed to parse transcript: {e}", file=sys.stderr)
    return modified


def _is_system_doc_modified(modified_files: Set[str]) -> bool:
    return any("pai/" in p and p.endswith(".md") for p in modified_files)


def _is_hook_modified(modified_files: Set[str]) -> bool:
    return any("/hooks/" in p and p.endswith(".ts") for p in modified_files)


def _is_system_file_modified(modified_files: Set[str]) -> bool:
    pai_dir = _get_pai_dir()
    excluded = [
        "memory/work/", "memory/learning/", "memory/state/", "plans/",
        "projects/", ".git/", "node_modules/", "ShellSnapshots/", "Projects/",
        "memory/voice/", "memory/relationship/", "history.jsonl", ".quote-cache",
    ]

    for file_path in modified_files:
        rel_path = file_path[len(pai_dir) + 1:] if file_path.startswith(pai_dir) else file_path
        if file_path.startswith("/") and not file_path.startswith(pai_dir):
            continue
        if any(ex in rel_path for ex in excluded):
            continue
        if (rel_path.startswith("pai/") or "skills/" in rel_path) and any(
            rel_path.endswith(ext) for ext in (".md", ".ts", ".yaml", ".yml")
        ):
            return True
        if "hooks/" in rel_path and rel_path.endswith(".ts"):
            return True
        if rel_path.endswith("settings.json"):
            return True
        if "pai/algorithm/" in rel_path and rel_path.endswith(".md"):
            return True
        if "/tools/" in rel_path and rel_path.endswith(".ts"):
            return True
        if "/workflows/" in rel_path and rel_path.endswith(".md"):
            return True
        if rel_path.startswith("agents/") and rel_path.endswith(".md"):
            return True
        if rel_path == "CLAUDE.md":
            return True
        if rel_path.startswith("custom-agents/") and rel_path.endswith(".md"):
            return True
    return False


# Pattern Checkers

def _check_hook_file_refs(docs_to_check: List[str], hooks_on_disk: Set[str]) -> List[Dict[str, str]]:
    drift: List[Dict[str, str]] = []
    system_dir = _pai_path("PAI")

    for doc_file in docs_to_check:
        doc_path = os.path.join(system_dir, doc_file)
        if not os.path.exists(doc_path):
            continue
        content = Path(doc_path).read_text()
        for match in re.finditer(r"(\w+)\.hook\.ts", content):
            hook_name = match.group(0)
            if hook_name not in hooks_on_disk:
                drift.append({
                    "doc": doc_file,
                    "pattern": "hook_file_ref",
                    "reference": hook_name,
                    "issue": f'References "{hook_name}" but file does not exist on disk',
                })
    return drift


def _check_handler_file_refs(docs_to_check: List[str], handlers_on_disk: Set[str]) -> List[Dict[str, str]]:
    drift: List[Dict[str, str]] = []
    system_dir = _pai_path("PAI")

    for doc_file in docs_to_check:
        doc_path = os.path.join(system_dir, doc_file)
        if not os.path.exists(doc_path):
            continue
        content = Path(doc_path).read_text()
        for match in re.finditer(r"handlers/(\w+)\.ts", content):
            handler_filename = f"{match.group(1)}.ts"
            if handler_filename not in handlers_on_disk:
                drift.append({
                    "doc": doc_file,
                    "pattern": "handler_file_ref",
                    "reference": match.group(0),
                    "issue": f'References "{match.group(0)}" but "{handler_filename}" does not exist in handlers/',
                })
    return drift


def _check_lib_file_refs(docs_to_check: List[str], libs_on_disk: Set[str]) -> List[Dict[str, str]]:
    drift: List[Dict[str, str]] = []
    system_dir = _pai_path("PAI")

    for doc_file in docs_to_check:
        doc_path = os.path.join(system_dir, doc_file)
        if not os.path.exists(doc_path):
            continue
        content = Path(doc_path).read_text()
        for match in re.finditer(r"hooks/lib/([\w-]+)\.ts", content):
            lib_filename = f"{match.group(1)}.ts"
            if lib_filename not in libs_on_disk:
                drift.append({
                    "doc": doc_file,
                    "pattern": "lib_file_ref",
                    "reference": match.group(0),
                    "issue": f'References "{match.group(0)}" but "{lib_filename}" does not exist in hooks/lib/',
                })
    return drift


def _check_system_doc_refs(docs_to_check: List[str], system_docs_on_disk: Set[str]) -> List[Dict[str, str]]:
    drift: List[Dict[str, str]] = []
    system_dir = _pai_path("PAI")

    for doc_file in docs_to_check:
        doc_path = os.path.join(system_dir, doc_file)
        if not os.path.exists(doc_path):
            continue
        content = Path(doc_path).read_text()
        for match in re.finditer(r"""(?:[`'"])(?:~/\.claude/)?(?:skills/)?pai/([\w/]+\.md)(?:[`'"])""", content):
            ref_target = match.group(1)
            target_path = os.path.join(system_dir, ref_target)
            if not os.path.exists(target_path):
                drift.append({
                    "doc": doc_file,
                    "pattern": "system_doc_ref",
                    "reference": f"pai/{ref_target}",
                    "issue": f'References "pai/{ref_target}" but file does not exist',
                })
    return drift


def _check_hook_counts(docs_to_check: List[str], actual_count: int) -> List[Dict[str, str]]:
    drift: List[Dict[str, str]] = []
    system_dir = _pai_path("PAI")

    for doc_file in docs_to_check:
        doc_path = os.path.join(system_dir, doc_file)
        if not os.path.exists(doc_path):
            continue
        content = Path(doc_path).read_text()
        for match in re.finditer(r"\*\*Status:\*\*.*?(\d+) hooks? active", content):
            doc_count = int(match.group(1))
            if doc_count != actual_count:
                drift.append({
                    "doc": doc_file,
                    "pattern": "hook_count",
                    "reference": match.group(0),
                    "issue": f'States "{doc_count} hooks active" but actual count on disk is {actual_count}',
                })
    return drift


# Review Queue

def _add_to_review_queue(drift_items: List[Dict[str, str]]) -> None:
    if not drift_items:
        return

    review_queue_file = str(memory("STATE") / "doc-review-queue.json")
    queue: List[Dict[str, str]] = []
    try:
        if os.path.exists(review_queue_file):
            queue = json.loads(Path(review_queue_file).read_text())
    except Exception:
        queue = []

    now = datetime.utcnow().isoformat() + "Z"
    new_items = [
        {
            "timestamp": now,
            "type": item["pattern"],
            "description": item["issue"],
            "doc": item["doc"],
            "reference": item["reference"],
        }
        for item in drift_items
    ]

    queue.extend(new_items)
    if len(queue) > 50:
        queue = queue[-50:]

    dir_path = os.path.dirname(review_queue_file)
    os.makedirs(dir_path, exist_ok=True)
    Path(review_queue_file).write_text(json.dumps(queue, indent=2))
    print(f"{TAG} Added {len(new_items)} item(s) to review queue: {review_queue_file}", file=sys.stderr)


# Deterministic Updates

def _update_last_updated_timestamp(doc_file: str) -> Optional[str]:
    system_dir = _pai_path("PAI")
    doc_path = os.path.join(system_dir, doc_file)
    if not os.path.exists(doc_path):
        return None

    content = Path(doc_path).read_text()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    pattern = re.compile(r"(\*\*Last Updated:\*\* )\d{4}-\d{2}-\d{2}")

    match = pattern.search(content)
    if match and f"**Last Updated:** {today}" not in content:
        updated = pattern.sub(f"\\g<1>{today}", content)
        Path(doc_path).write_text(updated)
        return f"Updated 'Last Updated' in {doc_file}: {match.group(0)} -> **Last Updated:** {today}"
    return None


def _update_hook_count(actual_count: int) -> Optional[str]:
    doc_path = os.path.join(_pai_path("PAI"), "THEHOOKSYSTEM.md")
    if not os.path.exists(doc_path):
        return None

    content = Path(doc_path).read_text()
    pattern = re.compile(r"(\*\*Status:\*\* Production - )\d+( hooks? active)")

    match = pattern.search(content)
    if match:
        old_match = re.search(r"\*\*Status:\*\* Production - (\d+)", content)
        old_count = int(old_match.group(1)) if old_match else 0
        if old_count != actual_count:
            updated = pattern.sub(f"\\g<1>{actual_count}\\g<2>", content)
            Path(doc_path).write_text(updated)
            return f"Updated hook count in THEHOOKSYSTEM.md: {old_count} -> {actual_count}"
    return None


# Main Handler

def handle_doc_cross_ref_integrity(
    transcript_path: str,
    session_id: str,
) -> None:
    """Run hybrid doc integrity check."""
    import time
    handler_start = time.time()
    print(f"{TAG} === Starting hybrid doc integrity check (deterministic) ===", file=sys.stderr)

    # Step 1: Parse transcript for modified files
    modified_files = _get_modified_files(transcript_path)
    print(f"{TAG} Modified files in session: {len(modified_files)}", file=sys.stderr)

    has_doc_changes = _is_system_doc_modified(modified_files)
    has_hook_changes = _is_hook_modified(modified_files)
    has_any_system_change = _is_system_file_modified(modified_files)

    if not has_any_system_change:
        print(f"{TAG} No meaningful system files modified, skipping", file=sys.stderr)
        return

    print(f"{TAG} System docs modified: {has_doc_changes}", file=sys.stderr)
    print(f"{TAG} Hook files modified: {has_hook_changes}", file=sys.stderr)

    # Step 2: Build filesystem inventory
    hooks_on_disk = set(_get_hook_files_on_disk())
    handlers_on_disk = set(_get_handler_files_on_disk())
    libs_on_disk = set(_get_lib_files_on_disk())
    system_docs_on_disk = set(_get_system_docs_on_disk())

    print(
        f"{TAG} Inventory: {len(hooks_on_disk)} hooks, {len(handlers_on_disk)} handlers, "
        f"{len(libs_on_disk)} libs, {len(system_docs_on_disk)} system docs",
        file=sys.stderr,
    )

    docs_to_check = list(system_docs_on_disk)
    print(f"{TAG} Checking {len(docs_to_check)} SYSTEM docs for cross-reference drift", file=sys.stderr)

    # Step 3: Run all pattern checks
    all_drift: List[Dict[str, str]] = []

    hook_drift = _check_hook_file_refs(docs_to_check, hooks_on_disk)
    if hook_drift:
        print(f"{TAG} [DRIFT] Hook file references: {len(hook_drift)} broken refs found", file=sys.stderr)
        all_drift.extend(hook_drift)
    else:
        print(f"{TAG} [OK] Hook file references: all valid", file=sys.stderr)

    handler_drift = _check_handler_file_refs(docs_to_check, handlers_on_disk)
    if handler_drift:
        print(f"{TAG} [DRIFT] Handler file references: {len(handler_drift)} broken refs found", file=sys.stderr)
        all_drift.extend(handler_drift)
    else:
        print(f"{TAG} [OK] Handler file references: all valid", file=sys.stderr)

    lib_drift = _check_lib_file_refs(docs_to_check, libs_on_disk)
    if lib_drift:
        print(f"{TAG} [DRIFT] Lib file references: {len(lib_drift)} broken refs found", file=sys.stderr)
        all_drift.extend(lib_drift)
    else:
        print(f"{TAG} [OK] Lib file references: all valid", file=sys.stderr)

    sys_doc_drift = _check_system_doc_refs(docs_to_check, system_docs_on_disk)
    if sys_doc_drift:
        print(f"{TAG} [DRIFT] System doc references: {len(sys_doc_drift)} broken refs found", file=sys.stderr)
        all_drift.extend(sys_doc_drift)
    else:
        print(f"{TAG} [OK] System doc references: all valid", file=sys.stderr)

    hook_count_drift = _check_hook_counts(docs_to_check, len(hooks_on_disk))
    if hook_count_drift:
        print(f"{TAG} [DRIFT] Hook counts: {len(hook_count_drift)} mismatches found", file=sys.stderr)
        all_drift.extend(hook_count_drift)
    else:
        print(f"{TAG} [OK] Hook counts: accurate", file=sys.stderr)

    # Step 4: Apply safe deterministic updates
    updates_applied: List[str] = []

    for path in modified_files:
        if "pai/" in path and path.endswith(".md"):
            doc_file = os.path.basename(path)
            result = _update_last_updated_timestamp(doc_file)
            if result:
                print(f"{TAG} [UPDATED] {result}", file=sys.stderr)
                updates_applied.append(result)

    if has_hook_changes:
        count_result = _update_hook_count(len(hooks_on_disk))
        if count_result:
            print(f"{TAG} [UPDATED] {count_result}", file=sys.stderr)
            updates_applied.append(count_result)

    # Step 5: Inference skipped in Python port (requires Inference.ts equivalent)
    print(f"{TAG} [INFERENCE] Skipped -- inference tool not yet ported to Python", file=sys.stderr)

    # Step 6: Save drift report
    drift_state_file = str(memory("STATE") / "doc-drift-state.json")
    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "session_id": session_id,
        "docs_checked": docs_to_check,
        "drift_items": all_drift,
        "updates_applied": updates_applied,
    }
    try:
        Path(drift_state_file).write_text(json.dumps(report, indent=2))
        print(f"{TAG} Drift report saved to {drift_state_file}", file=sys.stderr)
    except Exception as e:
        print(f"{TAG} Failed to save drift report: {e}", file=sys.stderr)

    if all_drift:
        _add_to_review_queue(all_drift)

    # Summary
    elapsed = int((time.time() - handler_start) * 1000)
    print(f"{TAG} === Summary ({elapsed}ms) ===", file=sys.stderr)
    print(f"{TAG} Docs checked: {len(docs_to_check)}", file=sys.stderr)
    print(f"{TAG} Drift items found: {len(all_drift)}", file=sys.stderr)
    print(f"{TAG} Updates applied: {len(updates_applied)} deterministic", file=sys.stderr)
    if all_drift:
        print(f"{TAG} WARNING: {len(all_drift)} cross-reference drift items need manual attention", file=sys.stderr)
    else:
        print(f"{TAG} All cross-references valid", file=sys.stderr)
    print(f"{TAG} === Check complete ===", file=sys.stderr)
