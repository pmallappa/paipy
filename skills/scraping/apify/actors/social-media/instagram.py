#!/usr/bin/env python3
"""
Instagram Scraper

Apify Actor: apify/instagram-scraper (145,279 users, 4.60 rating)
Pricing: $0.50-$2.70 per 1000 results (tiered)

Extract Instagram profiles, posts, hashtags, comments without login.
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
class InstagramProfileInput:
    """Input for scraping an Instagram profile."""

    username: str = ""
    """Instagram username (without @)."""
    max_posts: int = 12
    """Maximum number of latest posts to include."""
    include_metadata: bool = True
    """Include profile metadata."""


@dataclass
class InstagramPostLocation:
    """Location info for an Instagram post."""

    name: Optional[str] = None
    slug: Optional[str] = None


@dataclass
class InstagramPost(Post):
    """A single Instagram post."""

    id: str = ""
    short_code: str = ""
    url: str = ""
    caption: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    likes_count: int = 0
    comments_count: int = 0
    timestamp: str = ""
    type: str = "Image"  # 'Image', 'Video', 'Sidecar'
    location: Optional[InstagramPostLocation] = None
    hashtags: Optional[list[str]] = None
    mentions: Optional[list[str]] = None
    is_sponsored: Optional[bool] = None


@dataclass
class InstagramProfile(UserProfile):
    """Instagram profile data."""

    username: str = ""
    full_name: str = ""
    biography: Optional[str] = None
    external_url: Optional[str] = None
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0
    is_private: Optional[bool] = None
    is_verified: Optional[bool] = None
    latest_posts: Optional[list[InstagramPost]] = None


@dataclass
class InstagramPostsInput(PaginationOptions):
    """Input for scraping Instagram posts."""

    username: str = ""
    """Instagram username (without @)."""
    max_results: int = 50
    """Maximum number of posts to scrape."""


@dataclass
class InstagramHashtagInput(PaginationOptions):
    """Input for scraping Instagram by hashtag."""

    hashtag: str = ""
    """Hashtag (without #)."""
    max_results: int = 100
    """Maximum number of posts to scrape."""


@dataclass
class InstagramCommentInput(PaginationOptions):
    """Input for scraping Instagram comments."""

    post_url: str = ""
    """Instagram post URL."""
    max_results: int = 100
    """Maximum number of comments to scrape."""


@dataclass
class InstagramComment:
    """A single Instagram comment."""

    id: str = ""
    text: str = ""
    timestamp: str = ""
    likes_count: int = 0
    owner_username: str = ""
    owner_profile_pic_url: Optional[str] = None


# =============================================================================
# FUNCTIONS
# =============================================================================


def scrape_instagram_profile(
    input_data: InstagramProfileInput,
    options: Optional[ActorRunOptions] = None,
) -> InstagramProfile:
    """
    Scrape Instagram profile data.

    Example::

        profile = scrape_instagram_profile(InstagramProfileInput(
            username="exampleuser",
            max_posts=12,
        ))
        viral_posts = [p for p in (profile.latest_posts or []) if p.likes_count > 10000]
        print(f"Found {len(viral_posts)} viral posts")
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "apify/instagram-profile-scraper",
        {
            "usernames": [input_data.username],
            "resultsLimit": input_data.max_posts,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"Instagram profile scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(limit=1))

    if not items:
        raise RuntimeError(f"Profile not found: @{input_data.username}")

    profile = items[0]

    latest_posts = None
    if profile.get("latestPosts"):
        latest_posts = [_transform_post(p) for p in profile["latestPosts"]]

    return InstagramProfile(
        id=profile.get("id"),
        username=profile.get("username", ""),
        full_name=profile.get("fullName") or profile.get("username", ""),
        biography=profile.get("biography"),
        external_url=profile.get("externalUrl"),
        profile_picture_url=profile.get("profilePicUrl"),
        followers_count=profile.get("followersCount") or 0,
        following_count=profile.get("followsCount") or 0,
        posts_count=profile.get("postsCount") or 0,
        is_private=profile.get("private"),
        is_verified=profile.get("verified"),
        verified=profile.get("verified"),
        latest_posts=latest_posts,
    )


def scrape_instagram_posts(
    input_data: InstagramPostsInput,
    options: Optional[ActorRunOptions] = None,
) -> list[InstagramPost]:
    """
    Scrape Instagram posts from a profile.

    Example::

        posts = scrape_instagram_posts(InstagramPostsInput(
            username="exampleuser",
            max_results=50,
        ))
        import time
        thirty_days_ago = time.time() * 1000 - (30 * 24 * 60 * 60 * 1000)
        recent_popular = [
            p for p in posts
            if p.likes_count > 1000
        ]
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "apify/instagram-post-scraper",
        {
            "usernames": [input_data.username],
            "resultsLimit": input_data.max_results,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"Instagram posts scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(
        limit=input_data.max_results or 1000,
        offset=input_data.offset or 0,
    ))

    return [_transform_post(p) for p in items]


