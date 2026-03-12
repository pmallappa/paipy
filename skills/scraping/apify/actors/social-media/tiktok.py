#!/usr/bin/env python3
"""
TikTok Scraper

Top Actors:
- clockworks/tiktok-scraper (90,141 users, 4.61 rating)
- scraptik/tiktok-api (1,329 users, 4.68 rating, $0.002/request -- LOWEST COST)

Extract TikTok profiles, videos, hashtags, comments without login.
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
class TikTokProfileInput:
    """Input for scraping a TikTok profile."""

    username: str = ""
    """TikTok username (without @)."""
    max_videos: int = 30
    """Maximum number of videos to include."""


@dataclass
class TikTokProfile(UserProfile):
    """TikTok profile data."""

    id: str = ""
    username: str = ""
    nickname: Optional[str] = None
    signature: Optional[str] = None
    verified: Optional[bool] = None
    followers_count: int = 0
    following_count: int = 0
    heart_count: Optional[int] = None
    video_count: Optional[int] = None
    videos: Optional[list[TikTokVideo]] = None


@dataclass
class TikTokVideo(Post):
    """A single TikTok video."""

    id: str = ""
    url: str = ""
    text: Optional[str] = None
    desc: Optional[str] = None
    create_time: str = ""
    video_url: Optional[str] = None
    cover_url: Optional[str] = None
    play_count: Optional[int] = None
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    download_count: Optional[int] = None
    music_title: Optional[str] = None
    music_author: Optional[str] = None
    author_username: Optional[str] = None
    author_nickname: Optional[str] = None
    hashtags: Optional[list[str]] = None
    mentions: Optional[list[str]] = None
    is_ad: Optional[bool] = None


@dataclass
class TikTokHashtagInput(PaginationOptions):
    """Input for scraping TikTok by hashtag."""

    hashtag: str = ""
    """Hashtag (without #)."""
    max_results: int = 100
    """Maximum number of videos to scrape."""


@dataclass
class TikTokCommentsInput(PaginationOptions):
    """Input for scraping TikTok comments."""

    video_url: str = ""
    """TikTok video URL."""
    max_results: int = 100
    """Maximum number of comments to scrape."""


@dataclass
class TikTokComment:
    """A single TikTok comment."""

    id: str = ""
    text: str = ""
    create_time: str = ""
    like_count: int = 0
    reply_count: Optional[int] = None
    username: str = ""
    user_nickname: Optional[str] = None


# =============================================================================
# FUNCTIONS
# =============================================================================


def scrape_tiktok_profile(
    input_data: TikTokProfileInput,
    options: Optional[ActorRunOptions] = None,
) -> TikTokProfile:
    """
    Scrape TikTok profile data.

    Example::

        profile = scrape_tiktok_profile(TikTokProfileInput(
            username="exampleuser",
            max_videos=30,
        ))
        viral = [v for v in (profile.videos or []) if (v.play_count or 0) > 1_000_000]
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "clockworks/tiktok-profile-scraper",
        {
            "profiles": [f"https://www.tiktok.com/@{input_data.username}"],
            "resultsPerPage": input_data.max_videos,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"TikTok profile scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(limit=1))

    if not items:
        raise RuntimeError(f"Profile not found: @{input_data.username}")

    profile = items[0]
    author_meta = profile.get("authorMeta") or {}

    videos = None
    if profile.get("posts"):
        videos = [_transform_video(v) for v in profile["posts"]]

    return TikTokProfile(
        id=author_meta.get("id", ""),
        username=input_data.username,
        nickname=author_meta.get("name"),
        full_name=author_meta.get("name"),
        bio=author_meta.get("signature"),
        signature=author_meta.get("signature"),
        verified=author_meta.get("verified"),
        followers_count=author_meta.get("fans") or 0,
        following_count=author_meta.get("following") or 0,
        heart_count=author_meta.get("heart"),
        video_count=author_meta.get("video"),
        videos=videos,
    )


def scrape_tiktok_hashtag(
    input_data: TikTokHashtagInput,
    options: Optional[ActorRunOptions] = None,
) -> list[TikTokVideo]:
    """
    Scrape TikTok videos by hashtag.

    Example::

        videos = scrape_tiktok_hashtag(TikTokHashtagInput(
            hashtag="ai",
            max_results=100,
        ))
        top_videos = sorted(
            [v for v in videos if v.like_count > 10000],
            key=lambda v: v.like_count,
            reverse=True,
        )[:10]
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "clockworks/tiktok-hashtag-scraper",
        {
            "hashtags": [input_data.hashtag],
            "resultsPerPage": input_data.max_results,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"TikTok hashtag scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(
        limit=input_data.max_results or 1000,
        offset=input_data.offset or 0,
    ))

    return [_transform_video(v) for v in items]


def scrape_tiktok_comments(
    input_data: TikTokCommentsInput,
    options: Optional[ActorRunOptions] = None,
) -> list[TikTokComment]:
    """
    Scrape TikTok comments from a video.

    Example::

        comments = scrape_tiktok_comments(TikTokCommentsInput(
            video_url="https://www.tiktok.com/@user/video/123",
            max_results=200,
        ))
        popular = [c for c in comments if c.like_count > 50]
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "clockworks/tiktok-comments-scraper",
        {
            "postURLs": [input_data.video_url],
            "maxComments": input_data.max_results,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"TikTok comments scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(
        limit=input_data.max_results or 1000,
        offset=input_data.offset or 0,
    ))

    return [
        TikTokComment(
            id=comment.get("cid", ""),
            text=comment.get("text", ""),
            create_time=comment.get("createTime", ""),
            like_count=comment.get("diggCount") or 0,
            reply_count=comment.get("replyCommentTotal"),
            username=(comment.get("user") or {}).get("uniqueId", ""),
            user_nickname=(comment.get("user") or {}).get("nickname"),
        )
        for comment in items
    ]


# =============================================================================
# HELPERS
# =============================================================================


def _transform_video(video: dict[str, Any]) -> TikTokVideo:
    author_meta = video.get("authorMeta") or {}
    covers = video.get("covers") or {}
    music_meta = video.get("musicMeta") or {}
    raw_hashtags = video.get("hashtags") or []

    return TikTokVideo(
        id=video.get("id", ""),
        url=video.get("webVideoUrl") or f"https://www.tiktok.com/@{author_meta.get('name', '')}/video/{video.get('id', '')}",
        text=video.get("text"),
        desc=video.get("text"),
        caption=video.get("text"),
        create_time=video.get("createTime", ""),
        timestamp=video.get("createTime", ""),
        video_url=video.get("videoUrl"),
        cover_url=covers.get("default"),
        play_count=video.get("playCount"),
        views_count=video.get("playCount"),
        like_count=video.get("diggCount") or 0,
        likes_count=video.get("diggCount") or 0,
        comment_count=video.get("commentCount") or 0,
        comments_count=video.get("commentCount") or 0,
        share_count=video.get("shareCount") or 0,
        shares_count=video.get("shareCount") or 0,
        download_count=video.get("downloadCount"),
        music_title=music_meta.get("musicName"),
        music_author=music_meta.get("musicAuthor"),
        author_username=author_meta.get("name"),
        author_nickname=author_meta.get("nickName"),
        hashtags=[h.get("name", "") for h in raw_hashtags] if isinstance(raw_hashtags, list) and raw_hashtags and isinstance(raw_hashtags[0], dict) else raw_hashtags,
        mentions=video.get("mentions"),
        is_ad=video.get("isAd"),
    )
