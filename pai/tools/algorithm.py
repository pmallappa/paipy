#!/usr/bin/env python3
"""
THE ALGORITHM CLI -- Run the PAI Algorithm in Loop or Interactive mode

A unified CLI for executing Algorithm sessions against PRDs.

MODES:
  loop        -- Autonomous iteration via `claude -p` (SDK). Runs until all
                 ISC criteria pass or maxIterations reached. No human needed.
  interactive -- Launches a full interactive `claude` session with PRD context
                 loaded as the initial prompt. Human-in-the-loop.

USAGE:
  python algorithm.py -m loop -p <PRD> [-n 128]
  python algorithm.py -m interactive -p <PRD>
  python algorithm.py new -t <title> [-e <effort>]
  python algorithm.py status [-p <PRD>]
  python algorithm.py pause -p <PRD>
  python algorithm.py resume -p <PRD>
  python algorithm.py stop -p <PRD>
"""

import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# ---- Paths -----------------------------------------------------------------

HOME = os.environ.get("HOME", "~")
BASE_DIR = os.environ.get("PAI_DIR", os.path.join(HOME, ".claude"))
ALGORITHMS_DIR = os.path.join(BASE_DIR, "MEMORY", "STATE", "algorithms")
SESSION_NAMES_PATH = os.path.join(BASE_DIR, "MEMORY", "STATE", "session-names.json")
PROJECTS_DIR = os.environ.get("PROJECTS_DIR", os.path.join(HOME, "Projects"))
VOICE_URL = "http://localhost:8888/notify"
VOICE_ID = "fTtv3eikoepIosk8dTZ5"


# ---- Algorithm State -------------------------------------------------------

def ensure_algorithms_dir() -> None:
    os.makedirs(ALGORITHMS_DIR, exist_ok=True)


def read_algorithm_state(session_id: str) -> Optional[dict]:
    try:
        path = os.path.join(ALGORITHMS_DIR, f"{session_id}.json")
        if not os.path.exists(path):
            return None
        return json.loads(Path(path).read_text())
    except Exception:
        return None


def write_algorithm_state(state: dict) -> None:
    ensure_algorithms_dir()
    state["effortLevel"] = state.get("sla", "Standard")
    Path(os.path.join(ALGORITHMS_DIR, f"{state['sessionId']}.json")).write_text(
        json.dumps(state, indent=2)
    )


# ---- Session Names ---------------------------------------------------------

def read_session_names() -> dict[str, str]:
    try:
        if os.path.exists(SESSION_NAMES_PATH):
            return json.loads(Path(SESSION_NAMES_PATH).read_text())
    except Exception:
        pass
    return {}


def write_session_name(session_id: str, name: str) -> None:
    names = read_session_names()
    names[session_id] = name
    os.makedirs(os.path.dirname(SESSION_NAMES_PATH), exist_ok=True)
    Path(SESSION_NAMES_PATH).write_text(json.dumps(names, indent=2))


def remove_session_name(session_id: str) -> None:
    names = read_session_names()
    names.pop(session_id, None)
    Path(SESSION_NAMES_PATH).write_text(json.dumps(names, indent=2))


# ---- Voice Notifications ---------------------------------------------------

def voice_notify(message: str) -> None:
    # Voice notifications disabled in Python version per conversion instructions
    pass


# ---- PRD Parsing -----------------------------------------------------------

def extract_prd_title(content: str) -> str:
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else "Untitled PRD"


def read_prd(path: str) -> dict:
    raw = Path(path).read_text()
    match = re.match(r"^---\n([\s\S]*?)\n---\n([\s\S]*)$", raw)
    if not match:
        raise ValueError(f"Invalid PRD format: no frontmatter found in {path}")

    yaml_block = match.group(1)
    content = match.group(2)

    fm: dict[str, Any] = {}
    for line in yaml_block.splitlines():
        kv = re.match(r"^(\w+):\s*(.*)$", line)
        if kv:
            key, val = kv.group(1), kv.group(2)
            if val in ("null", ""):
                fm[key] = None
            elif val == "true":
                fm[key] = True
            elif val == "false":
                fm[key] = False
            elif val == "[]":
                fm[key] = []
            elif re.match(r"^\[.*\]$", val):
                fm[key] = [
                    s.strip().strip("\"'")
                    for s in val[1:-1].split(",")
                    if s.strip()
                ]
            elif re.match(r"^\d+$", val):
                fm[key] = int(val)
            else:
                fm[key] = val.strip("\"'")

    frontmatter = {
        "prd": fm.get("prd") is True,
        "id": fm.get("id", "unknown"),
        "status": fm.get("status", "DRAFT"),
        "mode": fm.get("mode", "interactive"),
        "effort_level": fm.get("effort_level") or fm.get("sla_tier") or "Standard",
        "iteration": fm.get("iteration", 0),
        "maxIterations": fm.get("maxIterations", 128),
        "loopStatus": fm.get("loopStatus"),
        "last_phase": fm.get("last_phase"),
        "failing_criteria": fm.get("failing_criteria", []),
        "verification_summary": fm.get("verification_summary", "0/0"),
        **fm,
    }

    return {"frontmatter": frontmatter, "content": content, "raw": raw}


