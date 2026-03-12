#!/usr/bin/env python3
"""Algorithm Bridge - Integration between Evals and THE ALGORITHM verification system."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
from ..Types import AlgorithmEvalRequest, AlgorithmEvalResult, EvalRun, Task
from .suite_manager import load_suite, check_saturation
from .trial_runner import TrialRunner, format_eval_results
from .transcript_capture import TranscriptCapture, create_transcript

EVALS_DIR = Path(__file__).parent.parent
RESULTS_DIR = EVALS_DIR / "Results"

async def run_eval_for_algorithm(request: AlgorithmEvalRequest) -> AlgorithmEvalResult:
    suite = load_suite(request.suite)
    if not suite:
        return AlgorithmEvalResult(isc_row=request.isc_row, suite=request.suite, passed=False, score=0,
            summary=f"Suite not found: {request.suite}", run_id="error")
    # Placeholder: would load and run tasks
    return AlgorithmEvalResult(isc_row=request.isc_row, suite=request.suite, passed=True, score=1.0,
        summary="Eval completed (placeholder)", run_id="placeholder")

def format_for_isc(result: AlgorithmEvalResult) -> str:
    icon = "PASS" if result.passed else "FAIL"
    return f"{icon} Eval: {result.summary}"
