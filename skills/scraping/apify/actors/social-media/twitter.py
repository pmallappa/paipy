#!/usr/bin/env python3
"""
Twitter/X Scraper

Top Actor:
- apidojo/twitter-scraper-lite (Unlimited, no rate limits, event-based pricing)

Extract Twitter/X profiles, tweets, followers, and search results.
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
class TwitterProfileInput:
    """Input for scraping a Twitter profile."""

    username: str
    """Twitter username (without @)."""
    include_tweets: bool = False
    """Include tweets in profile response."""
    max_tweets: int = 20
    """Maximum number of tweets to fetch."""


@dataclass
class TwitterProfile(UserProfile):
    """Twitter profile data."""

    username: str = ""
    display_name: str = ""
    bio: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    profile_image_url: Optional[str] = None
    banner_image_url: Optional[str] = None
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    tweets_count: Optional[int] = None
    verified: Optional[bool] = None
    created_at: Optional[str] = None
    latest_tweets: Optional[list[TwitterTweet]] = None


@dataclass
class TwitterTweetsInput(PaginationOptions):
    """Input for scraping tweets from a user."""

    username: str = ""
    """Twitter username (without @)."""
    max_tweets: int = 100
    """Maximum number of tweets to scrape."""
    include_replies: bool = True
    """Include replies."""
    include_retweets: bool = True
    """Include retweets."""


@dataclass
class TwitterSearchInput(PaginationOptions):
    """Input for searching Twitter."""

    query: str = ""
    """Search query."""
    max_tweets: int = 100
    """Maximum number of tweets to return."""
    search_type: str = "Latest"
    """Search type: 'Latest', 'Top', 'People', 'Photos', 'Videos'."""


@dataclass
class TwitterTweet(Post):
    """A single tweet."""

    id: str = ""
    url: str = ""
    text: str = ""
    author_username: str = ""
    author_display_name: str = ""
    timestamp: str = ""
    likes_count: int = 0
    retweets_count: int = 0
    replies_count: int = 0
    views_count: Optional[int] = None
    hashtags: Optional[list[str]] = None
    mentions: Optional[list[str]] = None
    image_urls: Optional[list[str]] = None
    video_url: Optional[str] = None
    is_retweet: Optional[bool] = None
    is_reply: Optional[bool] = None
    quoted_tweet: Optional[TwitterTweet] = None


# =============================================================================
# FUNCTIONS
# =============================================================================


def scrape_twitter_profile(
    input_data: TwitterProfileInput,
    options: Optional[ActorRunOptions] = None,
) -> TwitterProfile:
    """
    Scrape Twitter/X profile data.

    Example::

        profile = scrape_twitter_profile(TwitterProfileInput(
            username="exampleuser",
            include_tweets=True,
            max_tweets=20,
        ))
        print(f"{profile.display_name} (@{profile.username})")
        print(f"Followers: {profile.followers_count}")
        print(f"Latest tweets: {len(profile.latest_tweets or [])}")
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "apidojo/twitter-scraper-lite",
        {
            "mode": "profile",
            "username": input_data.username,
            "maxTweets": input_data.max_tweets if input_data.include_tweets else 0,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"Twitter profile scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(limit=100))

    if not items:
        raise RuntimeError(f"Profile not found: @{input_data.username}")

    profile_data = items[0]
    tweets = items[1:]

    return TwitterProfile(
        username=profile_data.get("username") or input_data.username,
        display_name=profile_data.get("name") or profile_data.get("displayName", ""),
        bio=profile_data.get("description") or profile_data.get("bio"),
        location=profile_data.get("location"),
        website=profile_data.get("url") or profile_data.get("website"),
        profile_image_url=profile_data.get("profileImageUrl"),
        banner_image_url=profile_data.get("bannerImageUrl"),
        followers_count=profile_data.get("followersCount") or profile_data.get("followers"),
        following_count=profile_data.get("followingCount") or profile_data.get("following"),
        tweets_count=profile_data.get("tweetsCount") or profile_data.get("tweets"),
        verified=profile_data.get("verified") or profile_data.get("isVerified"),
        created_at=profile_data.get("createdAt"),
        latest_tweets=[_map_to_twitter_tweet(t) for t in tweets],
    )


def scrape_twitter_tweets(
    input_data: TwitterTweetsInput,
    options: Optional[ActorRunOptions] = None,
) -> list[TwitterTweet]:
    """
    Scrape tweets from a Twitter/X user.

    Example::

        tweets = scrape_twitter_tweets(TwitterTweetsInput(
            username="exampleuser",
            max_tweets=100,
            include_replies=False,
        ))
        viral = [t for t in tweets if t.likes_count > 100 or t.retweets_count > 50]
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "apidojo/twitter-scraper-lite",
        {
            "mode": "tweets",
            "username": input_data.username,
            "maxTweets": input_data.max_tweets,
            "includeReplies": input_data.include_replies,
            "includeRetweets": input_data.include_retweets,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"Twitter tweets scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(
        limit=input_data.max_tweets or 1000,
        offset=input_data.offset or 0,
    ))

    return [_map_to_twitter_tweet(t) for t in items]


def search_twitter(
    input_data: TwitterSearchInput,
    options: Optional[ActorRunOptions] = None,
) -> list[TwitterTweet]:
    """
    Search Twitter/X for tweets.

    Example::

        tweets = search_twitter(TwitterSearchInput(
            query="AI security",
            max_tweets=50,
            search_type="Latest",
        ))
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "apidojo/twitter-scraper-lite",
        {
            "mode": "search",
            "query": input_data.query,
            "maxTweets": input_data.max_tweets,
            "searchType": input_data.search_type,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"Twitter search failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(
        limit=input_data.max_tweets or 1000,
        offset=input_data.offset or 0,
    ))

    return [_map_to_twitter_tweet(t) for t in items]


# =============================================================================
# HELPERS
# =============================================================================


def _map_to_twitter_tweet(tweet: dict[str, Any]) -> TwitterTweet:
    media = tweet.get("media") or []
    photo_urls = [m.get("url") for m in media if m.get("type") == "photo" and m.get("url")]
    video_entry = next((m for m in media if m.get("type") == "video"), None)

    return TwitterTweet(
        id=tweet.get("id") or tweet.get("tweetId", ""),
        url=tweet.get("url") or f"https://twitter.com/{tweet.get('authorUsername', '')}/status/{tweet.get('id', '')}",
        text=tweet.get("text") or tweet.get("fullText", ""),
        author_username=tweet.get("authorUsername") or tweet.get("username", ""),
        author_display_name=tweet.get("authorName") or tweet.get("displayName", ""),
        timestamp=tweet.get("createdAt") or tweet.get("timestamp", ""),
        likes_count=tweet.get("likesCount") or tweet.get("likes") or 0,
        retweets_count=tweet.get("retweetsCount") or tweet.get("retweets") or 0,
        replies_count=tweet.get("repliesCount") or tweet.get("replies") or 0,
        views_count=tweet.get("viewsCount") or tweet.get("views"),
        comments_count=tweet.get("repliesCount") or tweet.get("replies") or 0,
        hashtags=tweet.get("hashtags"),
        mentions=tweet.get("mentions"),
        image_urls=photo_urls or None,
        video_url=video_entry.get("url") if video_entry else None,
        is_retweet=tweet.get("isRetweet"),
        is_reply=tweet.get("isReplyTo") is not None,
        quoted_tweet=_map_to_twitter_tweet(tweet["quotedTweet"]) if tweet.get("quotedTweet") else None,
        caption=tweet.get("text") or tweet.get("fullText"),
    )