def update_frontmatter(path: str, updates: dict[str, Any]) -> None:
    raw = Path(path).read_text()
    match = re.match(r"^---\n([\s\S]*?)\n---\n([\s\S]*)$", raw)
    if not match:
        raise ValueError(f"Invalid PRD format in {path}")

    yaml_block = match.group(1)
    content = match.group(2)

    for key, value in updates.items():
        str_val = "null" if value is None else str(value)
        regex = re.compile(rf"^({re.escape(key)}):.*$", re.MULTILINE)
        if regex.search(yaml_block):
            yaml_block = regex.sub(f"{key}: {str_val}", yaml_block)
        else:
            yaml_block += f"\n{key}: {str_val}"

    Path(path).write_text(f"---\n{yaml_block}\n---\n{content}")


# ---- Criteria Counting -----------------------------------------------------

def count_criteria(content: str) -> dict:
    criteria: list[dict] = []

    for m in re.finditer(r"- \[x\] (ISC-[A-Za-z0-9-]+):\s*(.+?)(?:\s*\|\s*Verify:.*)?$", content, re.MULTILINE):
        criteria.append({"id": m.group(1), "description": m.group(2).strip(), "status": "passing"})
    for m in re.finditer(r"- \[ \] (ISC-[A-Za-z0-9-]+):\s*(.+?)(?:\s*\|\s*Verify:.*)?$", content, re.MULTILINE):
        criteria.append({"id": m.group(1), "description": m.group(2).strip(), "status": "failing"})

    if not criteria:
        for m in re.finditer(r"- \[x\] ([CA]\d+):\s*(.+)$", content, re.MULTILINE):
            criteria.append({"id": m.group(1), "description": m.group(2).strip(), "status": "passing"})
        for m in re.finditer(r"- \[ \] ([CA]\d+):\s*(.+)$", content, re.MULTILINE):
            criteria.append({"id": m.group(1), "description": m.group(2).strip(), "status": "failing"})

    passing = sum(1 for c in criteria if c["status"] == "passing")
    failing = sum(1 for c in criteria if c["status"] == "failing")
    failing_ids = [c["id"] for c in criteria if c["status"] == "failing"]

    return {"total": len(criteria), "passing": passing, "failing": failing,
            "failingIds": failing_ids, "criteria": criteria}


# ---- Dashboard State Sync --------------------------------------------------

def sync_criteria_to_state(state: dict, criteria_info: dict) -> None:
    state["criteria"] = [
        {
            "id": c["id"],
            "description": c["description"],
            "type": "anti-criterion" if c["id"].startswith("ISC-A") else "criterion",
            "status": "completed" if c["status"] == "passing" else "pending",
            "createdInPhase": "OBSERVE",
        }
        for c in criteria_info["criteria"]
    ]


def create_loop_state(session_id: str, prd_path: str, prd_id: str,
                      title: str, max_iter: int, criteria_info: dict,
                      effort_level: str = "Standard", agent_count: int = 1) -> dict:
    now = int(time.time() * 1000)
    state: dict[str, Any] = {
        "active": True, "sessionId": session_id,
        "taskDescription": f"Loop: {title}",
        "currentPhase": "EXECUTE", "phaseStartedAt": now,
        "algorithmStartedAt": now, "sla": effort_level,
        "criteria": [], "agents": [],
        "capabilities": ["Task Tool", "SDK", "Loop Runner"],
        "prdPath": prd_path,
        "phaseHistory": [{"phase": "EXECUTE", "startedAt": now,
                          "criteriaCount": criteria_info["total"], "agentCount": agent_count}],
        "loopMode": True, "loopIteration": 0,
        "loopMaxIterations": max_iter,
        "loopPrdId": prd_id, "loopPrdPath": prd_path,
        "loopHistory": [], "parallelAgents": agent_count, "mode": "loop",
    }
    sync_criteria_to_state(state, criteria_info)
    return state


