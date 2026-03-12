#!/usr/bin/env python3
"""Schema validation utilities for Content Schema."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

# Validation constants
UUID_REGEX = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.IGNORECASE)

VALID_CONTENT_TYPES = ["article", "video", "pdf", "newsletter", "podcast", "tweet_thread", "generic"]
VALID_PERSON_ROLES = ["author", "subject", "mentioned", "quoted", "expert", "interviewer", "interviewee"]
VALID_IMPORTANCE = ["primary", "secondary", "minor"]
VALID_MENTION_TYPES = ["subject", "source", "example", "competitor", "partner", "acquisition", "product", "other"]
VALID_SENTIMENTS = ["positive", "neutral", "negative", "mixed"]
VALID_LINK_TYPES = ["reference", "source", "related", "tool", "research", "product", "social", "other"]
VALID_POSITIONS = ["beginning", "middle", "end", "sidebar", "footer"]
VALID_SOURCE_TYPES = ["research_paper", "news_article", "blog_post", "twitter_thread", "podcast", "video", "book", "other"]
VALID_AUDIENCE_SEGMENTS = ["security_professionals", "ai_researchers", "technologists", "executives", "entrepreneurs", "general_tech", "other"]
VALID_TRENDING = ["low", "medium", "high"]
VALID_PROCESSING_METHODS = ["gemini", "fabric", "hybrid", "manual"]


class ValidationError(Exception):
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message)
        self.field = field


@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_content_schema(data: Any) -> ValidationResult:
    """Validate complete ContentSchema object."""
    errors: list[ValidationError] = []
    warnings: list[str] = []

    if not data or not isinstance(data, dict):
        errors.append(ValidationError("Data must be an object"))
        return ValidationResult(valid=False, errors=errors, warnings=warnings)

    required_fields = [
        "content", "people", "companies", "topics", "links",
        "sources", "newsletter_metadata", "analysis", "extraction_metadata",
    ]

    for fld in required_fields:
        if fld not in data:
            errors.append(ValidationError(f"Missing required field: {fld}", fld))

    if "content" in data:
        _validate_content(data["content"], errors, warnings)
    if "people" in data:
        _validate_people(data["people"], errors, warnings)
    if "companies" in data:
        _validate_companies(data["companies"], errors, warnings)
    if "topics" in data:
        _validate_topics(data["topics"], errors, warnings)
    if "links" in data:
        _validate_links(data["links"], errors, warnings)
    if "sources" in data:
        _validate_sources(data["sources"], errors, warnings)
    if "newsletter_metadata" in data:
        _validate_newsletter_metadata(data["newsletter_metadata"], errors, warnings)
    if "analysis" in data:
        _validate_analysis(data["analysis"], errors, warnings)
    if "extraction_metadata" in data:
        _validate_extraction_metadata(data["extraction_metadata"], errors, warnings)

    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


def _validate_content(content: Any, errors: list, warnings: list) -> None:
    if not content.get("id") or not UUID_REGEX.match(str(content.get("id", ""))):
        errors.append(ValidationError("Invalid or missing UUID", "content.id"))

    if not content.get("type") or content["type"] not in VALID_CONTENT_TYPES:
        errors.append(ValidationError(f"Invalid content type: {content.get('type')}", "content.type"))

    if not content.get("title") or not isinstance(content["title"], str) or not content["title"].strip():
        errors.append(ValidationError("Title is required and must be non-empty", "content.title"))

    if not content.get("summary"):
        errors.append(ValidationError("Summary object is required", "content.summary"))
    else:
        if not content["summary"].get("short"):
            warnings.append("Short summary is empty")
        if not content["summary"].get("medium"):
            warnings.append("Medium summary is empty")
        if not content["summary"].get("long"):
            warnings.append("Long summary is empty")

    if not content.get("metadata"):
        errors.append(ValidationError("Metadata object is required", "content.metadata"))
    else:
        if not content["metadata"].get("source_url"):
            errors.append(ValidationError("source_url is required", "content.metadata.source_url"))
        if not content["metadata"].get("accessed_date"):
            errors.append(ValidationError("accessed_date is required", "content.metadata.accessed_date"))


def _validate_people(people: Any, errors: list, warnings: list) -> None:
    if not isinstance(people, list):
        errors.append(ValidationError("people must be an array", "people"))
        return

    for i, person in enumerate(people):
        if not person.get("name"):
            errors.append(ValidationError(f"Person at index {i} missing name", f"people[{i}].name"))
        if not person.get("role") or person["role"] not in VALID_PERSON_ROLES:
            errors.append(ValidationError(f"Invalid role for person at index {i}", f"people[{i}].role"))
        if not person.get("importance") or person["importance"] not in VALID_IMPORTANCE:
            errors.append(ValidationError(f"Invalid importance for person at index {i}", f"people[{i}].importance"))
        if not person.get("context"):
            warnings.append(f"Person at index {i} missing context")


def _validate_companies(companies: Any, errors: list, warnings: list) -> None:
    if not isinstance(companies, list):
        errors.append(ValidationError("companies must be an array", "companies"))
        return

    for i, company in enumerate(companies):
        if not company.get("name"):
            errors.append(ValidationError(f"Company at index {i} missing name", f"companies[{i}].name"))
        if not company.get("mentioned_as") or company["mentioned_as"] not in VALID_MENTION_TYPES:
            errors.append(ValidationError(f"Invalid mentioned_as for company at index {i}", f"companies[{i}].mentioned_as"))
        if not company.get("sentiment") or company["sentiment"] not in VALID_SENTIMENTS:
            errors.append(ValidationError(f"Invalid sentiment for company at index {i}", f"companies[{i}].sentiment"))


def _validate_topics(topics: Any, errors: list, warnings: list) -> None:
    if not topics.get("primary_category"):
        errors.append(ValidationError("primary_category is required", "topics.primary_category"))
    if not isinstance(topics.get("secondary_categories"), list):
        errors.append(ValidationError("secondary_categories must be an array", "topics.secondary_categories"))
    if not isinstance(topics.get("tags"), list):
        errors.append(ValidationError("tags must be an array", "topics.tags"))
    elif len(topics["tags"]) < 4:
        warnings.append("tags array has fewer than 4 items (recommended: 4-10)")
    if not isinstance(topics.get("keywords"), list):
        errors.append(ValidationError("keywords must be an array", "topics.keywords"))
    elif len(topics["keywords"]) < 5:
        warnings.append("keywords array has fewer than 5 items (recommended: 5-15)")
    if not isinstance(topics.get("themes"), list):
        errors.append(ValidationError("themes must be an array", "topics.themes"))
    if not isinstance(topics.get("newsletter_sections"), list):
        errors.append(ValidationError("newsletter_sections must be an array", "topics.newsletter_sections"))


def _validate_links(links: Any, errors: list, warnings: list) -> None:
    if not isinstance(links, list):
        errors.append(ValidationError("links must be an array", "links"))
        return

    for i, link in enumerate(links):
        if not link.get("url"):
            errors.append(ValidationError(f"Link at index {i} missing url", f"links[{i}].url"))
        if not link.get("domain"):
            errors.append(ValidationError(f"Link at index {i} missing domain", f"links[{i}].domain"))
        if not link.get("link_type") or link["link_type"] not in VALID_LINK_TYPES:
            errors.append(ValidationError(f"Invalid link_type for link at index {i}", f"links[{i}].link_type"))
        if not link.get("position") or link["position"] not in VALID_POSITIONS:
            errors.append(ValidationError(f"Invalid position for link at index {i}", f"links[{i}].position"))


def _validate_sources(sources: Any, errors: list, warnings: list) -> None:
    if not isinstance(sources, list):
        errors.append(ValidationError("sources must be an array", "sources"))
        return

    for i, source in enumerate(sources):
        if not source.get("source_type") or source["source_type"] not in VALID_SOURCE_TYPES:
            errors.append(ValidationError(f"Invalid source_type for source at index {i}", f"sources[{i}].source_type"))


def _validate_newsletter_metadata(metadata: Any, errors: list, warnings: list) -> None:
    if not isinstance(metadata.get("include_in_newsletter"), bool):
        errors.append(ValidationError("include_in_newsletter must be a boolean", "newsletter_metadata.include_in_newsletter"))


def _validate_analysis(analysis: Any, errors: list, warnings: list) -> None:
    if not analysis.get("sentiment") or analysis["sentiment"] not in VALID_SENTIMENTS:
        errors.append(ValidationError("Invalid sentiment", "analysis.sentiment"))

    for score_name in ["importance_score", "novelty_score", "controversy_score"]:
        val = analysis.get(score_name)
        if not isinstance(val, (int, float)) or val < 1 or val > 10:
            errors.append(ValidationError(f"{score_name} must be 1-10", f"analysis.{score_name}"))

    if not analysis.get("trending_potential") or analysis["trending_potential"] not in VALID_TRENDING:
        errors.append(ValidationError("Invalid trending_potential", "analysis.trending_potential"))

    if not isinstance(analysis.get("relevance_to_audience"), list):
        errors.append(ValidationError("relevance_to_audience must be an array", "analysis.relevance_to_audience"))
    else:
        for i, segment in enumerate(analysis["relevance_to_audience"]):
            if segment not in VALID_AUDIENCE_SEGMENTS:
                errors.append(ValidationError(f"Invalid audience segment at index {i}: {segment}", f"analysis.relevance_to_audience[{i}]"))

    if not isinstance(analysis.get("key_insights"), list):
        errors.append(ValidationError("key_insights must be an array", "analysis.key_insights"))
    if not isinstance(analysis.get("related_content_ids"), list):
        errors.append(ValidationError("related_content_ids must be an array", "analysis.related_content_ids"))


def _validate_extraction_metadata(metadata: Any, errors: list, warnings: list) -> None:
    if not metadata.get("processed_date"):
        errors.append(ValidationError("processed_date is required", "extraction_metadata.processed_date"))
    if not metadata.get("processing_method") or metadata["processing_method"] not in VALID_PROCESSING_METHODS:
        errors.append(ValidationError("Invalid processing_method", "extraction_metadata.processing_method"))
    val = metadata.get("confidence_score")
    if not isinstance(val, (int, float)) or val < 0 or val > 1:
        errors.append(ValidationError("confidence_score must be 0-1", "extraction_metadata.confidence_score"))
    if not isinstance(metadata.get("warnings"), list):
        errors.append(ValidationError("warnings must be an array", "extraction_metadata.warnings"))
    if not metadata.get("version"):
        errors.append(ValidationError("version is required", "extraction_metadata.version"))


def assert_valid(data: Any) -> None:
    """Quick validation - raises on error."""
    result = validate_content_schema(data)
    if not result.valid:
        error_messages = "; ".join(str(e) for e in result.errors)
        raise ValidationError(f"Schema validation failed: {error_messages}")
