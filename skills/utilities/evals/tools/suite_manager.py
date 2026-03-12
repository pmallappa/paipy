#!/usr/bin/env python3
"""Eval Suite Manager - Manage capability vs regression suites with saturation monitoring."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
from ..Types import EvalSuite, EvalType, SaturationStatus, EvalRun
from datetime import datetime, timezone

EVALS_DIR = Path(__file__).parent.parent
SUITES_DIR = EVALS_DIR / "Suites"
RESULTS_DIR = EVALS_DIR / "Results"

def _ensure_dirs():
    (SUITES_DIR / "Capability").mkdir(parents=True, exist_ok=True)
    (SUITES_DIR / "Regression").mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

def create_suite(name: str, suite_type: EvalType, description: str, domain=None, pass_threshold=None, saturation_threshold=None, tasks=None) -> EvalSuite:
    _ensure_dirs()
    suite = EvalSuite(name=name, description=description, type=suite_type, domain=domain,
        tasks=tasks or [], pass_threshold=pass_threshold or (0.95 if suite_type == "regression" else 0.70),
        saturation_threshold=saturation_threshold or 0.95, created_at=datetime.now(timezone.utc).isoformat())
    dir_name = "Capability" if suite_type == "capability" else "Regression"
    file_path = SUITES_DIR / dir_name / f"{name}.json"
    file_path.write_text(json.dumps({"name": suite.name, "description": suite.description, "type": suite.type,
        "domain": suite.domain, "tasks": suite.tasks, "pass_threshold": suite.pass_threshold,
        "saturation_threshold": suite.saturation_threshold, "created_at": suite.created_at}, indent=2))
    return suite

def load_suite(name: str) -> Optional[dict]:
    _ensure_dirs()
    for dir_name in ["Capability", "Regression"]:
        file_path = SUITES_DIR / dir_name / f"{name}.json"
        if file_path.exists():
            return json.loads(file_path.read_text())
    return None

def list_suites(suite_type: Optional[EvalType] = None) -> list[dict]:
    _ensure_dirs()
    suites = []
    dirs = [suite_type.capitalize() if suite_type else d for d in ["Capability", "Regression"]] if not suite_type else [("Capability" if suite_type == "capability" else "Regression")]
    for dir_name in dirs:
        dir_path = SUITES_DIR / dir_name
        if dir_path.exists():
            for f in dir_path.glob("*.json"):
                suites.append(json.loads(f.read_text()))
    return suites

def check_saturation(suite_name: str) -> SaturationStatus:
    suite = load_suite(suite_name)
    if not suite: raise ValueError(f"Suite not found: {suite_name}")
    threshold = suite.get("saturation_threshold", 0.95)
    history = []
    suite_results_dir = RESULTS_DIR / suite_name
    if suite_results_dir.exists():
        for run_dir in sorted(suite_results_dir.iterdir())[-10:]:
            run_path = run_dir / "run.json"
            if run_path.exists():
                try:
                    run = json.loads(run_path.read_text())
                    history.append({"date": run.get("completed_at", run["started_at"]), "rate": run["pass_rate"]})
                except Exception: pass
    recent = [h for h in history[-3:] if h["rate"] >= threshold]
    saturated = len(recent) >= 3
    if suite["type"] == "capability" and saturated: action = "graduate_to_regression"
    elif saturated: action = "add_harder_cases"
    else: action = "keep"
    return SaturationStatus(suite_id=suite_name, pass_rate_history=history, saturated=saturated,
        consecutive_above_threshold=len(recent), recommended_action=action)
