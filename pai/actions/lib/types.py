#!/usr/bin/env python3
"""
============================================================================
PAI ACTIONS - Core Type Definitions
============================================================================

Actions are atomic, composable units of work with typed inputs and outputs.
They follow Unix philosophy: do one thing well, communicate via JSON streams.

KEY CONCEPTS:
- Actions have Pydantic models for input/output validation
- Actions can run locally or as Cloudflare Workers
- Pipelines chain actions, but ARE actions (same interface)
- Everything is JSON stdin -> processing -> JSON stdout

============================================================================
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ── Execution Context ────────────────────────────────────────────


class TraceContext(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None


class PipelineContext(BaseModel):
    name: str
    step_id: str
    step_index: int


class ActionContext(BaseModel):
    """Execution context passed to every action."""

    mode: Literal["local", "cloud"]
    env: Optional[Dict[str, str]] = None
    trace: Optional[TraceContext] = None
    pipeline: Optional[PipelineContext] = None


# ── Result Wrapper ───────────────────────────────────────────────


class ActionResultMetadata(BaseModel):
    duration_ms: int
    action: str
    mode: Literal["local", "cloud"]


class ActionResult(BaseModel):
    """Result wrapper for action execution."""

    success: bool
    output: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[ActionResultMetadata] = None


# ── Deployment Config ────────────────────────────────────────────


class DeploymentConfig(BaseModel):
    """Deployment hints for worker generation."""

    timeout: Optional[int] = None  # milliseconds, default 30000
    memory: Optional[int] = None  # MB for worker sizing
    secrets: Optional[List[str]] = None
    cpu_intensive: Optional[bool] = None


# ── Action Spec ──────────────────────────────────────────────────


class ActionSpec(BaseModel):
    """
    The core Action specification.

    Every action implements this interface. Pipelines also implement this
    interface, making them composable at the same level as atomic actions.
    """

    name: str  # Unique identifier: category/name (e.g., "parse/topic")
    version: str  # Semantic version
    description: str  # Human-readable description
    input_schema: Any  # Pydantic model class for input validation
    output_schema: Any  # Pydantic model class for output validation
    execute: Optional[Callable[..., Awaitable[Any]]] = Field(default=None, exclude=True)
    deployment: Optional[DeploymentConfig] = None
    tags: Optional[List[str]] = None

    model_config = {"arbitrary_types_allowed": True}


# ── Registry ─────────────────────────────────────────────────────


class ActionRegistryEntry(BaseModel):
    """Registry entry with resolved metadata."""

    name: str
    version: str
    description: str
    path: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    tags: Optional[List[str]] = None
    deployment: Optional[DeploymentConfig] = None


class ActionRegistry(BaseModel):
    """The action registry format."""

    version: str
    generated_at: str
    actions: List[ActionRegistryEntry]


# ── Helper ───────────────────────────────────────────────────────


def define_action(spec: ActionSpec) -> ActionSpec:
    """Helper to create a typed action."""
    return spec


# ── Common Schema Types ─────────────────────────────────────────


class TextInput(BaseModel):
    """Simple text input."""

    text: str = Field(min_length=1)


class UrlInput(BaseModel):
    """URL input."""

    url: str  # Validated as URL


class Topic(BaseModel):
    """Topic structure."""

    name: str
    subtopics: Optional[List[str]] = None
    keywords: Optional[List[str]] = None


class SearchQuery(BaseModel):
    """Search query."""

    query: str
    limit: Optional[int] = Field(default=None, gt=0)


class SearchResult(BaseModel):
    """Search result."""

    url: str
    title: str
    snippet: str
    relevance: Optional[float] = Field(default=None, ge=0, le=1)


class MarkdownOutput(BaseModel):
    """Markdown output."""

    content: str
    word_count: Optional[int] = None


class CommonSchemas:
    """Common schema types for reuse across actions."""

    TextInput = TextInput
    UrlInput = UrlInput
    Topic = Topic
    SearchQuery = SearchQuery
    SearchResult = SearchResult
    MarkdownOutput = MarkdownOutput