def update_loop_state_for_iteration(state: dict, iteration: int, criteria_info: dict) -> None:
    state["active"] = True
    state["loopIteration"] = iteration
    state["currentPhase"] = "EXECUTE"
    state["phaseStartedAt"] = int(time.time() * 1000)
    state["taskDescription"] = (
        f"Loop: {state.get('loopPrdId', '')} "
        f"[{criteria_info['passing']}/{criteria_info['total']} iter {iteration}]"
    )
    sync_criteria_to_state(state, criteria_info)


def finalize_loop_state(state: dict, outcome: str, criteria_info: dict) -> None:
    state["active"] = False
    state["completedAt"] = int(time.time() * 1000)
    state["currentPhase"] = "COMPLETE" if outcome == "completed" else "VERIFY"
    state["summary"] = (
        f"{outcome}: {criteria_info['passing']}/{criteria_info['total']} "
        f"criteria in {state.get('loopIteration', 0)} iterations"
    )
    sync_criteria_to_state(state, criteria_info)
    history = state.get("phaseHistory", [])
    if history:
        last = history[-1]
        if not last.get("completedAt"):
            last["completedAt"] = int(time.time() * 1000)


# ---- Iteration Prompt (Loop Mode) ------------------------------------------

def build_iteration_prompt(prd_path: str, iteration: int, max_iterations: int) -> str:
    mode = "loop"
    effort_level = "Standard"
    last_phase = "unknown"
    failing_list = "unknown -- read the PRD to identify them"
    verification_summary = "unknown"

    try:
        prd = read_prd(prd_path)
        fm = prd["frontmatter"]
        mode = fm.get("mode") or "loop"
        effort_level = fm.get("effort_level") or "Standard"
        last_phase = fm.get("last_phase") or "unknown"
        verification_summary = fm.get("verification_summary") or "0/0"

        criteria = count_criteria(prd["content"])
        if criteria["failingIds"]:
            details = []
            for fid in criteria["failingIds"]:
                escaped = re.escape(fid)
                line_match = re.search(rf"- \[ \] {escaped}:.*", prd["content"])
                details.append(line_match.group(0).lstrip("- [ ] ") if line_match else fid)
            failing_list = "\n  ".join(details)
    except Exception:
        pass

    return f"""You are running inside The Algorithm -- autonomous loop iteration.

PRD: {prd_path}
Iteration: {iteration} of {max_iterations}
Mode: {mode} (autonomous -- no human interaction available)
Per-iteration effort level: {effort_level}
Last phase reached: {last_phase}
Current progress: {verification_summary}

Failing criteria:
  {failing_list}

Instructions:
1. Read the PRD. Focus on the IDEAL STATE CRITERIA section.
2. Read the CONTEXT section to understand the problem space.
3. Read the CHANGELOG to understand what previous iterations accomplished.
4. Focus on 1-3 failing criteria with highest priority.
5. For each targeted criterion, read its Verify: method and execute it.
6. If a criterion has Verify: Custom -- SKIP it.
7. After changes, RE-VERIFY ALL criteria to catch regressions.
8. Update the PRD checkboxes and frontmatter.
9. Be honest. If a criterion fails, leave it unchecked.
10. Focus on SAFE INCREMENTS."""


# ---- Parallel Agent Partitioning --------------------------------------------

def partition_criteria(criteria_info: dict, agent_count: int) -> list[dict]:
    failing = [c for c in criteria_info["criteria"] if c["status"] == "failing"]
    if not failing:
        return []

    def get_domain(cid: str) -> str:
        match = re.match(r"^ISC-(.+)-\d+$", cid)
        return match.group(1) if match else cid

    domain_groups: dict[str, list[dict]] = {}
    for c in failing:
        domain = get_domain(c["id"])
        domain_groups.setdefault(domain, []).append({"id": c["id"], "description": c["description"]})

    sorted_domains = sorted(domain_groups.items(), key=lambda x: -len(x[1]))
    effective = min(agent_count, len(sorted_domains))
    agents = [{"agentId": i + 1, "criteriaIds": [], "criteriaDetails": []} for i in range(effective)]

    for _, group in sorted_domains:
        min_agent = min(agents, key=lambda a: len(a["criteriaIds"]))
        for c in group:
            min_agent["criteriaIds"].append(c["id"])
            min_agent["criteriaDetails"].append(c)

    return [a for a in agents if a["criteriaIds"]]


# ---- CHANGELOG Append -------------------------------------------------------

