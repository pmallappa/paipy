#!/usr/bin/env python3
"""Trial Runner - Execute multiple trials and calculate pass@k / pass^k metrics."""
from __future__ import annotations
import math, time, random, string
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from ..Types import Task, Trial, EvalRun, GraderResult, Transcript
from ..Graders.base import create_grader, run_graders, GraderContext
from .transcript_capture import TranscriptCapture

class TrialRunner:
    def __init__(self, task: Task, executor, on_trial_complete=None):
        self.task = task
        self.executor = executor
        self.on_trial_complete = on_trial_complete

    async def run(self) -> EvalRun:
        task = self.task
        n_trials = task.trials or 1
        trials: list[Trial] = []
        run_id = f"run_{int(time.time()*1000)}_{''.join(random.choices(string.ascii_lowercase+string.digits, k=6))}"
        start_time = time.time() * 1000
        graders = [create_grader(config) for config in task.graders]
        for i in range(n_trials):
            trial_id = f"trial_{i+1}"
            trial_start = time.time() * 1000
            try:
                execution = await self.executor(task, i + 1)
                ctx = GraderContext(task_id=task.id, trial_id=trial_id, transcript=execution["transcript"],
                    output=execution["output"], working_dir=task.setup.get("working_dir") if task.setup else None,
                    reference=task.reference_solution)
                result = await run_graders(graders, ctx)
                trial = Trial(id=trial_id, task_id=task.id, trial_number=i+1,
                    status="passed" if result["passed"] else "failed",
                    started_at=datetime.fromtimestamp(trial_start/1000, tz=timezone.utc).isoformat(),
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    transcript=execution["transcript"], grader_results=result["results"],
                    score=result["aggregate_score"], passed=result["passed"])
            except Exception as e:
                cap = TranscriptCapture(task.id, trial_id)
                trial = Trial(id=trial_id, task_id=task.id, trial_number=i+1, status="error",
                    started_at=datetime.fromtimestamp(trial_start/1000, tz=timezone.utc).isoformat(),
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    transcript=cap.finalize(), grader_results=[], score=0, passed=False, error=str(e))
            trials.append(trial)
            if self.on_trial_complete: self.on_trial_complete(trial)
        pass_count = sum(1 for t in trials if t.passed)
        scores = [t.score for t in trials]
        mean_score = sum(scores) / len(scores)
        variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
        std_dev = math.sqrt(variance)
        pass_at_k = 1.0 if any(t.passed for t in trials) else 0.0
        pass_to_k = pass_count / n_trials
        return EvalRun(id=run_id, task_id=task.id, trials=trials, n_trials=n_trials,
            pass_rate=pass_count/n_trials, mean_score=mean_score, std_dev=std_dev,
            pass_at_k=pass_at_k, pass_to_k=pass_to_k,
            started_at=datetime.fromtimestamp(start_time/1000, tz=timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
            total_duration_ms=int(time.time()*1000 - start_time))

def calculate_pass_at_k_for_k(trials: list[Trial], k: int) -> float:
    n = len(trials)
    c = sum(1 for t in trials if t.passed)
    if k > n: return 0.0
    if c == 0: return 0.0
    if c >= k: return 1.0
    fail_prob = 1.0
    for i in range(k):
        fail_prob *= (n - c - i) / (n - i)
    return 1.0 - fail_prob

def format_eval_results(run: EvalRun) -> str:
    lines = [f"## Evaluation Results: {run.task_id}", "", f"**Run ID:** {run.id}",
        f"**Duration:** {run.total_duration_ms/1000:.2f}s", "", "### Summary", "",
        "| Metric | Value |", "|--------|-------|",
        f"| Trials | {run.n_trials} |", f"| Pass Rate | {run.pass_rate*100:.1f}% |",
        f"| Mean Score | {run.mean_score:.3f} |", f"| Std Dev | {run.std_dev:.3f} |",
        f"| pass@k | {run.pass_at_k*100:.1f}% |", f"| pass^k | {run.pass_to_k*100:.1f}% |"]
    return "\n".join(lines)
