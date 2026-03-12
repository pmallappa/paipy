#!/usr/bin/env python3
"""
Facebook Scraper

Top Actors:
- apify/facebook-posts-scraper (35,226 users, 4.56 rating)
- apify/facebook-groups-scraper (16,182 users, 4.19 rating)
- apify/facebook-comments-scraper (17,173 users, 4.46 rating)

Extract Facebook posts, groups, comments, pages without login.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ... import Apify, DatasetOptions
from ...types import ActorRunOptions, PaginationOptions, Post, UserProfile


# =============================================================================
# TYPES
# =============================================================================


@dataclass
class FacebookPostsInput(PaginationOptions):
    """Input for scraping Facebook posts."""

    page_urls: Optional[list[str]] = None
    """Facebook page or profile URLs."""
    max_posts_per_page: int = 50
    """Maximum number of posts per page."""
    from_date: Optional[str] = None
    """Date range filter start."""
    to_date: Optional[str] = None
    """Date range filter end."""


@dataclass
class FacebookPost(Post):
    """A single Facebook post."""

    id: str = ""
    url: str = ""
    text: Optional[str] = None
    post_date: str = ""
    page_url: Optional[str] = None
    page_name: Optional[str] = None
    likes_count: Optional[int] = None
    comments_count: Optional[int] = None
    shares_count: Optional[int] = None
    image_urls: Optional[list[str]] = None
    video_url: Optional[str] = None
    type: Optional[str] = None  # 'post', 'video', 'image', 'link'


@dataclass
class FacebookGroupsInput(PaginationOptions):
    """Input for scraping Facebook groups."""

    group_urls: Optional[list[str]] = None
    """Facebook group URLs."""
    max_posts_per_group: int = 50
    """Maximum posts per group."""
    include_comments: bool = False
    """Include comments."""


@dataclass
class FacebookComment:
    """A single Facebook comment."""

    id: str = ""
    text: str = ""
    date: str = ""
    likes_count: Optional[int] = None
    author_name: Optional[str] = None
    author_url: Optional[str] = None


@dataclass
class FacebookGroupPost(FacebookPost):
    """A Facebook group post."""

    group_name: Optional[str] = None
    group_url: Optional[str] = None
    author_name: Optional[str] = None
    author_url: Optional[str] = None
    comments: Optional[list[FacebookComment]] = None


@dataclass
class FacebookCommentsInput(PaginationOptions):
    """Input for scraping Facebook comments."""

    post_urls: Optional[list[str]] = None
    """Facebook post URLs."""
    max_comments_per_post: int = 100
    """Maximum comments per post."""


# =============================================================================
# FUNCTIONS
# =============================================================================


def scrape_facebook_posts(
    input_data: FacebookPostsInput,
    options: Optional[ActorRunOptions] = None,
) -> list[FacebookPost]:
    """
    Scrape Facebook posts from pages or profiles.

    Example::

        posts = scrape_facebook_posts(FacebookPostsInput(
            page_urls=["https://www.facebook.com/SomePage"],
            max_posts_per_page=100,
        ))
        viral = [p for p in posts if (p.likes_count or 0) > 1000 or (p.shares_count or 0) > 100]
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "apify/facebook-posts-scraper",
        {
            "startUrls": [{"url": u} for u in (input_data.page_urls or [])],
            "maxPosts": input_data.max_posts_per_page,
            "fromDate": input_data.from_date,
            "toDate": input_data.to_date,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"Facebook posts scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(
        limit=input_data.max_results or 1000,
        offset=input_data.offset or 0,
    ))

    return [
        FacebookPost(
            id=post.get("id", ""),
            url=post.get("url", ""),
            text=post.get("text"),
            caption=post.get("text"),
            post_date=post.get("time", ""),
            timestamp=post.get("time", ""),
            page_url=post.get("pageUrl"),
            page_name=post.get("pageName"),
            likes_count=post.get("likes"),
            comments_count=post.get("comments"),
            shares_count=post.get("shares"),
            image_urls=post.get("images"),
            video_url=post.get("video"),
            type=post.get("postType"),
        )
        for post in items
    ]


def scrape_facebook_groups(
    input_data: FacebookGroupsInput,
    options: Optional[ActorRunOptions] = None,
) -> list[FacebookGroupPost]:
    """
    Scrape Facebook groups posts.

    Example::

        posts = scrape_facebook_groups(FacebookGroupsInput(
            group_urls=["https://www.facebook.com/groups/somegroupid"],
            max_posts_per_group=50,
            include_comments=True,
        ))
        active = [p for p in posts if (p.comments_count or 0) > 10]
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "apify/facebook-groups-scraper",
        {
            "startUrls": [{"url": u} for u in (input_data.group_urls or [])],
            "maxPosts": input_data.max_posts_per_group,
            "includeComments": input_data.include_comments,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"Facebook groups scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(
        limit=input_data.max_results or 1000,
        offset=input_data.offset or 0,
    ))

    results: list[FacebookGroupPost] = []
    for post in items:
        raw_comments = post.get("comments")
        parsed_comments = None
        if isinstance(raw_comments, list):
            parsed_comments = [
                FacebookComment(
                    id=c.get("id", ""),
                    text=c.get("text", ""),
                    date=c.get("time", ""),
                    likes_count=c.get("likes"),
                    author_name=c.get("authorName"),
                    author_url=c.get("authorUrl"),
                )
                for c in raw_comments
            ]

        results.append(
            FacebookGroupPost(
                id=post.get("id", ""),
                url=post.get("url", ""),
                text=post.get("text"),
                caption=post.get("text"),
                post_date=post.get("time", ""),
                timestamp=post.get("time", ""),
                group_name=post.get("groupName"),
                group_url=post.get("groupUrl"),
                author_name=post.get("authorName"),
                author_url=post.get("authorUrl"),
                likes_count=post.get("likes"),
                comments_count=post.get("comments") if isinstance(post.get("comments"), int) else None,
                shares_count=post.get("shares"),
                image_urls=post.get("images"),
                video_url=post.get("video"),
                comments=parsed_comments,
            )
        )

    return results


def scrape_facebook_comments(
    input_data: FacebookCommentsInput,
    options: Optional[ActorRunOptions] = None,
) -> list[FacebookComment]:
    """
    Scrape Facebook comments from posts.

    Example::

        comments = scrape_facebook_comments(FacebookCommentsInput(
            post_urls=["https://www.facebook.com/post/123"],
            max_comments_per_post=200,
        ))
        top_comments = sorted(
            [c for c in comments if (c.likes_count or 0) > 50],
            key=lambda c: c.likes_count or 0,
            reverse=True,
        )
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "apify/facebook-comments-scraper",
        {
            "startUrls": [{"url": u} for u in (input_data.post_urls or [])],
            "maxComments": input_data.max_comments_per_post,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"Facebook comments scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(
        limit=input_data.max_results or 1000,
        offset=input_data.offset or 0,
    ))

    return [
        FacebookComment(
            id=comment.get("id", ""),
            text=comment.get("text", ""),
            date=comment.get("time", ""),
            likes_count=comment.get("likes"),
            author_name=comment.get("authorName"),
            author_url=comment.get("authorUrl"),
        )
        for comment in items
    ]
