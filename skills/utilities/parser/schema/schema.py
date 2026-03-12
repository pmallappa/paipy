#!/usr/bin/env python3
"""
Content Schema v1.0.0 type definitions.
Matches schema/content-schema.json
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Optional

# Type aliases
ContentType = Literal["article", "video", "pdf", "newsletter", "podcast", "tweet_thread", "generic"]
AuthorPlatform = Literal["youtube", "substack", "blog", "news_site", "twitter", "arxiv", "medium", "linkedin", "other"]
PersonRole = Literal["author", "subject", "mentioned", "quoted", "expert", "interviewer", "interviewee"]
Importance = Literal["primary", "secondary", "minor"]
MentionType = Literal["subject", "source", "example", "competitor", "partner", "acquisition", "product", "other"]
Sentiment = Literal["positive", "neutral", "negative", "mixed"]
LinkType = Literal["reference", "source", "related", "tool", "research", "product", "social", "other"]
Position = Literal["beginning", "middle", "end", "sidebar", "footer"]
SourceType = Literal["research_paper", "news_article", "blog_post", "twitter_thread", "podcast", "video", "book", "other"]
AudienceSegment = Literal["security_professionals", "ai_researchers", "technologists", "executives", "entrepreneurs", "general_tech", "other"]
TrendingPotential = Literal["low", "medium", "high"]
ProcessingMethod = Literal["gemini", "fabric", "hybrid", "manual"]


@dataclass
class Summary:
    short: str  # 1-2 sentences
    medium: str  # paragraph
    long: str  # multiple paragraphs


@dataclass
class ContentBody:
    full_text: Optional[str]
    transcript: Optional[str]
    excerpts: list[str] = field(default_factory=list)


@dataclass
class SocialHandles:
    twitter: Optional[str] = None  # @handle
    linkedin: Optional[str] = None  # URL
    email: Optional[str] = None
    website: Optional[str] = None  # URL


@dataclass
class ContentMetadata:
    source_url: str
    canonical_url: Optional[str]
    published_date: Optional[str]  # ISO 8601
    accessed_date: str  # ISO 8601
    language: str
    word_count: Optional[int]
    read_time_minutes: Optional[int]
    author_platform: AuthorPlatform


@dataclass
class Content:
    id: str  # UUID v4
    type: ContentType
    title: str
    summary: Summary
    content: ContentBody
    metadata: ContentMetadata


@dataclass
class Person:
    name: str
    role: PersonRole
    title: Optional[str]
    company: Optional[str]
    social: SocialHandles
    context: str
    importance: Importance


@dataclass
class Company:
    name: str
    domain: Optional[str]
    industry: Optional[str]
    context: str
    mentioned_as: MentionType
    sentiment: Sentiment


@dataclass
class Topics:
    primary_category: str
    secondary_categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)
    newsletter_sections: list[str] = field(default_factory=list)


@dataclass
class Link:
    url: str
    domain: str
    title: Optional[str]
    description: Optional[str]
    link_type: LinkType
    context: str
    position: Position


@dataclass
class Source:
    publication: Optional[str]
    author: Optional[str]
    url: Optional[str]
    published_date: Optional[str]  # ISO 8601
    source_type: SourceType


@dataclass
class NewsletterMetadata:
    issue_number: Optional[int]
    section: Optional[str]
    position_in_section: Optional[int]
    editorial_note: Optional[str]
    include_in_newsletter: bool
    scheduled_date: Optional[str]  # ISO 8601


@dataclass
class Analysis:
    sentiment: Sentiment
    importance_score: int  # 1-10
    novelty_score: int  # 1-10
    controversy_score: int  # 1-10
    relevance_to_audience: list[AudienceSegment]
    key_insights: list[str]
    related_content_ids: list[str]  # UUIDs
    trending_potential: TrendingPotential


@dataclass
class ExtractionMetadata:
    processed_date: str  # ISO 8601
    processing_method: ProcessingMethod
    confidence_score: float  # 0-1
    warnings: list[str]
    version: str  # e.g., "1.0.0"


@dataclass
class ContentSchema:
    content: Content
    people: list[Person]
    companies: list[Company]
    topics: Topics
    links: list[Link]
    sources: list[Source]
    newsletter_metadata: NewsletterMetadata
    analysis: Analysis
    extraction_metadata: ExtractionMetadata


# UUID validation regex
UUID_REGEX = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.IGNORECASE)

# ISO 8601 date validation (basic)
ISO_8601_REGEX = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z?$')
