#!/usr/bin/env python3
"""
LinkedIn Scraper

Top Actors:
- dev_fusion/Linkedin-Profile-Scraper (26,635 users, 4.10 rating, $10/1k results)
- curious_coder/linkedin-jobs-scraper (9,430 users, 4.98 rating, $1/1k results)
- supreme_coder/linkedin-post (3,663 users, 4.16 rating, $0.001/post)

Extract LinkedIn profiles, jobs, posts, company data without cookies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ... import Apify, DatasetOptions
from ...types import ActorRunOptions, ContactInfo, Location, PaginationOptions, Post, UserProfile


# =============================================================================
# TYPES
# =============================================================================


@dataclass
class LinkedInProfileInput:
    """Input for scraping a LinkedIn profile."""

    profile_url: str = ""
    """LinkedIn profile URL."""
    include_email: bool = False
    """Include email extraction (requires website visit)."""


@dataclass
class LinkedInExperience:
    """A single work experience entry."""

    title: str = ""
    company: str = ""
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[str] = None


@dataclass
class LinkedInEducation:
    """A single education entry."""

    school: str = ""
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None


@dataclass
class LinkedInProfile(UserProfile):
    """LinkedIn profile data."""

    full_name: str = ""
    headline: Optional[str] = None
    location: Optional[str] = None
    about: Optional[str] = None
    profile_url: str = ""
    company: Optional[str] = None
    position: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    connections_count: Optional[int] = None
    skills: Optional[list[str]] = None
    experience: Optional[list[LinkedInExperience]] = None
    education: Optional[list[LinkedInEducation]] = None
    languages: Optional[list[str]] = None


@dataclass
class LinkedInJobsInput(PaginationOptions):
    """Input for searching LinkedIn jobs."""

    keywords: str = ""
    """Job search keywords."""
    location: Optional[str] = None
    """Location (e.g., 'San Francisco, CA')."""
    max_results: int = 50
    """Maximum number of jobs to scrape."""
    date_posted: Optional[str] = None
    """Date posted filter ('past-24h', 'past-week', 'past-month', 'any')."""
    experience_level: Optional[list[str]] = None
    """Experience level filter."""
    remote: Optional[bool] = None
    """Remote filter."""


@dataclass
class LinkedInJob:
    """A single LinkedIn job listing."""

    id: str = ""
    title: str = ""
    company: str = ""
    company_url: Optional[str] = None
    company_logo: Optional[str] = None
    location: str = ""
    description: str = ""
    posted_date: str = ""
    applicants: Optional[str] = None
    job_url: str = ""
    seniority: Optional[str] = None
    employment_type: Optional[str] = None
    job_functions: Optional[list[str]] = None
    industries: Optional[list[str]] = None
    salary: Optional[str] = None


@dataclass
class LinkedInPostsInput(PaginationOptions):
    """Input for scraping LinkedIn posts."""

    profile_url: str = ""
    """LinkedIn profile or company URL."""
    max_results: int = 50
    """Maximum number of posts to scrape."""


@dataclass
class LinkedInPost(Post):
    """A single LinkedIn post."""

    id: str = ""
    url: str = ""
    text: str = ""
    author_name: Optional[str] = None
    author_url: Optional[str] = None
    author_headline: Optional[str] = None
    likes_count: int = 0
    comments_count: int = 0
    shares_count: Optional[int] = None
    timestamp: str = ""
    image_urls: Optional[list[str]] = None
    video_url: Optional[str] = None


# =============================================================================
# FUNCTIONS
# =============================================================================


def scrape_linkedin_profile(
    input_data: LinkedInProfileInput,
    options: Optional[ActorRunOptions] = None,
) -> LinkedInProfile:
    """
    Scrape LinkedIn profile data including email.

    Example::

        profile = scrape_linkedin_profile(LinkedInProfileInput(
            profile_url="https://www.linkedin.com/in/exampleuser",
            include_email=True,
        ))
        print(f"{profile.full_name} - {profile.headline}")
        print(f"Email: {profile.email}")
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "dev_fusion/Linkedin-Profile-Scraper",
        {
            "urls": [input_data.profile_url],
            "includeEmail": input_data.include_email,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"LinkedIn profile scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(limit=1))

    if not items:
        raise RuntimeError(f"Profile not found: {input_data.profile_url}")

    profile = items[0]

    return LinkedInProfile(
        full_name=profile.get("fullName") or profile.get("name", ""),
        headline=profile.get("headline"),
        bio=profile.get("about"),
        about=profile.get("about"),
        location=profile.get("location"),
        profile_url=input_data.profile_url,
        company=profile.get("company"),
        position=profile.get("position") or profile.get("headline"),
        email=profile.get("email"),
        phone=profile.get("phone"),
        website=profile.get("website"),
        connections_count=profile.get("connections"),
        followers_count=profile.get("followers"),
        skills=profile.get("skills"),
        experience=profile.get("experience"),
        education=profile.get("education"),
        languages=profile.get("languages"),
    )


def search_linkedin_jobs(
    input_data: LinkedInJobsInput,
    options: Optional[ActorRunOptions] = None,
) -> list[LinkedInJob]:
    """
    Search LinkedIn jobs.

    Example::

        jobs = search_linkedin_jobs(LinkedInJobsInput(
            keywords="artificial intelligence engineer",
            location="United States",
            remote=True,
            max_results=100,
        ))
        competitive = [
            j for j in jobs
            if j.seniority and "Senior" in j.seniority
            and int(j.applicants or "0") > 100
        ]
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "curious_coder/linkedin-jobs-scraper",
        {
            "keyword": input_data.keywords,
            "location": input_data.location,
            "maxItems": input_data.max_results,
            "datePosted": input_data.date_posted,
            "experienceLevel": input_data.experience_level,
            "remote": input_data.remote,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"LinkedIn jobs scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(
        limit=input_data.max_results or 1000,
        offset=input_data.offset or 0,
    ))

    return [
        LinkedInJob(
            id=job.get("jobId") or job.get("id", ""),
            title=job.get("title", ""),
            company=job.get("company", ""),
            company_url=job.get("companyUrl"),
            company_logo=job.get("companyLogo"),
            location=job.get("location", ""),
            description=job.get("description", ""),
            posted_date=job.get("postedDate") or job.get("postedAt", ""),
            applicants=job.get("applicants"),
            job_url=job.get("jobUrl") or job.get("url", ""),
            seniority=job.get("seniority"),
            employment_type=job.get("employmentType"),
            job_functions=job.get("jobFunctions"),
            industries=job.get("industries"),
            salary=job.get("salary"),
        )
        for job in items
    ]


def scrape_linkedin_posts(
    input_data: LinkedInPostsInput,
    options: Optional[ActorRunOptions] = None,
) -> list[LinkedInPost]:
    """
    Scrape LinkedIn posts from a profile or company.

    Example::

        posts = scrape_linkedin_posts(LinkedInPostsInput(
            profile_url="https://www.linkedin.com/in/exampleuser",
            max_results=50,
        ))
        viral = [p for p in posts if p.likes_count > 100 or p.comments_count > 20]
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "supreme_coder/linkedin-post",
        {
            "urls": [input_data.profile_url],
            "maxPosts": input_data.max_results,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"LinkedIn posts scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(
        limit=input_data.max_results or 1000,
        offset=input_data.offset or 0,
    ))

    return [
        LinkedInPost(
            id=post.get("id") or post.get("postId", ""),
            url=post.get("url") or post.get("postUrl", ""),
            text=post.get("text") or post.get("content", ""),
            author_name=post.get("authorName"),
            author_url=post.get("authorUrl"),
            author_headline=post.get("authorHeadline"),
            likes_count=post.get("likesCount") or post.get("likes") or 0,
            comments_count=post.get("commentsCount") or post.get("comments") or 0,
            shares_count=post.get("sharesCount") or post.get("shares"),
            views_count=post.get("viewsCount"),
            timestamp=post.get("timestamp") or post.get("postedAt", ""),
            image_urls=post.get("images"),
            video_url=post.get("videoUrl"),
            caption=post.get("text"),
        )
        for post in items
    ]
