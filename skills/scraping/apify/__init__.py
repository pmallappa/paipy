#!/usr/bin/env python3
"""
Apify Code-First Interface

Replaces token-heavy MCP calls with direct code execution.
Enables in-code filtering and control flow for massive token savings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import httpx


@dataclass
class Actor:
    """Apify actor metadata."""

    id: str = ""
    name: str = ""
    username: str = ""
    title: str = ""
    description: Optional[str] = None
    created_at: Optional[str] = None
    modified_at: Optional[str] = None
    stats: Optional[dict[str, Any]] = None


@dataclass
class ActorRun:
    """Apify actor run information."""

    id: str = ""
    actor_id: str = ""
    status: str = ""  # READY, RUNNING, SUCCEEDED, FAILED, TIMED-OUT, ABORTED
    started_at: str = ""
    finished_at: Optional[str] = None
    default_dataset_id: str = ""
    default_key_value_store_id: str = ""
    build_number: Optional[str] = None
    exit_code: Optional[int] = None
    container_url: Optional[str] = None
    output: Any = None


@dataclass
class DatasetOptions:
    """Options for listing dataset items."""

    offset: Optional[int] = None
    limit: Optional[int] = None
    fields: Optional[list[str]] = None
    omit: Optional[list[str]] = None
    clean: Optional[bool] = None


class ApifyDataset:
    """
    Dataset interface for reading and filtering data.

    KEY FEATURE: Filter data in code BEFORE returning to model context.
    This is where the massive token savings happen!
    """

    BASE_URL = "https://api.apify.com/v2"

    def __init__(self, token: str, dataset_id: str) -> None:
        self._token = token
        self._dataset_id = dataset_id

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def list_items(self, options: Optional[DatasetOptions] = None) -> list[Any]:
        """List dataset items."""
        params: dict[str, Any] = {}
        if options:
            if options.offset is not None:
                params["offset"] = options.offset
            if options.limit is not None:
                params["limit"] = options.limit
            if options.fields is not None:
                params["fields"] = ",".join(options.fields)
            if options.omit is not None:
                params["omit"] = ",".join(options.omit)
            if options.clean is not None:
                params["clean"] = str(options.clean).lower()

        url = f"{self.BASE_URL}/datasets/{self._dataset_id}/items"
        resp = httpx.get(url, headers=self._headers(), params=params, timeout=120)
        resp.raise_for_status()
        return resp.json()

    def get_all_items(self) -> list[Any]:
        """
        Get all dataset items (handles pagination automatically).

        WARNING: For large datasets, use list_items with limit
        or filter in code to avoid excessive tokens.
        """
        all_items: list[Any] = []
        offset = 0
        limit = 1000

        while True:
            items = self.list_items(DatasetOptions(offset=offset, limit=limit))
            all_items.extend(items)
            if len(items) < limit:
                break
            offset += limit

        return all_items

    def filter(self, predicate: Callable[[Any], bool]) -> list[Any]:
        """
        Filter items by predicate function.

        Convenience method -- you can also filter using standard
        list comprehensions after list_items().
        """
        items = self.get_all_items()
        return [item for item in items if predicate(item)]

    def top(self, key: Callable[[Any], Any], limit: int, *, reverse: bool = True) -> list[Any]:
        """
        Get top N items by sort key.

        Args:
            key: Sort key function.
            limit: Number of items to return.
            reverse: If True (default), sort descending.
        """
        items = self.get_all_items()
        items.sort(key=key, reverse=reverse)
        return items[:limit]


class Apify:
    """Main Apify client for code-first operations."""

    BASE_URL = "https://api.apify.com/v2"

    def __init__(self, token: Optional[str] = None) -> None:
        self._token = token or os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_API_KEY") or ""

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
    ) -> list[Actor]:
        """
        Search for actors by keyword.

        Fetches actors and filters client-side by query (name, title, description).
        """
        fetch_limit = max(limit * 3, 30)
        url = f"{self.BASE_URL}/acts"
        params = {"limit": fetch_limit, "offset": offset}
        resp = httpx.get(url, headers=self._headers(), params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", {}).get("items", [])

        query_words = query.lower().split()
        filtered: list[Actor] = []
        for item in items:
            name = (item.get("name") or "").lower()
            title = (item.get("title") or "").lower()
            description = (item.get("description") or "").lower()
            username = (item.get("username") or "").lower()
            search_text = f"{name} {title} {description} {username}"

            if any(word in search_text for word in query_words):
                filtered.append(
                    Actor(
                        id=item.get("id", ""),
                        name=item.get("name", ""),
                        username=item.get("username", ""),
                        title=item.get("title", ""),
                        description=item.get("description"),
                        created_at=item.get("createdAt"),
                        modified_at=item.get("modifiedAt"),
                        stats=item.get("stats"),
                    )
                )

        return filtered[:limit]

    def call_actor(
        self,
        actor_id: str,
        input_data: Any,
        options: Optional[dict[str, Any]] = None,
    ) -> ActorRun:
        """
        Call (execute) an actor.

        Args:
            actor_id: Actor ID or "username/actor-name".
            input_data: Actor input configuration.
            options: Runtime options (memory, timeout, build).
        """
        url = f"{self.BASE_URL}/acts/{actor_id}/runs"
        params: dict[str, Any] = {}
        if options:
            if options.get("memory"):
                params["memory"] = options["memory"]
            if options.get("timeout"):
                params["timeout"] = options["timeout"]
            if options.get("build"):
                params["build"] = options["build"]

        resp = httpx.post(
            url,
            headers={**self._headers(), "Content-Type": "application/json"},
            json=input_data,
            params=params,
            timeout=60,
        )
        resp.raise_for_status()
        run = resp.json().get("data", {})

        return ActorRun(
            id=run.get("id", ""),
            actor_id=run.get("actId", ""),
            status=run.get("status", ""),
            started_at=run.get("startedAt", ""),
            finished_at=run.get("finishedAt"),
            default_dataset_id=run.get("defaultDatasetId", ""),
            default_key_value_store_id=run.get("defaultKeyValueStoreId", ""),
            build_number=run.get("buildNumber"),
            exit_code=run.get("exitCode"),
            container_url=run.get("containerUrl"),
            output=run.get("output"),
        )

    def get_dataset(self, dataset_id: str) -> ApifyDataset:
        """Get dataset interface for reading and filtering data."""
        return ApifyDataset(self._token, dataset_id)

    def get_run(self, run_id: str) -> ActorRun:
        """Get actor run status."""
        url = f"{self.BASE_URL}/actor-runs/{run_id}"
        resp = httpx.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        run = resp.json().get("data", {})

        return ActorRun(
            id=run.get("id", ""),
            actor_id=run.get("actId", ""),
            status=run.get("status", ""),
            started_at=run.get("startedAt", ""),
            finished_at=run.get("finishedAt"),
            default_dataset_id=run.get("defaultDatasetId", ""),
            default_key_value_store_id=run.get("defaultKeyValueStoreId", ""),
            build_number=run.get("buildNumber"),
            exit_code=run.get("exitCode"),
            container_url=run.get("containerUrl"),
            output=run.get("output"),
        )

    def wait_for_run(
        self,
        run_id: str,
        *,
        wait_secs: int = 300,
    ) -> ActorRun:
        """Wait for actor run to finish."""
        url = f"{self.BASE_URL}/actor-runs/{run_id}"
        params = {"waitForFinish": wait_secs}
        resp = httpx.get(url, headers=self._headers(), params=params, timeout=wait_secs + 30)
        resp.raise_for_status()
        run = resp.json().get("data", {})

        return ActorRun(
            id=run.get("id", ""),
            actor_id=run.get("actId", ""),
            status=run.get("status", ""),
            started_at=run.get("startedAt", ""),
            finished_at=run.get("finishedAt"),
            default_dataset_id=run.get("defaultDatasetId", ""),
            default_key_value_store_id=run.get("defaultKeyValueStoreId", ""),
            build_number=run.get("buildNumber"),
            exit_code=run.get("exitCode"),
            container_url=run.get("containerUrl"),
            output=run.get("output"),
        )
