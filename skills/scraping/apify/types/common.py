#!/usr/bin/env python3
"""Common types shared across all Apify actors."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class PaginationOptions:
    """Standard pagination options for all scrapers."""

    max_results: Optional[int] = None
    """Maximum number of results to return."""
    offset: Optional[int] = None
    """Skip first N results."""


@dataclass
class DateRangeOptions:
    """Date range filter options."""

    from_date: Optional[str | datetime] = None
    """Start date (ISO string or datetime object)."""
    to_date: Optional[str | datetime] = None
    """End date (ISO string or datetime object)."""


@dataclass
class EngagementMetrics:
    """Engagement metrics common to social media posts."""

    likes_count: Optional[int] = None
    comments_count: Optional[int] = None
    shares_count: Optional[int] = None
    views_count: Optional[int] = None


@dataclass
class UserProfile:
    """Standard user/profile information."""

    id: Optional[str] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    bio: Optional[str] = None
    profile_picture_url: Optional[str] = None
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    verified: Optional[bool] = None


@dataclass
class Post(EngagementMetrics):
    """Standard post/content structure."""

    id: str = ""
    url: str = ""
    text: Optional[str] = None
    caption: Optional[str] = None
    timestamp: str = ""
    author: Optional[UserProfile] = None
    image_urls: Optional[list[str]] = None
    video_url: Optional[str] = None
    hashtags: Optional[list[str]] = None
    mentions: Optional[list[str]] = None


@dataclass
class Location:
    """Geo-location data."""

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None


@dataclass
class SocialMediaLinks:
    """Social media links."""

    facebook: Optional[str] = None
    twitter: Optional[str] = None
    instagram: Optional[str] = None
    linkedin: Optional[str] = None
    youtube: Optional[str] = None


@dataclass
class ContactInfo:
    """Contact information."""

    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    social_media: Optional[SocialMediaLinks] = None


@dataclass
class BusinessInfo:
    """Business/place information."""

    name: str = ""
    category: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    price_level: Optional[int] = None
    location: Optional[Location] = None
    contact: Optional[ContactInfo] = None
    opening_hours: Optional[list[str]] = None
    is_open: Optional[bool] = None


@dataclass
class ActorRunOptions:
    """Actor run options for controlling execution."""

    memory: Optional[int] = None
    """Memory allocation in MB (128, 256, 512, 1024, 2048, 4096, 8192)."""
    timeout: Optional[int] = None
    """Timeout in seconds."""
    build: Optional[str] = None
    """Build tag or number to use."""


@dataclass
class ActorError:
    """Error result when actor fails."""

    message: str = ""
    actor_id: str = ""
    run_id: Optional[str] = None
    status: Optional[str] = None
