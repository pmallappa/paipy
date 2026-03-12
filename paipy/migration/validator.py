#!/usr/bin/env python3
"""PAI Installation Validator - Verifies installation completeness."""
from __future__ import annotations
import json, subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

@dataclass
class ValidationCheck:
    name: str
    category: Literal["structure", "config", "skills", "hooks", "runtime"]
    passed: bool
    message: str
    severity: Literal["error", "warning", "info"]

@dataclass
class ValidationResult:
    passed: bool
    score: int
    checks: list[ValidationCheck]
    summary: dict = field(default_factory=dict)

def validate_installation(path_str: str) -> ValidationResult:
    path = Path(path_str)
    checks: list[ValidationCheck] = []
    checks.extend(_validate_structure(path))
    checks.extend(_validate_config(path))
    checks.extend(_validate_skills(path))
    checks.extend(_validate_hooks(path))
    checks.extend(_validate_runtime(path))
    passed_count = sum(1 for c in checks if c.passed)
    failed = sum(1 for c in checks if not c.passed and c.severity == "error")
    warnings = sum(1 for c in checks if not c.passed and c.severity == "warning")
    return ValidationResult(passed=failed == 0, score=round(passed_count / len(checks) * 100) if checks else 0,
        checks=checks, summary={"total": len(checks), "passed": passed_count, "failed": failed, "warnings": warnings})

def _validate_structure(path: Path) -> list[ValidationCheck]:
    checks = []
    for d, name in [("skills", "Skills directory"), ("memory", "memory directory"), ("hooks", "Hooks directory"), ("skills/pai", "PAI skill"), ("agents", "Agents directory")]:
        p = path / d
        checks.append(ValidationCheck(name=name, category="structure", passed=p.exists(), message="Present" if p.exists() else "Missing", severity="error"))
    for d, name in [("Plans", "Plans directory"), ("Commands", "Commands directory")]:
        p = path / d
        checks.append(ValidationCheck(name=name, category="structure", passed=p.exists(), message="Present" if p.exists() else "Missing (optional)", severity="warning"))
    return checks

def _validate_config(path: Path) -> list[ValidationCheck]:
    checks = []
    sp = path / "settings.json"
    checks.append(ValidationCheck(name="settings.json exists", category="config", passed=sp.exists(), message="Found" if sp.exists() else "Missing", severity="error"))
    if sp.exists():
        try:
            settings = json.loads(sp.read_text())
            checks.append(ValidationCheck(name="settings.json is valid JSON", category="config", passed=True, message="Valid", severity="error"))
            has_p = bool(settings.get("principal", {}).get("name"))
            checks.append(ValidationCheck(name="Principal name configured", category="config", passed=has_p, message=f'Set to "{settings["principal"]["name"]}"' if has_p else "Not configured", severity="error"))
            has_id = bool(settings.get("daidentity", {}).get("name"))
            checks.append(ValidationCheck(name="AI identity configured", category="config", passed=has_id, message=f'Set to "{settings["daidentity"]["name"]}"' if has_id else "Not configured", severity="error"))
        except Exception as e:
            checks.append(ValidationCheck(name="settings.json is valid JSON", category="config", passed=False, message=f"Parse error: {e}", severity="error"))
    cm = path / "CLAUDE.md"
    checks.append(ValidationCheck(name="CLAUDE.md exists", category="config", passed=cm.exists(), message="Found" if cm.exists() else "Missing", severity="warning"))
    return checks

def _validate_skills(path: Path) -> list[ValidationCheck]:
    checks = []
    sd = path / "skills"
    if not sd.exists():
        checks.append(ValidationCheck(name="Skills directory", category="skills", passed=False, message="Missing", severity="error")); return checks
    try:
        skills = [s.name for s in sd.iterdir() if s.is_dir()]
        checks.append(ValidationCheck(name="Skills count", category="skills", passed=len(skills) > 0, message=f"{len(skills)} skills found", severity="info" if skills else "error"))
        csm = sd / "PAI" / "SKILL.md"
        checks.append(ValidationCheck(name="PAI skill has SKILL.md", category="skills", passed=csm.exists(), message="Found" if csm.exists() else "Missing", severity="error"))
    except Exception as e:
        checks.append(ValidationCheck(name="Skills scan", category="skills", passed=False, message=f"Error: {e}", severity="error"))
    return checks

def _validate_hooks(path: Path) -> list[ValidationCheck]:
    checks = []
    hd = path / "hooks"
    if not hd.exists():
        checks.append(ValidationCheck(name="Hooks directory", category="hooks", passed=False, message="Missing", severity="warning")); return checks
    try:
        hooks = [f.name for f in hd.iterdir() if f.suffix in (".ts", ".py")]
        checks.append(ValidationCheck(name="Hooks count", category="hooks", passed=len(hooks) > 0, message=f"{len(hooks)} hooks found", severity="info" if hooks else "warning"))
    except Exception as e:
        checks.append(ValidationCheck(name="Hooks scan", category="hooks", passed=False, message=f"Error: {e}", severity="warning"))
    return checks

def _validate_runtime(path: Path) -> list[ValidationCheck]:
    checks = []
    try:
        ver = subprocess.run(["python3", "--version"], capture_output=True, text=True, timeout=5)
        checks.append(ValidationCheck(name="Python runtime", category="runtime", passed=ver.returncode == 0, message=ver.stdout.strip() if ver.returncode == 0 else "Not found", severity="error"))
    except Exception:
        checks.append(ValidationCheck(name="Python runtime", category="runtime", passed=False, message="Not detected", severity="error"))
    try:
        ver = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=5)
        found = ver.returncode == 0
        checks.append(ValidationCheck(name="Claude Code CLI", category="runtime", passed=found, message=ver.stdout.strip() if found else "Not installed", severity="warning"))
    except Exception:
        checks.append(ValidationCheck(name="Claude Code CLI", category="runtime", passed=False, message="Not detected", severity="warning"))
    return checks

def format_validation_result(result: ValidationResult) -> str:
    lines = ["", f"Installation Validation: {'PASSED' if result.passed else 'FAILED'} ({result.score}%)",
        f"{result.summary['passed']}/{result.summary['total']} checks passed"]
    if result.summary.get("warnings"): lines.append(f"{result.summary['warnings']} warnings")
    lines.append("")
    for cat in ["structure", "config", "skills", "hooks", "runtime"]:
        cat_checks = [c for c in result.checks if c.category == cat]
        if not cat_checks: continue
        lines.append(cat.upper())
        lines.append("-" * 40)
        for c in cat_checks:
            icon = "+" if c.passed else ("X" if c.severity == "error" else "!")
            lines.append(f"  {icon} {c.name}: {c.message}")
        lines.append("")
    return "\n".join(lines)

def quick_validate(path_str: str) -> dict:
    path = Path(path_str)
    errors = []
    if not path.exists(): errors.append("Installation directory does not exist")
    if not (path / "settings.json").exists(): errors.append("settings.json not found")
    if not (path / "skills" / "PAI" / "SKILL.md").exists(): errors.append("PAI skill not found")
    if not (path / "MEMORY").exists(): errors.append("MEMORY directory not found")
    return {"valid": len(errors) == 0, "errors": errors}