def append_prd_changelog(prd_path: str, iteration: int,
                         pre: dict, post: dict, elapsed_ms: int) -> None:
    try:
        content = Path(prd_path).read_text()
        marker = "## CHANGELOG"
        idx = content.find(marker)
        if idx == -1:
            return

        gained = post["passing"] - pre["passing"]
        regressions = [
            c["id"] for c in pre["criteria"]
            if c["status"] == "passing"
            and any(p["id"] == c["id"] and p["status"] == "failing" for p in post["criteria"])
        ]
        still_failing = post["failingIds"]
        elapsed_sec = round(elapsed_ms / 1000)
        now = datetime.now().strftime("%Y-%m-%d")

        entry = f"""
### Iteration {iteration} -- {now}
- **Phase reached:** VERIFY
- **Criteria delta:** {pre['passing']}/{pre['total']} -> {post['passing']}/{post['total']} ({'+' if gained >= 0 else ''}{gained})
- **Duration:** {elapsed_sec}s
- **Still failing:** {', '.join(still_failing) if still_failing else 'None'}
- **Regressions:** {', '.join(regressions) if regressions else 'None'}
"""

        after_header = content.find("\n", idx + len(marker))
        if after_header == -1:
            return

        insert_point = after_header + 1
        next_newline = content.find("\n", insert_point)
        next_line = content[insert_point:next_newline] if next_newline != -1 else ""
        if next_line.strip().startswith("_"):
            content = content[:insert_point] + entry + content[next_newline + 1:]
        else:
            content = content[:insert_point] + entry + content[insert_point:]

        Path(prd_path).write_text(content)
    except Exception:
        pass


def detect_plateau(loop_history: list[dict], window: int = 3) -> bool:
    if len(loop_history) < window:
        return False
    recent = loop_history[-window:]
    baseline = recent[0].get("criteriaPassing", 0)
    return all(h.get("criteriaPassing", 0) == baseline for h in recent)


# ---- Progress Bar -----------------------------------------------------------

def progress_bar(passing: int, total: int, width: int = 20) -> str:
    pct = passing / total if total > 0 else 0
    filled = round(pct * width)
    return f"{'█' * filled}{'░' * (width - filled)} {round(pct * 100)}%"


# ---- Core Loop Mode --------------------------------------------------------

