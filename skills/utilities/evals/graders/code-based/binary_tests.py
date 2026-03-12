#!/usr/bin/env python3
"""Binary Tests Grader - Run actual test files and check pass/fail."""
import subprocess, time
from ..base import BaseGrader, GraderContext, register_grader
from ...Types import GraderConfig, GraderResult

class BinaryTestsGrader(BaseGrader):
    type = "binary_tests"
    category = "code_based"

    async def grade(self, context: GraderContext) -> GraderResult:
        start = time.perf_counter()
        params = self.config.params or {}
        test_files = params.get("test_files", [])
        if not test_files:
            return self.create_result(0, False, (time.perf_counter() - start) * 1000, reasoning="No test files configured")
        working_dir = context.working_dir or "."
        timeout_s = (params.get("timeout_ms") or 60000) // 1000
        results = []
        for test_file in test_files:
            try:
                command = params.get("test_command") or self._detect_test_command(test_file)
                proc = subprocess.run(f"{command} {test_file}", shell=True, cwd=working_dir, capture_output=True, text=True, timeout=timeout_s)
                passed = proc.returncode == 0
                results.append({"file": test_file, "passed": passed, "output": proc.stdout[-500:], "error": None if passed else proc.stderr[-500:]})
            except Exception as e:
                results.append({"file": test_file, "passed": False, "output": "", "error": str(e)})
        pass_count = sum(1 for r in results if r["passed"])
        score = pass_count / len(test_files)
        passed = pass_count == len(test_files)
        return self.create_result(score, passed, (time.perf_counter() - start) * 1000,
            reasoning=f"{pass_count}/{len(test_files)} tests passed",
            details={"results": results, "working_dir": working_dir})

    @staticmethod
    def _detect_test_command(file: str) -> str:
        if file.endswith(".py"): return "python -m pytest"
        if file.endswith(".ts"): return "bun test"
        if file.endswith(".js"): return "node --test"
        if file.endswith(".go"): return "go test"
        if file.endswith(".rs"): return "cargo test --"
        return "python -m pytest"

register_grader("binary_tests", BinaryTestsGrader)
