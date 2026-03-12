#!/usr/bin/env python3
"""String Match Grader - Fast deterministic check for exact or pattern matching."""
from ..base import BaseGrader, GraderContext, register_grader
from ...Types import GraderConfig, GraderResult
import time

class StringMatchGrader(BaseGrader):
    type = "string_match"
    category = "code_based"

    async def grade(self, context: GraderContext) -> GraderResult:
        start = time.perf_counter()
        params = self.config.params or {}
        patterns = params.get("patterns", [])
        if not patterns:
            return self.create_result(0, False, (time.perf_counter() - start) * 1000, reasoning="No patterns configured")
        case_sensitive = params.get("case_sensitive", False)
        output = context.output if case_sensitive else context.output.lower()
        check_patterns = patterns if case_sensitive else [p.lower() for p in patterns]
        matches = [p in output for p in check_patterns]
        match_count = sum(matches)
        mode = params.get("mode", "all")
        if mode == "all":
            passed = match_count == len(check_patterns)
            score = match_count / len(check_patterns)
        else:
            passed = match_count > 0
            score = 1.0 if passed else 0.0
        return self.create_result(score, passed, (time.perf_counter() - start) * 1000,
            reasoning=f"Matched {match_count}/{len(patterns)} patterns (mode: {mode})",
            details={"patterns": check_patterns, "matches": [{"pattern": p, "matched": m} for p, m in zip(check_patterns, matches)], "mode": mode})

register_grader("string_match", StringMatchGrader)