def run_loop(prd_path: str, max_override: Optional[int] = None, agent_count: int = 1) -> None:
    abs_path = os.path.abspath(prd_path)
    if not os.path.exists(abs_path):
        print(f"\x1b[31mError:\x1b[0m PRD not found: {abs_path}", file=sys.stderr)
        sys.exit(1)

    prd = read_prd(abs_path)
    fm = prd["frontmatter"]
    max_iter = max_override if max_override is not None else fm.get("maxIterations", 128)
    prd_title = extract_prd_title(prd["content"])
    effort_level = fm.get("effort_level", "Standard")

    if fm.get("status") == "COMPLETE":
        print(f"\x1b[32m\u2713\x1b[0m PRD already COMPLETE: {fm['id']}")
        return

    if fm.get("loopStatus") == "running":
        print(f"\x1b[31mError:\x1b[0m Loop already running on {fm['id']}", file=sys.stderr)
        sys.exit(1)

    loop_session_id = str(uuid.uuid4())
    initial_criteria = count_criteria(prd["content"])
    state = create_loop_state(
        loop_session_id, abs_path, fm["id"], prd_title,
        max_iter, initial_criteria, effort_level, agent_count
    )
    write_algorithm_state(state)
    suffix = f" ({agent_count} agents)" if agent_count > 1 else ""
    write_session_name(loop_session_id, f"Loop: {prd_title}{suffix}")

    update_frontmatter(abs_path, {"loopStatus": "running", "maxIterations": max_iter})

    bar = progress_bar(initial_criteria["passing"], initial_criteria["total"])
    print()
    print(f"\x1b[36m\u2554{'═' * 66}\u2557\x1b[0m")
    print(f"\x1b[36m\u2551\x1b[0m  \x1b[1mTHE ALGORITHM\x1b[0m -- Loop Mode{' ' * 38}\x1b[36m\u2551\x1b[0m")
    print(f"\x1b[36m\u2560{'═' * 66}\u2563\x1b[0m")
    print(f"\x1b[36m\u2551\x1b[0m  PRD:       {fm['id']:<53}\x1b[36m\u2551\x1b[0m")
    print(f"\x1b[36m\u2551\x1b[0m  Title:     {prd_title[:53]:<53}\x1b[36m\u2551\x1b[0m")
    print(f"\x1b[36m\u2551\x1b[0m  Progress:  {bar:<53}\x1b[36m\u2551\x1b[0m")
    print(f"\x1b[36m\u255a{'═' * 66}\u255d\x1b[0m")
    print()

    while True:
        prd = read_prd(abs_path)
        fm = prd["frontmatter"]
        criteria = count_criteria(prd["content"])

        # Exit conditions
        if fm.get("status") == "COMPLETE":
            update_frontmatter(abs_path, {"loopStatus": "completed"})
            finalize_loop_state(state, "completed", criteria)
            write_algorithm_state(state)
            write_session_name(loop_session_id, f"Loop: {prd_title} [COMPLETE]")
            total_time = round((time.time() * 1000 - state["algorithmStartedAt"]) / 1000)
            print(f"\n\x1b[32m\u2713 COMPLETE\x1b[0m -- {criteria['passing']}/{criteria['total']} in {fm.get('iteration', 0)} iterations ({total_time}s)")
            return

        if fm.get("status") == "BLOCKED":
            update_frontmatter(abs_path, {"loopStatus": "completed"})
            finalize_loop_state(state, "blocked", criteria)
            write_algorithm_state(state)
            print(f"\n\x1b[33m\u26A0 BLOCKED\x1b[0m -- {criteria['passing']}/{criteria['total']}")
            return

        if fm.get("iteration", 0) >= max_iter:
            update_frontmatter(abs_path, {"loopStatus": "failed"})
            finalize_loop_state(state, "failed", criteria)
            write_algorithm_state(state)
            print(f"\n\x1b[33m\u26A0 Max iterations reached ({max_iter})\x1b[0m")
            return

        if fm.get("loopStatus") == "paused":
            finalize_loop_state(state, "paused", criteria)
            state["active"] = True
            state["currentPhase"] = "PLAN"
            state.pop("completedAt", None)
            write_algorithm_state(state)
            print(f"\n\x1b[33m\u23F8 Paused\x1b[0m -- resume with: python algorithm.py resume -p {abs_path}")
            return

        if fm.get("loopStatus") == "stopped":
            finalize_loop_state(state, "stopped", criteria)
            write_algorithm_state(state)
            print(f"\n\x1b[31m\u25A0 Stopped\x1b[0m")
            return

        # Run iteration
        new_iteration = fm.get("iteration", 0) + 1
        iter_start = time.time()

        update_frontmatter(abs_path, {
            "iteration": new_iteration,
            "updated": datetime.now().strftime("%Y-%m-%d"),
        })

        update_loop_state_for_iteration(state, new_iteration, criteria)
        write_algorithm_state(state)
        write_session_name(loop_session_id,
                           f"Loop: {prd_title} [{criteria['passing']}/{criteria['total']} iter {new_iteration}]")

        bar = progress_bar(criteria["passing"], criteria["total"])
        print(f"\x1b[36m--- Iteration {new_iteration}/{max_iter} {'─' * max(0, 50 - len(str(new_iteration)) - len(str(max_iter)))}\x1b[0m")
        print(f"  Progress: {criteria['passing']}/{criteria['total']} {bar} | Failing: {criteria['failing']}")
        print()

        # Sequential path: single agent
        prompt = build_iteration_prompt(abs_path, new_iteration, max_iter)

        result = subprocess.run(
            ["claude", "-p", prompt,
             "--allowedTools", "Edit,Write,Bash,Read,Glob,Grep,WebFetch,WebSearch,NotebookEdit"],
            capture_output=True, text=True,
            timeout=600,
            cwd=os.path.dirname(abs_path),
        )

        iter_end = time.time()
        iter_elapsed_ms = int((iter_end - iter_start) * 1000)

        if result.returncode != 0:
            print(f"\x1b[31m  Error in iteration {new_iteration}\x1b[0m", file=sys.stderr)
            if result.stderr:
                print(f"  {result.stderr[:200]}", file=sys.stderr)
            state.setdefault("loopHistory", []).append({
                "iteration": new_iteration,
                "startedAt": int(iter_start * 1000),
                "completedAt": int(iter_end * 1000),
                "criteriaPassing": criteria["passing"],
                "criteriaTotal": criteria["total"],
            })
            write_algorithm_state(state)
            time.sleep(2)
            continue

        post_prd = read_prd(abs_path)
        post_criteria = count_criteria(post_prd["content"])

        state.setdefault("loopHistory", []).append({
            "iteration": new_iteration,
            "startedAt": int(iter_start * 1000),
            "completedAt": int(iter_end * 1000),
            "criteriaPassing": post_criteria["passing"],
            "criteriaTotal": post_criteria["total"],
        })
        sync_criteria_to_state(state, post_criteria)
        state["loopIteration"] = new_iteration
        write_algorithm_state(state)

        gained = post_criteria["passing"] - criteria["passing"]
        if result.stdout:
            summary = result.stdout[:200].replace("\n", " ")
            print(f"\x1b[90m  Output: {summary}{'...' if len(result.stdout) > 200 else ''}\x1b[0m")

        print(f"  \x1b[32m+{gained}\x1b[0m criteria -- now {post_criteria['passing']}/{post_criteria['total']} passing")

        append_prd_changelog(abs_path, new_iteration, criteria, post_criteria, iter_elapsed_ms)

        if state.get("loopHistory") and detect_plateau(state["loopHistory"], 3):
            print(f"\x1b[33m  Plateau detected -- no progress in last 3 iterations\x1b[0m")
            update_frontmatter(abs_path, {"status": "BLOCKED", "loopStatus": "completed"})

        time.sleep(2)


