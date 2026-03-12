#!/usr/bin/env python3
"""
YouTube Scraper

Top Actors:
- streamers/youtube-scraper (40,455 users, 4.40 rating, $0.005/video)
- apidojo/youtube-scraper (4,336 users, 3.88 rating, $0.50/1k videos)

Extract YouTube channels, videos, comments -- no API quotas/limits!
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ... import Apify, DatasetOptions
from ...types import ActorRunOptions, EngagementMetrics, PaginationOptions, Post, UserProfile


# =============================================================================
# TYPES
# =============================================================================


@dataclass
class YouTubeChannelInput:
    """Input for scraping a YouTube channel."""

    channel_url: str = ""
    """YouTube channel URL or ID."""
    max_videos: int = 50
    """Maximum number of videos to include."""


@dataclass
class YouTubeChannel(UserProfile):
    """YouTube channel data."""

    id: str = ""
    title: str = ""
    url: str = ""
    description: Optional[str] = None
    subscribers_count: Optional[int] = None
    videos_count: Optional[int] = None
    views_count: Optional[int] = None
    joined_date: Optional[str] = None
    country: Optional[str] = None
    thumbnail_url: Optional[str] = None
    banner_url: Optional[str] = None
    verified: Optional[bool] = None
    videos: Optional[list[YouTubeVideo]] = None


@dataclass
class YouTubeVideo(Post):
    """A single YouTube video."""

    id: str = ""
    url: str = ""
    title: str = ""
    description: Optional[str] = None
    channel_id: Optional[str] = None
    channel_title: Optional[str] = None
    channel_url: Optional[str] = None
    published_at: str = ""
    views_count: int = 0
    likes_count: Optional[int] = None
    comments_count: Optional[int] = None
    duration: Optional[str] = None
    thumbnail_url: Optional[str] = None
    tags: Optional[list[str]] = None
    category: Optional[str] = None


@dataclass
class YouTubeSearchInput(PaginationOptions):
    """Input for searching YouTube."""

    query: str = ""
    """Search query."""
    max_results: int = 50
    """Maximum number of videos."""
    upload_date: Optional[str] = None
    """Upload date filter: 'hour', 'today', 'week', 'month', 'year'."""
    duration: Optional[str] = None
    """Duration filter: 'short', 'medium', 'long'."""
    sort_by: str = "relevance"
    """Sort by: 'relevance', 'date', 'viewCount', 'rating'."""


@dataclass
class YouTubeCommentsInput(PaginationOptions):
    """Input for scraping YouTube comments."""

    video_url: str = ""
    """YouTube video URL or ID."""
    max_results: int = 100
    """Maximum number of comments."""


@dataclass
class YouTubeComment:
    """A single YouTube comment."""

    id: str = ""
    text: str = ""
    author_name: str = ""
    author_channel_url: Optional[str] = None
    likes_count: int = 0
    reply_count: Optional[int] = None
    published_at: str = ""


# =============================================================================
# FUNCTIONS
# =============================================================================


def scrape_youtube_channel(
    input_data: YouTubeChannelInput,
    options: Optional[ActorRunOptions] = None,
) -> YouTubeChannel:
    """
    Scrape YouTube channel data.

    Example::

        channel = scrape_youtube_channel(YouTubeChannelInput(
            channel_url="https://www.youtube.com/@exampleuser",
            max_videos=50,
        ))
        top_videos = sorted(
            [v for v in (channel.videos or []) if v.views_count > 10000],
            key=lambda v: v.views_count,
            reverse=True,
        )[:10]
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "streamers/youtube-channel-scraper",
        {
            "startUrls": [input_data.channel_url],
            "maxResults": input_data.max_videos,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"YouTube channel scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items()

    if not items:
        raise RuntimeError(f"Channel not found: {input_data.channel_url}")

    channel_data = items[0]
    videos = [_transform_video(v) for v in items[1:]]

    return YouTubeChannel(
        id=channel_data.get("channelId", ""),
        title=channel_data.get("title", ""),
        full_name=channel_data.get("title"),
        url=channel_data.get("url") or input_data.channel_url,
        description=channel_data.get("description"),
        bio=channel_data.get("description"),
        subscribers_count=channel_data.get("numberOfSubscribers"),
        followers_count=channel_data.get("numberOfSubscribers"),
        videos_count=channel_data.get("numberOfVideos"),
        views_count=channel_data.get("numberOfViews"),
        joined_date=channel_data.get("joinedDate"),
        country=channel_data.get("country"),
        thumbnail_url=channel_data.get("thumbnailUrl"),
        banner_url=channel_data.get("bannerUrl"),
        verified=channel_data.get("verified"),
        videos=videos,
    )


def search_youtube(
    input_data: YouTubeSearchInput,
    options: Optional[ActorRunOptions] = None,
) -> list[YouTubeVideo]:
    """
    Search YouTube videos.

    Example::

        videos = search_youtube(YouTubeSearchInput(
            query="artificial intelligence tutorial",
            max_results=100,
            upload_date="month",
            sort_by="viewCount",
        ))
        engaging = [v for v in videos if v.views_count > 50000 and (v.likes_count or 0) > 1000]
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "streamers/youtube-scraper",
        {
            "searchKeywords": input_data.query,
            "maxResults": input_data.max_results,
            "uploadDate": input_data.upload_date,
            "videoDuration": input_data.duration,
            "sortBy": input_data.sort_by,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"YouTube search failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(
        limit=input_data.max_results or 1000,
        offset=input_data.offset or 0,
    ))

    return [_transform_video(v) for v in items]


def scrape_youtube_comments(
    input_data: YouTubeCommentsInput,
    options: Optional[ActorRunOptions] = None,
) -> list[YouTubeComment]:
    """
    Scrape YouTube comments from a video.

    Example::

        comments = scrape_youtube_comments(YouTubeCommentsInput(
            video_url="https://www.youtube.com/watch?v=ABC123",
            max_results=500,
        ))
        popular = sorted(
            [c for c in comments if c.likes_count > 100],
            key=lambda c: c.likes_count,
            reverse=True,
        )
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "streamers/youtube-comments-scraper",
        {
            "startUrls": [input_data.video_url],
            "maxComments": input_data.max_results,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"YouTube comments scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(
        limit=input_data.max_results or 1000,
        offset=input_data.offset or 0,
    ))

    return [
        YouTubeComment(
            id=comment.get("id", ""),
            text=comment.get("text", ""),
            author_name=comment.get("authorText", ""),
            author_channel_url=comment.get("authorChannelUrl"),
            likes_count=comment.get("likesCount") or 0,
            reply_count=comment.get("replyCount"),
            published_at=comment.get("publishedTimeText", ""),
        )
        for comment in items
    ]


# =============================================================================
# HELPERS
# =============================================================================


def _transform_video(video: dict[str, Any]) -> YouTubeVideo:
    return YouTubeVideo(
        id=video.get("id", ""),
        url=video.get("url") or f"https://www.youtube.com/watch?v={video.get('id', '')}",
        title=video.get("title", ""),
        text=video.get("title"),
        description=video.get("description"),
        channel_id=video.get("channelId"),
        channel_title=video.get("channelName") or video.get("channelTitle"),
        channel_url=video.get("channelUrl"),
        published_at=video.get("date") or video.get("publishedAt", ""),
        timestamp=video.get("date") or video.get("publishedAt", ""),
        views_count=video.get("views") or video.get("viewsCount") or 0,
        likes_count=video.get("likes") or video.get("likesCount"),
        comments_count=video.get("numberOfComments") or video.get("commentsCount"),
        duration=video.get("duration"),
        thumbnail_url=video.get("thumbnail") or video.get("thumbnailUrl"),
        tags=video.get("tags"),
        category=video.get("category"),
    )
