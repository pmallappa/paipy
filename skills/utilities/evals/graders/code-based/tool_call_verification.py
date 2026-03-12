#!/usr/bin/env python3
"""Tool Call Verification Grader - Verify that specific tools were called."""
import json, re, time
from ..base import BaseGrader, GraderContext, register_grader
from ...Types import GraderConfig, GraderResult

class ToolCallVerificationGrader(BaseGrader):
    type = "tool_calls"
    category = "code_based"

    async def grade(self, context: GraderContext) -> GraderResult:
        start = time.perf_counter()
        params = self.config.params or {}
        tool_calls = context.transcript.tool_calls
        checks = []
        if params.get("required"):
            for req in params["required"]:
                matching = None
                for tc in tool_calls:
                    if tc.name != req["tool"]: continue
                    if req.get("params"):
                        match = True
                        for k, expected in req["params"].items():
                            actual = tc.params.get(k)
                            if isinstance(expected, str) and "*" in expected:
                                pattern = "^" + expected.replace("*", ".*") + "$"
                                if not re.match(pattern, str(actual)): match = False; break
                            elif actual != expected: match = False; break
                        if not match: continue
                    matching = tc; break
                checks.append({"check": f"required.{req['tool']}", "passed": matching is not None,
                    "details": f"Found: {json.dumps(dict(matching.params) if matching else {})[:100]}" if matching else f"Not found in {len(tool_calls)} tool calls"})
        if params.get("forbidden"):
            for forbidden in params["forbidden"]:
                found = any(tc.name == forbidden for tc in tool_calls)
                checks.append({"check": f"forbidden.{forbidden}", "passed": not found, "details": "Found (should not exist)" if found else "Not found (correct)"})
        if params.get("sequence"):
            tool_order = [tc.name for tc in tool_calls]
            seq_idx = 0
            for tool in tool_order:
                if seq_idx < len(params["sequence"]) and tool == params["sequence"][seq_idx]:
                    seq_idx += 1
            complete = seq_idx == len(params["sequence"])
            checks.append({"check": "sequence", "passed": complete,
                "details": f"Sequence complete: {' -> '.join(params['sequence'])}" if complete else f"Incomplete: found {seq_idx}/{len(params['sequence'])} in order"})
        if params.get("max_calls") is not None:
            within = len(tool_calls) <= params["max_calls"]
            checks.append({"check": "max_calls", "passed": within, "details": f"{len(tool_calls)} calls (max: {params['max_calls']})"})
        pass_count = sum(1 for c in checks if c["passed"])
        score = pass_count / len(checks) if checks else 1.0
        passed = pass_count == len(checks)
        return self.create_result(score, passed, (time.perf_counter() - start) * 1000,
            reasoning=f"{pass_count}/{len(checks)} tool call checks passed",
            details={"checks": checks, "total_tool_calls": len(tool_calls), "tool_call_summary": [tc.name for tc in tool_calls]})

register_grader("tool_calls", ToolCallVerificationGrader)