# ---- Interactive Mode -------------------------------------------------------

def run_interactive(prd_path: str) -> None:
    abs_path = os.path.abspath(prd_path)
    if not os.path.exists(abs_path):
        print(f"\x1b[31mError:\x1b[0m PRD not found: {abs_path}", file=sys.stderr)
        sys.exit(1)

    prd = read_prd(abs_path)
    prd_title = extract_prd_title(prd["content"])
    criteria = count_criteria(prd["content"])

    prompt = (
        f"Work on this PRD: {abs_path}\n\n"
        f"Title: {prd_title}\n"
        f"Progress: {criteria['passing']}/{criteria['total']}\n"
        f"Failing: {', '.join(criteria['failingIds']) if criteria['failingIds'] else 'None'}\n\n"
        "Read the PRD, understand the IDEAL STATE CRITERIA, and make progress."
    )

    print(f"\x1b[36m\u25CB\x1b[0m THE ALGORITHM (interactive) -- {prd_title}")
    print(f"  PRD: {abs_path}")
    print(f"  Progress: {criteria['passing']}/{criteria['total']}")
    print("  Launching claude...\n")

    env = dict(os.environ)
    env.pop("CLAUDECODE", None)

    proc = subprocess.Popen(
        ["claude", prompt,
         "--allowedTools", "Edit,Write,Bash,Read,Glob,Grep,WebFetch,WebSearch,NotebookEdit"],
        cwd=os.path.dirname(abs_path),
        env=env,
    )
    proc.wait()
    sys.exit(proc.returncode or 0)


# ---- PRD Creation ----------------------------------------------------------

def create_new_prd(title: str, effort_level: str = "Standard",
                   output_dir: Optional[str] = None) -> str:
    slug = re.sub(r"[^a-z0-9\s-]", "", title.lower())
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)[:40].rstrip("-") or "task"

    now = datetime.now()
    filename = f"PRD-{now.strftime('%Y%m%d')}-{slug}.md"

    if output_dir:
        target_dir = os.path.abspath(output_dir)
    else:
        session_slug = f"{now.strftime('%Y%m%d-%H%M%S')}_{slug}"
        target_dir = os.path.join(BASE_DIR, "MEMORY", "WORK", session_slug)

    os.makedirs(target_dir, exist_ok=True)

    prd_id = f"PRD-{now.strftime('%Y%m%d')}-{slug}"
    prd_content = f"""---
prd: true
id: {prd_id}
status: DRAFT
mode: interactive
effort_level: {effort_level}
iteration: 0
maxIterations: 128
loopStatus: null
last_phase: null
failing_criteria: []
verification_summary: "0/0"
created: {now.strftime('%Y-%m-%d')}
updated: {now.strftime('%Y-%m-%d')}
---

# {title}

## CONTEXT

_Describe the problem space, existing architecture, and constraints._

## IDEAL STATE CRITERIA

_Define criteria as checkbox items:_

- [ ] ISC-CORE-1: First criterion | Verify: Run `test command`
- [ ] ISC-CORE-2: Second criterion | Verify: Check output

## STATUS

| Metric | Value |
|--------|-------|
| Total criteria | 2 |
| Passing | 0 |
| Failing | 2 |
| Status | DRAFT |

## CHANGELOG

_Iteration history will be appended here._
"""

    full_path = os.path.join(target_dir, filename)
    Path(full_path).write_text(prd_content)
    return full_path


# ---- PRD Discovery ----------------------------------------------------------

