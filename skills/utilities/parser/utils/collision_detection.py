#!/usr/bin/env python3
"""
Entity Collision Detection Utility

Manages entity GUIDs across parsed content to prevent duplicates
and build a knowledge graph of people, companies, links, and sources.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


ENTITY_INDEX_PATH = Path(__file__).parent.parent / "entity-index.json"


@dataclass
class PersonEntity:
    id: str
    name: str
    first_seen: str
    occurrences: int
    content_ids: list[str] = field(default_factory=list)


@dataclass
class CompanyEntity:
    id: str
    name: str
    domain: Optional[str]
    first_seen: str
    occurrences: int
    content_ids: list[str] = field(default_factory=list)


@dataclass
class LinkEntity:
    id: str
    url: str
    first_seen: str
    occurrences: int
    content_ids: list[str] = field(default_factory=list)


@dataclass
class SourceEntity:
    id: str
    url: Optional[str]
    author: Optional[str]
    publication: Optional[str]
    first_seen: str
    occurrences: int
    content_ids: list[str] = field(default_factory=list)


@dataclass
class EntityIndex:
    version: str = "1.0.0"
    last_updated: str = ""
    people: dict[str, dict] = field(default_factory=dict)
    companies: dict[str, dict] = field(default_factory=dict)
    links: dict[str, dict] = field(default_factory=dict)
    sources: dict[str, dict] = field(default_factory=dict)


def normalize_name(name: str) -> str:
    """Normalize person/company name for canonical ID."""
    return name.lower().strip()


def normalize_url(url: str) -> str:
    """Normalize URL for canonical ID."""
    return url.lower().strip().rstrip("/")


def get_source_canonical_id(source: dict) -> str:
    """Compute canonical ID for source."""
    if source.get("url"):
        return normalize_url(source["url"])
    author = normalize_name(source.get("author") or "")
    publication = normalize_name(source.get("publication") or "")
    return f"{author}|{publication}"


async def load_entity_index() -> dict:
    """Load entity index from disk."""
    try:
        data = ENTITY_INDEX_PATH.read_text(encoding="utf-8")
        return json.loads(data)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "version": "1.0.0",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "people": {},
            "companies": {},
            "links": {},
            "sources": {},
        }


async def save_entity_index(index: dict) -> None:
    """Save entity index to disk."""
    index["last_updated"] = datetime.now(timezone.utc).isoformat()
    temp_path = str(ENTITY_INDEX_PATH) + ".tmp"

    Path(temp_path).write_text(json.dumps(index, indent=2), encoding="utf-8")
    Path(temp_path).rename(ENTITY_INDEX_PATH)


def get_or_create_person(person_data: dict, entity_index: dict, content_id: str) -> str:
    """Get existing GUID or create new one for person."""
    canonical_id = normalize_name(person_data["name"])

    if canonical_id in entity_index["people"]:
        existing = entity_index["people"][canonical_id]
        if content_id not in existing["content_ids"]:
            existing["occurrences"] += 1
            existing["content_ids"].append(content_id)
        return existing["id"]
    else:
        person_id = str(uuid.uuid4())
        entity_index["people"][canonical_id] = {
            "id": person_id,
            "name": person_data["name"],
            "first_seen": datetime.now(timezone.utc).isoformat(),
            "occurrences": 1,
            "content_ids": [content_id],
        }
        return person_id


def get_or_create_company(company_data: dict, entity_index: dict, content_id: str) -> str:
    """Get existing GUID or create new one for company."""
    canonical_id = (
        company_data["domain"].lower().strip()
        if company_data.get("domain")
        else normalize_name(company_data["name"])
    )

    if canonical_id in entity_index["companies"]:
        existing = entity_index["companies"][canonical_id]
        if content_id not in existing["content_ids"]:
            existing["occurrences"] += 1
            existing["content_ids"].append(content_id)
        return existing["id"]
    else:
        company_id = str(uuid.uuid4())
        entity_index["companies"][canonical_id] = {
            "id": company_id,
            "name": company_data["name"],
            "domain": company_data.get("domain"),
            "first_seen": datetime.now(timezone.utc).isoformat(),
            "occurrences": 1,
            "content_ids": [content_id],
        }
        return company_id


def get_or_create_link(link_data: dict, entity_index: dict, content_id: str) -> str:
    """Get existing GUID or create new one for link."""
    canonical_id = normalize_url(link_data["url"])

    if canonical_id in entity_index["links"]:
        existing = entity_index["links"][canonical_id]
        if content_id not in existing["content_ids"]:
            existing["occurrences"] += 1
            existing["content_ids"].append(content_id)
        return existing["id"]
    else:
        link_id = str(uuid.uuid4())
        entity_index["links"][canonical_id] = {
            "id": link_id,
            "url": link_data["url"],
            "first_seen": datetime.now(timezone.utc).isoformat(),
            "occurrences": 1,
            "content_ids": [content_id],
        }
        return link_id


def get_or_create_source(source_data: dict, entity_index: dict, content_id: str) -> str:
    """Get existing GUID or create new one for source."""
    canonical_id = get_source_canonical_id(source_data)

    if canonical_id in entity_index["sources"]:
        existing = entity_index["sources"][canonical_id]
        if content_id not in existing["content_ids"]:
            existing["occurrences"] += 1
            existing["content_ids"].append(content_id)
        return existing["id"]
    else:
        source_id = str(uuid.uuid4())
        entity_index["sources"][canonical_id] = {
            "id": source_id,
            "url": source_data.get("url"),
            "author": source_data.get("author"),
            "publication": source_data.get("publication"),
            "first_seen": datetime.now(timezone.utc).isoformat(),
            "occurrences": 1,
            "content_ids": [content_id],
        }
        return source_id


def is_url_already_parsed(url: str, entity_index: dict) -> bool:
    """Check if URL has already been parsed."""
    canonical_id = normalize_url(url)
    link_data = entity_index["links"].get(canonical_id)
    return bool(link_data and len(link_data.get("content_ids", [])) > 0)


def get_existing_content_id(url: str, entity_index: dict) -> Optional[str]:
    """Get content ID for already-parsed URL."""
    canonical_id = normalize_url(url)
    link_data = entity_index["links"].get(canonical_id)

    if link_data and len(link_data.get("content_ids", [])) > 0:
        return link_data["content_ids"][0]
    return None


async def process_content_entities(
    content_id: str,
    extracted_data: dict,
) -> dict:
    """Process all entities for a piece of content and assign GUIDs."""
    entity_index = await load_entity_index()

    people = [
        {**person, "id": get_or_create_person(person, entity_index, content_id)}
        for person in extracted_data.get("people", [])
    ]

    companies = [
        {**company, "id": get_or_create_company(company, entity_index, content_id)}
        for company in extracted_data.get("companies", [])
    ]

    links = [
        {**link, "id": get_or_create_link(link, entity_index, content_id)}
        for link in extracted_data.get("links", [])
    ]

    sources = [
        {**source, "id": get_or_create_source(source, entity_index, content_id)}
        for source in extracted_data.get("sources", [])
    ]

    await save_entity_index(entity_index)

    return {"people": people, "companies": companies, "links": links, "sources": sources}
