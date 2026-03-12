#!/usr/bin/env python3
"""State Check Grader - Verify system state after agent execution."""
import json, os, time
from pathlib import Path
from ..base import BaseGrader, GraderContext, register_grader
from ...Types import GraderConfig, GraderResult

class StateCheckGrader(BaseGrader):
    type = "state_check"
    category = "code_based"

    async def grade(self, context: GraderContext) -> GraderResult:
        start = time.perf_counter()
        params = self.config.params or {}
        checks = []
        working_dir = context.working_dir or os.getcwd()
        if params.get("expect"):
            for key, expected in params["expect"].items():
                check_result = self._check_state(key, expected, context)
                checks.append({"check": f"state.{key}", "passed": check_result["passed"], "expected": expected, "actual": check_result.get("actual")})
        if params.get("check_files"):
            for file_check in params["check_files"]:
                file_path = Path(working_dir) / file_check["path"]
                if not file_path.exists():
                    checks.append({"check": f"file.{file_check['path']}", "passed": False, "expected": "file exists", "actual": "file not found"})
                    continue
                content = file_path.read_text(encoding="utf-8")
                for pattern in file_check.get("contains", []):
                    found = pattern in content
                    checks.append({"check": f"file.{file_check['path']}.contains", "passed": found, "expected": pattern, "actual": "found" if found else "not found"})
                for pattern in file_check.get("not_contains", []):
                    found = pattern in content
                    checks.append({"check": f"file.{file_check['path']}.not_contains", "passed": not found, "expected": f"NOT: {pattern}", "actual": "found (should not exist)" if found else "not found (correct)"})
        if params.get("check_env"):
            for key, expected in params["check_env"].items():
                actual = os.environ.get(key)
                checks.append({"check": f"env.{key}", "passed": actual == expected, "expected": expected, "actual": actual})
        pass_count = sum(1 for c in checks if c["passed"])
        score = pass_count / len(checks) if checks else 1.0
        passed = pass_count == len(checks)
        return self.create_result(score, passed, (time.perf_counter() - start) * 1000,
            reasoning=f"{pass_count}/{len(checks)} state checks passed", details={"checks": checks})

    def _check_state(self, key, expected, context):
        if context.transcript.final_outcome and isinstance(context.transcript.final_outcome, dict):
            if key in context.transcript.final_outcome:
                actual = context.transcript.final_outcome[key]
                return {"passed": self._deep_equal(actual, expected), "actual": actual}
        try:
            import re as _re
            json_match = _re.search(r"\{[\s\S]*\}", context.output)
            if json_match:
                parsed = json.loads(json_match.group())
                if key in parsed:
                    actual = parsed[key]
                    return {"passed": self._deep_equal(actual, expected), "actual": actual}
        except (json.JSONDecodeError, Exception):
            pass
        return {"passed": False, "actual": None}

    def _deep_equal(self, a, b):
        if a == b: return True
        if type(a) != type(b): return False
        if isinstance(b, dict):
            if not isinstance(a, dict): return False
            return all(k in a and self._deep_equal(a[k], v) for k, v in b.items())
        return False

register_grader("state_check", StateCheckGrader)