def find_all_prds() -> list[str]:
    files: list[str] = []

    work_dir = os.path.join(BASE_DIR, "MEMORY", "WORK")
    if os.path.isdir(work_dir):
        try:
            for session in os.listdir(work_dir):
                session_path = os.path.join(work_dir, session)
                if not os.path.isdir(session_path):
                    continue
                flat_prd = os.path.join(session_path, "PRD.md")
                if os.path.exists(flat_prd):
                    files.append(flat_prd)
                try:
                    for f in os.listdir(session_path):
                        if f.startswith("PRD-") and f.endswith(".md"):
                            files.append(os.path.join(session_path, f))
                except OSError:
                    pass
        except OSError:
            pass

    if os.path.isdir(PROJECTS_DIR):
        try:
            for project in os.listdir(PROJECTS_DIR):
                prd_dir = os.path.join(PROJECTS_DIR, project, ".prd")
                if os.path.isdir(prd_dir):
                    try:
                        for f in os.listdir(prd_dir):
                            if f.startswith("PRD-") and f.endswith(".md"):
                                files.append(os.path.join(prd_dir, f))
                    except OSError:
                        pass
        except OSError:
            pass

    return files


# ---- Status -----------------------------------------------------------------

def show_status(specific_path: Optional[str] = None) -> None:
    if specific_path:
        abs_path = os.path.abspath(specific_path)
        prd = read_prd(abs_path)
        criteria = count_criteria(prd["content"])
        print_prd_status(abs_path, prd["frontmatter"], criteria)
        return

    files = find_all_prds()
    if not files:
        print("No PRDs found.")
        return

    print(f"\x1b[36mTHE ALGORITHM -- PRD Status\x1b[0m\n")

    for f in files:
        try:
            prd = read_prd(f)
            criteria = count_criteria(prd["content"])
            print_prd_status(f, prd["frontmatter"], criteria)
        except Exception:
            pass


def print_prd_status(path: str, fm: dict, criteria: dict) -> None:
    status = fm.get("status", "DRAFT")
    loop = fm.get("loopStatus", "idle")
    icons = {"COMPLETE": "\x1b[32m\u2713\x1b[0m", "BLOCKED": "\x1b[33m\u26A0\x1b[0m"}
    icon = icons.get(status, "\x1b[90m\u25CB\x1b[0m")

    bar = progress_bar(criteria["passing"], criteria["total"], 10)
    print(f"{icon} {fm.get('id', 'unknown')}")
    print(f"  Status: {status} | Loop: {loop} | Iter: {fm.get('iteration', 0)}/{fm.get('maxIterations', 128)}")
    print(f"  Criteria: [{bar}] {criteria['passing']}/{criteria['total']}")
    print(f"  Path: {path}")
    print()


# ---- Pause / Resume / Stop -------------------------------------------------

def pause_loop(prd_path: str) -> None:
    abs_path = os.path.abspath(prd_path)
    prd = read_prd(abs_path)
    fm = prd["frontmatter"]
    if fm.get("loopStatus") != "running":
        print(f"Loop is not running on {fm['id']} (status: {fm.get('loopStatus', 'idle')})")
        return
    update_frontmatter(abs_path, {"loopStatus": "paused"})
    print(f"\x1b[33m\u23F8 Paused\x1b[0m Loop on {fm['id']}")
    print(f"  Resume with: python algorithm.py resume -p {abs_path}")


def resume_loop(prd_path: str) -> None:
    abs_path = os.path.abspath(prd_path)
    prd = read_prd(abs_path)
    fm = prd["frontmatter"]
    if fm.get("loopStatus") != "paused":
        print(f"Loop is not paused on {fm['id']}")
        return
    update_frontmatter(abs_path, {"loopStatus": "running"})
    print(f"\x1b[36m\u25B6 Resuming\x1b[0m Loop on {fm['id']}")
    run_loop(abs_path)


def stop_loop(prd_path: str) -> None:
    abs_path = os.path.abspath(prd_path)
    prd = read_prd(abs_path)
    fm = prd["frontmatter"]
    update_frontmatter(abs_path, {"loopStatus": "stopped"})
    print(f"\x1b[31m\u25A0 Stopped\x1b[0m Loop on {fm['id']}")


# ---- PRD Path Resolution ---------------------------------------------------

def resolve_prd_path(inp: str) -> str:
    if "/" in inp or inp.endswith(".md"):
        return os.path.abspath(inp)
    all_prds = find_all_prds()
    matches = [p for p in all_prds if inp in os.path.basename(p) or inp in p]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous PRD reference '{inp}'. Matches:", file=sys.stderr)
        for m in matches:
            print(f"  {m}", file=sys.stderr)
        sys.exit(1)
    print(f"PRD not found: {inp}", file=sys.stderr)
    sys.exit(1)


# ---- CLI Argument Parsing ---------------------------------------------------

