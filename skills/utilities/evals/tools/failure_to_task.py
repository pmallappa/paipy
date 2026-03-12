#!/usr/bin/env python3
"""Failure to Task Converter - Convert real failures into evaluation test cases."""
from __future__ import annotations
import json, time, random, string
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from ..Types import FailureLog, Task, GraderConfig, EvalDomain

EVALS_DIR = Path(__file__).parent.parent
FAILURES_LOG = EVALS_DIR / "Data" / "failures.jsonl"
TASKS_DIR = EVALS_DIR / "UseCases"

def _ensure_dirs():
    (EVALS_DIR / "Data").mkdir(parents=True, exist_ok=True)
    TASKS_DIR.mkdir(parents=True, exist_ok=True)

def log_failure(description: str, category: str, severity: str, expected_behavior=None, actual_behavior=None, task_context=None) -> dict:
    _ensure_dirs()
    log = {"id": f"failure_{int(time.time()*1000)}_{''.join(random.choices(string.ascii_lowercase+string.digits,k=6))}",
        "timestamp": datetime.now(timezone.utc).isoformat(), "description": description, "category": category,
        "severity": severity, "expected_behavior": expected_behavior, "actual_behavior": actual_behavior, "task_context": task_context}
    with open(FAILURES_LOG, "a") as f: f.write(json.dumps(log) + "\n")
    return log

def load_failures() -> list[dict]:
    if not FAILURES_LOG.exists(): return []
    return [json.loads(line) for line in FAILURES_LOG.read_text().strip().split("\n") if line]

def load_unconverted_failures() -> list[dict]:
    return [f for f in load_failures() if not f.get("converted_to_task")]

def convert_failure_to_task(failure: dict) -> dict:
    domain_map = {"file_targeting": "coding", "wrong_file": "coding", "partial_edit": "coding",
        "conversation_flow": "conversational", "research_accuracy": "research", "gui_interaction": "computer_use"}
    domain = domain_map.get(failure["category"].lower(), "general")
    graders = [{"type": "llm_rubric", "weight": 0.4, "params": {
        "rubric": f"The agent should: {failure.get('expected_behavior', 'complete the task correctly')}\nThe agent should NOT: {failure.get('actual_behavior', 'fail the task')}"}}]
    return {"id": f"task_{failure['category']}_{int(time.time()*1000)}", "description": failure["description"],
        "type": "regression", "domain": domain, "graders": graders, "trials": 1, "pass_threshold": 0.75,
        "tags": [failure["category"], failure["severity"], "from_failure"], "source": "failure_log",
        "created_at": datetime.now(timezone.utc).isoformat()}
