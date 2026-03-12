#!/usr/bin/env python3
"""Transcript Capture System - Captures full agent execution trajectories."""
from __future__ import annotations
import json, time, random, string
from datetime import datetime, timezone
from typing import Any, Optional
from ..Types import Transcript, Turn, ToolCall, TranscriptMetrics

class TranscriptCapture:
    def __init__(self, task_id: str, trial_id: str):
        self.task_id = task_id
        self.trial_id = trial_id
        self.turns: list[Turn] = []
        self.tool_calls: list[ToolCall] = []
        self.reasoning_traces: list[str] = []
        self.start_time = time.time() * 1000
        self.first_token_time: Optional[float] = None
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def add_turn(self, role: str, content: str, tokens: Optional[int] = None) -> None:
        if role == "assistant" and self.first_token_time is None:
            self.first_token_time = time.time() * 1000
        if tokens:
            if role in ("user", "system"): self.total_input_tokens += tokens
            else: self.total_output_tokens += tokens
        self.turns.append(Turn(index=len(self.turns), role=role, content=content,
            timestamp=datetime.now(timezone.utc).isoformat(), tokens=tokens))

    def start_tool_call(self, name: str, params: dict) -> str:
        tc_id = f"tc_{int(time.time()*1000)}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=6))}"
        self.tool_calls.append(ToolCall(id=tc_id, name=name, params=params, started_at=datetime.now(timezone.utc).isoformat()))
        return tc_id

    def complete_tool_call(self, tc_id: str, result: Any = None, error: Optional[str] = None) -> None:
        for call in self.tool_calls:
            if call.id == tc_id:
                call.result = result
                call.error = error
                call.completed_at = datetime.now(timezone.utc).isoformat()
                started = datetime.fromisoformat(call.started_at)
                completed = datetime.fromisoformat(call.completed_at)
                call.duration_ms = int((completed - started).total_seconds() * 1000)
                break

    def add_reasoning_trace(self, trace: str) -> None:
        self.reasoning_traces.append(trace)

    def finalize(self, final_outcome: Any = None) -> Transcript:
        now = time.time() * 1000
        wall_time = int(now - self.start_time)
        total_tokens = self.total_input_tokens + self.total_output_tokens
        metrics = TranscriptMetrics(
            n_turns=len(self.turns), n_tool_calls=len(self.tool_calls),
            total_tokens=total_tokens, input_tokens=self.total_input_tokens,
            output_tokens=self.total_output_tokens, wall_time_ms=wall_time,
            time_to_first_token_ms=int(self.first_token_time - self.start_time) if self.first_token_time else None,
            time_to_last_token_ms=wall_time,
            tokens_per_second=self.total_output_tokens / (wall_time / 1000) if wall_time > 0 else None)
        return Transcript(task_id=self.task_id, trial_id=self.trial_id,
            started_at=datetime.fromtimestamp(self.start_time / 1000, tz=timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
            turns=self.turns, tool_calls=self.tool_calls,
            reasoning_traces=self.reasoning_traces if self.reasoning_traces else None,
            final_outcome=final_outcome, metrics=metrics)

def parse_claude_code_transcript(session_log: str, task_id: str, trial_id: str) -> Transcript:
    capture = TranscriptCapture(task_id, trial_id)
    for line in session_log.strip().split("\n"):
        if not line: continue
        try:
            entry = json.loads(line)
            if entry.get("type") == "user": capture.add_turn("user", entry["content"], entry.get("tokens"))
            elif entry.get("type") == "assistant":
                capture.add_turn("assistant", entry["content"], entry.get("tokens"))
                for tc in entry.get("tool_calls", []):
                    tc_id = capture.start_tool_call(tc["name"], tc["params"])
                    if tc.get("result") is not None: capture.complete_tool_call(tc_id, tc["result"], tc.get("error"))
            elif entry.get("type") == "tool_result": capture.add_turn("tool", entry["content"])
            elif entry.get("type") == "thinking": capture.add_reasoning_trace(entry["content"])
        except (json.JSONDecodeError, KeyError): pass
    return capture.finalize()

def create_transcript(task_id: str, trial_id: str, data: dict) -> Transcript:
    capture = TranscriptCapture(task_id, trial_id)
    for turn in data.get("turns", []):
        capture.add_turn(turn["role"], turn["content"])
    for tc in data.get("toolCalls", []):
        tc_id = capture.start_tool_call(tc["name"], tc["params"])
        capture.complete_tool_call(tc_id, tc.get("result"))
    return capture.finalize(data.get("finalOutcome"))