def parse_args(argv: list[str]) -> dict:
    args = argv[1:]
    result: dict[str, Any] = {
        "subcommand": None, "mode": None, "prdPath": None,
        "maxIterations": None, "agentCount": 1, "title": None, "effortLevel": None,
    }

    subcommands = ["status", "pause", "resume", "stop", "new"]
    if args and args[0] in subcommands:
        result["subcommand"] = args[0]

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-m", "--mode") and i + 1 < len(args):
            i += 1
            result["mode"] = args[i]
        elif arg in ("-p", "--prd") and i + 1 < len(args):
            i += 1
            result["prdPath"] = args[i]
        elif arg in ("-n", "--max") and i + 1 < len(args):
            i += 1
            result["maxIterations"] = int(args[i])
        elif arg in ("-a", "--agents") and i + 1 < len(args):
            i += 1
            result["agentCount"] = int(args[i])
        elif arg in ("-t", "--title") and i + 1 < len(args):
            i += 1
            result["title"] = args[i]
        elif arg in ("-e", "--effort") and i + 1 < len(args):
            i += 1
            result["effortLevel"] = args[i]
        elif arg in ("-h", "--help"):
            print_help()
            sys.exit(0)
        i += 1

    ac = result["agentCount"]
    if not (1 <= ac <= 16):
        print(f"\x1b[31mError:\x1b[0m Invalid agent count: {ac}. Must be 1-16.", file=sys.stderr)
        sys.exit(1)

    return result


def print_help() -> None:
    print("""
\x1b[36mTHE ALGORITHM\x1b[0m -- PAI Algorithm Runner (v1.0.0)

Usage:
  python algorithm.py -m <mode> -p <PRD> [-n N] [-a N]
  python algorithm.py new -t <title> [-e <effort>]
  python algorithm.py status [-p <PRD>]
  python algorithm.py pause -p <PRD>
  python algorithm.py resume -p <PRD>
  python algorithm.py stop -p <PRD>

Modes:
  loop          Autonomous iteration
  interactive   Full claude session with PRD context

Flags:
  -m, --mode <mode>     Execution mode: loop or interactive
  -p, --prd <path>      PRD file path or PRD ID
  -n, --max <N>         Max iterations (loop mode, default: 128)
  -a, --agents <N>      Parallel agents (1-16, default: 1)
  -t, --title <title>   PRD title (required for 'new')
  -e, --effort <level>  Effort level (default: Standard)
  -h, --help            Show this help
""")


# ---- Main ------------------------------------------------------------------

def main() -> None:
    parsed = parse_args(sys.argv)

    if parsed["subcommand"]:
        prd_ref = parsed["prdPath"]

        if parsed["subcommand"] == "status":
            show_status(resolve_prd_path(prd_ref) if prd_ref else None)
        elif parsed["subcommand"] == "new":
            if not parsed["title"]:
                print("Usage: python algorithm.py new -t <title> [-e <effort>]", file=sys.stderr)
                sys.exit(1)
            prd_path = create_new_prd(
                parsed["title"],
                parsed["effortLevel"] or "Standard",
                prd_ref or None,
            )
            print(f"\x1b[32m\u2713\x1b[0m Created PRD: {prd_path}")
            print(f"\n  Run with:  python algorithm.py -m interactive -p {prd_path}")
            print(f"  Or loop:   python algorithm.py -m loop -p {prd_path} -n 20")
        elif parsed["subcommand"] == "pause":
            if not prd_ref:
                print("Usage: python algorithm.py pause -p <PRD>", file=sys.stderr)
                sys.exit(1)
            pause_loop(resolve_prd_path(prd_ref))
        elif parsed["subcommand"] == "resume":
            if not prd_ref:
                print("Usage: python algorithm.py resume -p <PRD>", file=sys.stderr)
                sys.exit(1)
            resume_loop(resolve_prd_path(prd_ref))
        elif parsed["subcommand"] == "stop":
            if not prd_ref:
                print("Usage: python algorithm.py stop -p <PRD>", file=sys.stderr)
                sys.exit(1)
            stop_loop(resolve_prd_path(prd_ref))

    elif parsed["mode"]:
        if not parsed["prdPath"]:
            print("Error: -p <PRD> is required when using -m <mode>", file=sys.stderr)
            sys.exit(1)

        resolved = resolve_prd_path(parsed["prdPath"])

        if parsed["mode"] == "loop":
            run_loop(resolved, parsed["maxIterations"], parsed["agentCount"])
        elif parsed["mode"] == "interactive":
            run_interactive(resolved)
        else:
            print(f"Unknown mode: {parsed['mode']}. Use 'loop' or 'interactive'.", file=sys.stderr)
            sys.exit(1)
    else:
        print_help()


if __name__ == "__main__":
    main()