def scrape_instagram_hashtag(
    input_data: InstagramHashtagInput,
    options: Optional[ActorRunOptions] = None,
) -> list[InstagramPost]:
    """
    Scrape Instagram posts by hashtag.

    Example::

        posts = scrape_instagram_hashtag(InstagramHashtagInput(
            hashtag="ai",
            max_results=100,
        ))
        popular_videos = [
            p for p in posts
            if p.type == "Video" and p.likes_count > 5000
        ][:10]
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "apify/instagram-hashtag-scraper",
        {
            "hashtags": [input_data.hashtag],
            "resultsLimit": input_data.max_results,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"Instagram hashtag scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(
        limit=input_data.max_results or 1000,
        offset=input_data.offset or 0,
    ))

    return [_transform_post(p) for p in items]


def scrape_instagram_comments(
    input_data: InstagramCommentInput,
    options: Optional[ActorRunOptions] = None,
) -> list[InstagramComment]:
    """
    Scrape Instagram comments from a post.

    Example::

        comments = scrape_instagram_comments(InstagramCommentInput(
            post_url="https://www.instagram.com/p/ABC123/",
            max_results=100,
        ))
        popular = sorted(
            [c for c in comments if c.likes_count > 10],
            key=lambda c: c.likes_count,
            reverse=True,
        )[:10]
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "apify/instagram-comment-scraper",
        {
            "directUrls": [input_data.post_url],
            "resultsLimit": input_data.max_results,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"Instagram comments scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(
        limit=input_data.max_results or 1000,
        offset=input_data.offset or 0,
    ))

    return [
        InstagramComment(
            id=item.get("id", ""),
            text=item.get("text", ""),
            timestamp=item.get("timestamp", ""),
            likes_count=item.get("likesCount") or 0,
            owner_username=item.get("ownerUsername", ""),
            owner_profile_pic_url=item.get("ownerProfilePicUrl"),
        )
        for item in items
    ]


# =============================================================================
# HELPERS
# =============================================================================


def _transform_post(post: dict[str, Any]) -> InstagramPost:
    """Transform raw Instagram post data to our standard format."""
    location = None
    if post.get("locationName"):
        location = InstagramPostLocation(
            name=post.get("locationName"),
            slug=post.get("locationSlug"),
        )

    author = None
    if post.get("ownerUsername"):
        author = UserProfile(
            username=post.get("ownerUsername"),
            full_name=post.get("ownerFullName"),
        )

    return InstagramPost(
        id=post.get("id", ""),
        short_code=post.get("shortCode", ""),
        url=post.get("url") or f"https://www.instagram.com/p/{post.get('shortCode', '')}/",
        caption=post.get("caption"),
        image_url=post.get("displayUrl") or post.get("imageUrl"),
        video_url=post.get("videoUrl"),
        likes_count=post.get("likesCount") or 0,
        comments_count=post.get("commentsCount") or 0,
        views_count=post.get("videoViewCount"),
        timestamp=post.get("timestamp", ""),
        type=post.get("type") or ("Video" if post.get("videoUrl") else "Image"),
        location=location,
        hashtags=post.get("hashtags"),
        mentions=post.get("mentions"),
        is_sponsored=post.get("isSponsored"),
        text=post.get("caption"),
        author=author,
    )
