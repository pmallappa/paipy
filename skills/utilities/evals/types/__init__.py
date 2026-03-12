#!/usr/bin/env python3
"""
Evals Type System
Based on Anthropic's "Demystifying Evals for AI Agents" (Jan 2026)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

EvalDomain = Literal["coding", "conversational", "research", "computer_use", "general"]
EvalType = Literal["capability", "regression"]
TaskStatus = Literal["pending", "running", "passed", "failed", "error"]

GraderType = Literal[
    "string_match", "regex_match", "binary_tests", "static_analysis",
    "state_check", "tool_calls", "json_schema", "outcome_verification",
    "llm_rubric", "natural_language_assert", "pairwise_comparison",
    "reference_comparison", "human_review", "spot_check",
]


@dataclass
class GraderConfig:
    type: GraderType
    weight: float = 1.0
    required: bool = False
    params: Optional[dict[str, Any]] = None


@dataclass
class MetricConfig:
    type: Literal["transcript", "latency", "custom"]
    metrics: list[str] = field(default_factory=list)


@dataclass
class Task:
    id: str
    description: str
    type: EvalType
    domain: EvalDomain
    graders: list[GraderConfig] = field(default_factory=list)
    setup: Optional[dict[str, Any]] = None
    tracked_metrics: Optional[list[MetricConfig]] = None
    trials: int = 1
    pass_threshold: float = 0.75
    reference_solution: Optional[str] = None
    tags: Optional[list[str]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    source: Optional[Literal["manual", "failure_log", "generated"]] = None


@dataclass
class ToolCall:
    id: str
    name: str
    params: dict[str, Any]
    started_at: str
    result: Any = None
    error: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None


@dataclass
class Turn:
    index: int
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    timestamp: str
    tool_call: Optional[ToolCall] = None
    tokens: Optional[int] = None


@dataclass
class TranscriptMetrics:
    n_turns: int
    n_tool_calls: int
    total_tokens: int
    input_tokens: int
    output_tokens: int
    wall_time_ms: int
    time_to_first_token_ms: Optional[int] = None
    time_to_last_token_ms: Optional[int] = None
    tokens_per_second: Optional[float] = None


@dataclass
class Transcript:
    task_id: str
    trial_id: str
    started_at: str
    turns: list[Turn]
    tool_calls: list[ToolCall]
    metrics: TranscriptMetrics
    completed_at: Optional[str] = None
    reasoning_traces: Optional[list[str]] = None
    final_outcome: Any = None


@dataclass
class GraderResult:
    grader_type: GraderType
    weight: float
    score: float
    passed: bool
    duration_ms: float
    reasoning: Optional[str] = None
    details: Optional[dict[str, Any]] = None


@dataclass
class Trial:
    id: str
    task_id: str
    trial_number: int
    status: TaskStatus
    started_at: str
    transcript: Transcript
    grader_results: list[GraderResult]
    score: float
    passed: bool
    completed_at: Optional[str] = None
    error: Optional[str] = None


@dataclass
class EvalRun:
    id: str
    task_id: str
    trials: list[Trial]
    n_trials: int
    pass_rate: float
    mean_score: float
    std_dev: float
    pass_at_k: float
    pass_to_k: float
    started_at: str
    total_duration_ms: int
    completed_at: Optional[str] = None
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


@dataclass
class EvalSuite:
    name: str
    description: str
    type: EvalType
    tasks: list[str]
    created_at: str
    domain: Optional[EvalDomain] = None
    pass_threshold: Optional[float] = None
    saturation_threshold: Optional[float] = None
    updated_at: Optional[str] = None


@dataclass
class SaturationStatus:
    suite_id: str
    pass_rate_history: list[dict]
    saturated: bool
    consecutive_above_threshold: int
    recommended_action: Literal["graduate_to_regression", "add_harder_cases", "keep"]


@dataclass
class HumanReview:
    id: str
    trial_id: str
    task_id: str
    status: Literal["pending", "in_progress", "completed"]
    created_at: str
    reviewer: Optional[str] = None
    score: Optional[float] = None
    passed: Optional[bool] = None
    notes: Optional[str] = None
    model_score: Optional[float] = None
    agreement: Optional[bool] = None
    completed_at: Optional[str] = None


@dataclass
class FailureLog:
    id: str
    timestamp: str
    description: str
    category: str
    severity: Literal["low", "medium", "high", "critical"]
    task_context: Optional[str] = None
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    transcript: Optional[Transcript] = None
    converted_to_task: Optional[str] = None


@dataclass
class AlgorithmEvalRequest:
    isc_row: int
    suite: str
    verification_criteria: Optional[str] = None


@dataclass
class AlgorithmEvalResult:
    isc_row: int
    suite: str
    passed: bool
    score: float
    summary: str
    run_id: str
