#!/usr/bin/env python3
"""Base Grader Interface - All graders implement this for consistent execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Type

from ..Types import GraderConfig, GraderResult, GraderType, Transcript


@dataclass
class GraderContext:
    task_id: str
    trial_id: str
    transcript: Transcript
    output: str
    working_dir: Optional[str] = None
    reference: Optional[str] = None


class BaseGrader(ABC):
    type: GraderType
    category: str  # 'code_based' | 'model_based' | 'human'

    def __init__(self, config: GraderConfig):
        self.config = config

    @abstractmethod
    async def grade(self, context: GraderContext) -> GraderResult:
        ...

    def get_weight(self) -> float:
        return self.config.weight if self.config.weight is not None else 1.0

    def is_required(self) -> bool:
        return self.config.required if self.config.required is not None else False

    def create_result(
        self,
        score: float,
        passed: bool,
        duration_ms: float,
        reasoning: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> GraderResult:
        return GraderResult(
            grader_type=self.type,
            weight=self.get_weight(),
            score=score,
            passed=passed,
            duration_ms=duration_ms,
            reasoning=reasoning,
            details=details,
        )


# Grader registry for dynamic instantiation
_grader_registry: dict[str, Type[BaseGrader]] = {}


def register_grader(grader_type: str, grader_class: Type[BaseGrader]) -> None:
    _grader_registry[grader_type] = grader_class


def create_grader(config: GraderConfig) -> BaseGrader:
    grader_class = _grader_registry.get(config.type)
    if not grader_class:
        raise ValueError(f"Unknown grader type: {config.type}")
    return grader_class(config)


def list_graders() -> list[str]:
    return list(_grader_registry.keys())


async def run_graders(
    graders: list[BaseGrader],
    context: GraderContext,
) -> dict:
    results: list[GraderResult] = []
    total_weight = 0.0
    weighted_sum = 0.0
    all_required_passed = True

    for grader in graders:
        result = await grader.grade(context)
        results.append(result)

        weight = grader.get_weight()
        total_weight += weight
        weighted_sum += result.score * weight

        if grader.is_required() and not result.passed:
            all_required_passed = False

    aggregate_score = weighted_sum / total_weight if total_weight > 0 else 0
    passed = all_required_passed and aggregate_score >= 0.5

    return {"results": results, "aggregate_score": aggregate_score, "passed": passed}
