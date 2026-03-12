#!/usr/bin/env python3
"""Regex Match Grader - Pattern matching with regular expressions."""
import re, time
from ..base import BaseGrader, GraderContext, register_grader
from ...Types import GraderConfig, GraderResult

class RegexMatchGrader(BaseGrader):
    type = "regex_match"
    category = "code_based"

    async def grade(self, context: GraderContext) -> GraderResult:
        start = time.perf_counter()
        params = self.config.params or {}
        patterns = params.get("patterns", [])
        if not patterns:
            return self.create_result(0, False, (time.perf_counter() - start) * 1000, reasoning="No patterns configured")
        flags_str = params.get("flags", "gm")
        py_flags = 0
        if "m" in flags_str: py_flags |= re.MULTILINE
        if "i" in flags_str: py_flags |= re.IGNORECASE
        results = []
        for pattern in patterns:
            try:
                matched = bool(re.search(pattern, context.output, py_flags))
                results.append({"pattern": pattern, "matched": matched, "error": None})
            except re.error as e:
                results.append({"pattern": pattern, "matched": False, "error": str(e)})
        match_count = sum(1 for r in results if r["matched"])
        error_count = sum(1 for r in results if r["error"])
        mode = params.get("mode", "all")
        if mode == "all":
            passed = match_count == len(patterns)
            score = match_count / len(patterns)
        else:
            passed = match_count > 0
            score = 1.0 if passed else 0.0
        if error_count > 0:
            score *= (len(patterns) - error_count) / len(patterns)
        return self.create_result(score, passed, (time.perf_counter() - start) * 1000,
            reasoning=f"Matched {match_count}/{len(patterns)} patterns{f' ({error_count} errors)' if error_count else ''} (mode: {mode})",
            details={"results": results, "mode": mode, "flags": flags_str})

register_grader("regex_match", RegexMatchGrader)
