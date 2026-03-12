#!/usr/bin/env python3
"""
============================================================================
PAI ACTIONS v2 - Shareable Action Types
============================================================================

Actions are portable, self-contained units that:
- Use JSON Schema (universal) not Pydantic (Python-specific)
- Declare capabilities needed, don't import implementations
- Can be packaged, shared, downloaded, run anywhere

Package structure:
  action.json  - Metadata, JSON schemas, capability requirements
  action.py    - Implementation (receives capabilities via context)

============================================================================
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional

from pydantic import BaseModel


# ── Capabilities ─────────────────────────────────────────────────


class LLMOptions(BaseModel):
    """Options for LLM inference."""

    tier: Optional[Literal["fast", "standard", "smart"]] = None
    system: Optional[str] = None
    json: Optional[bool] = None
    max_tokens: Optional[int] = None


class LLMResponse(BaseModel):
    """Response from LLM inference."""

    text: str
    json: Optional[Any] = None
    usage: Optional[Dict[str, int]] = None


class ShellResult(BaseModel):
    """Result from shell command execution."""

    stdout: str
    stderr: str
    code: int


class KVStore:
    """Key-value storage interface."""

    async def get(self, key: str) -> Optional[str]:
        raise NotImplementedError

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        raise NotImplementedError


class ActionCapabilities:
    """
    Capabilities that actions can request.
    Runtime provides implementations - actions don't import them.
    """

    def __init__(self) -> None:
        self.llm: Optional[Callable[..., Awaitable[LLMResponse]]] = None
        self.fetch: Optional[Callable[..., Awaitable[Any]]] = None
        self.shell: Optional[Callable[[str], Awaitable[ShellResult]]] = None
        self.read_file: Optional[Callable[[str], Awaitable[str]]] = None
        self.write_file: Optional[Callable[[str, str], Awaitable[None]]] = None
        self.kv: Optional[KVStore] = None


# ── Context ──────────────────────────────────────────────────────


class EnvContext(BaseModel):
    """Execution environment."""

    mode: Literal["local", "cloud"]
    secrets: Optional[List[str]] = None


class TraceContext(BaseModel):
    """Trace for observability."""

    trace_id: str
    span_id: str


class PipelineContext(BaseModel):
    """Pipeline context when running in a pipeline."""

    name: str
    step_id: str


class ActionContext:
    """Execution context passed to every action."""

    def __init__(
        self,
        capabilities: Optional[ActionCapabilities] = None,
        env: Optional[EnvContext] = None,
        trace: Optional[TraceContext] = None,
        pipeline: Optional[PipelineContext] = None,
    ) -> None:
        self.capabilities = capabilities or ActionCapabilities()
        self.env = env or EnvContext(mode="local")
        self.trace = trace
        self.pipeline = pipeline


# ── Manifest ─────────────────────────────────────────────────────


class AuthorInfo(BaseModel):
    """Author information."""

    name: str
    url: Optional[str] = None


class DeploymentConfig(BaseModel):
    """Deployment hints."""

    timeout: Optional[int] = None
    memory: Optional[int] = None
    secrets: Optional[List[str]] = None


class ActionManifest(BaseModel):
    """Action manifest - the action.json file."""

    name: str  # Unique name: category/name
    version: str  # Semantic version
    description: str  # Human description
    input: Dict[str, Any]  # Input schema (JSON Schema draft-07)
    output: Dict[str, Any]  # Output schema (JSON Schema draft-07)
    requires: Optional[List[Literal["llm", "fetch", "shell", "readFile", "writeFile", "kv"]]] = None
    tags: Optional[List[str]] = None
    author: Optional[AuthorInfo] = None
    license: Optional[str] = None
    deployment: Optional[DeploymentConfig] = None


# ── Implementation Interface ─────────────────────────────────────


class ActionImplementation:
    """The action implementation interface."""

    async def execute(self, input_data: Any, ctx: ActionContext) -> Any:
        raise NotImplementedError


# ── Result ───────────────────────────────────────────────────────


class ActionResultMetadata(BaseModel):
    """Metadata for action result."""

    duration_ms: int
    action: str
    version: str


class ActionResult(BaseModel):
    """Result wrapper."""

    success: bool
    output: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[ActionResultMetadata] = None


# ── Schema Validation ────────────────────────────────────────────


def validate_schema(
    data: Any, schema: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Helper to validate input/output against JSON Schema.
    Uses jsonschema for validation.
    """
    try:
        import jsonschema

        jsonschema.validate(instance=data, schema=schema)
        return {"valid": True}
    except jsonschema.ValidationError as e:
        return {"valid": False, "errors": [str(e.message)]}
    except ImportError:
        # Fallback: skip validation if jsonschema not installed
        return {"valid": True}
