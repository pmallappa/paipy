#!/usr/bin/env python3
"""Static Analysis Grader - Run linters, type checkers, security scanners."""
import re, subprocess, time
from ..base import BaseGrader, GraderContext, register_grader
from ...Types import GraderConfig, GraderResult

class StaticAnalysisGrader(BaseGrader):
    type = "static_analysis"
    category = "code_based"

    async def grade(self, context: GraderContext) -> GraderResult:
        start = time.perf_counter()
        params = self.config.params or {}
        commands = params.get("commands", [])
        if not commands:
            return self.create_result(0, False, (time.perf_counter() - start) * 1000, reasoning="No analysis commands configured")
        working_dir = context.working_dir or "."
        results = []
        for command in commands:
            try:
                proc = subprocess.run(command, shell=True, cwd=working_dir, capture_output=True, text=True, timeout=60)
                output = proc.stdout + proc.stderr
                warnings = self._count_issues(output, "warning")
                errors = self._count_issues(output, "error")
                passed = errors == 0 and (not params.get("fail_on_warning") or warnings == 0)
                results.append({"command": command, "passed": passed, "output": output[-1000:], "warnings": warnings, "errors": errors})
            except Exception as e:
                results.append({"command": command, "passed": False, "output": str(e), "warnings": 0, "errors": 1})
        pass_count = sum(1 for r in results if r["passed"])
        total_errors = sum(r["errors"] for r in results)
        total_warnings = sum(r["warnings"] for r in results)
        score = pass_count / len(commands)
        passed = pass_count == len(commands)
        return self.create_result(score, passed, (time.perf_counter() - start) * 1000,
            reasoning=f"{pass_count}/{len(commands)} checks passed ({total_errors} errors, {total_warnings} warnings)",
            details={"results": results, "total_errors": total_errors, "total_warnings": total_warnings})

    @staticmethod
    def _count_issues(output: str, issue_type: str) -> int:
        patterns = ([r"error:", r"\berror\b", r"failed", r"\[E\d+\]"] if issue_type == "error"
                    else [r"warning:", r"\bwarn\b", r"\[W\d+\]"])
        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, output, re.IGNORECASE))
        return min(count, 100)

register_grader("static_analysis", StaticAnalysisGrader)
