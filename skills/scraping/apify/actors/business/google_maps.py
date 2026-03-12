#!/usr/bin/env python3
"""
Google Maps Scraper

Apify Actor: compass/crawler-google-places (198,093 users, 4.76 rating)
Pricing: $0.001-$0.007 per event (Actor start + per place + optional add-ons)

HIGHEST VALUE ACTOR -- 198k users!
Extract Google Maps business data, reviews, contacts, images -- perfect for lead generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ... import Apify, DatasetOptions
from ...types import ActorRunOptions, BusinessInfo, ContactInfo, Location, PaginationOptions


# =============================================================================
# TYPES
# =============================================================================


@dataclass
class GoogleMapsSearchInput(PaginationOptions):
    """Input for searching Google Maps."""

    query: str = ""
    """Search query (e.g., 'restaurants in San Francisco')."""
    max_results: int = 50
    """Maximum number of places to scrape."""
    include_reviews: bool = False
    """Include reviews for each place."""
    max_reviews_per_place: int = 0
    """Maximum reviews per place."""
    include_images: bool = False
    """Include images."""
    scrape_contact_info: bool = False
    """Scrape contact information from websites."""
    language: str = "en"
    """Language code (en, es, fr, de, etc.)."""
    country: Optional[str] = None
    """Country code for search region."""


@dataclass
class GoogleMapsPlaceInput:
    """Input for scraping a specific Google Maps place."""

    place_url: str = ""
    """Google Maps place URL or Place ID."""
    include_reviews: bool = False
    """Include reviews."""
    max_reviews: int = 0
    """Maximum reviews to scrape."""
    include_images: bool = False
    """Include images."""
    scrape_contact_info: bool = False
    """Scrape contact info from website."""


@dataclass
class OpeningHours:
    """Opening hours for a business."""

    monday: Optional[str] = None
    tuesday: Optional[str] = None
    wednesday: Optional[str] = None
    thursday: Optional[str] = None
    friday: Optional[str] = None
    saturday: Optional[str] = None
    sunday: Optional[str] = None


@dataclass
class PopularTimesHour:
    """A single hour entry in popular times."""

    hour: int = 0
    occupancy_percent: int = 0


@dataclass
class PopularTimes:
    """Popular times for a day."""

    day: str = ""
    hours: Optional[list[PopularTimesHour]] = None


@dataclass
class ReviewsDistribution:
    """Distribution of reviews by star rating."""

    one_star: Optional[int] = None
    two_star: Optional[int] = None
    three_star: Optional[int] = None
    four_star: Optional[int] = None
    five_star: Optional[int] = None


@dataclass
class GoogleMapsReview:
    """A single Google Maps review."""

    id: Optional[str] = None
    text: str = ""
    published_at_date: str = ""
    rating: float = 0.0
    likes_count: Optional[int] = None
    reviewer_id: Optional[str] = None
    reviewer_name: Optional[str] = None
    reviewer_photo_url: Optional[str] = None
    reviewer_reviews_count: Optional[int] = None
    response_from_owner: Optional[str] = None
    response_from_owner_date: Optional[str] = None
    image_urls: Optional[list[str]] = None


@dataclass
class GoogleMapsSocialMedia:
    """Social media links for a Google Maps place."""

    facebook: Optional[str] = None
    twitter: Optional[str] = None
    instagram: Optional[str] = None
    linkedin: Optional[str] = None


@dataclass
class GoogleMapsPlace(BusinessInfo):
    """A Google Maps place/business."""

    place_id: str = ""
    name: str = ""
    url: str = ""
    category: Optional[str] = None
    categories: Optional[list[str]] = None
    address: Optional[str] = None
    location: Optional[Location] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    price_level: Optional[int] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    opening_hours: Optional[Any] = None
    popular_times: Optional[list[PopularTimes]] = None
    is_temporarily_closed: Optional[bool] = None
    is_permanently_closed: Optional[bool] = None
    total_score: Optional[float] = None
    reviews_distribution: Optional[ReviewsDistribution] = None
    image_urls: Optional[list[str]] = None
    reviews: Optional[list[GoogleMapsReview]] = None
    contact_info: Optional[ContactInfo] = None
    social_media: Optional[GoogleMapsSocialMedia] = None
    verification_status: Optional[str] = None


@dataclass
class GoogleMapsReviewsInput(PaginationOptions):
    """Input for scraping Google Maps reviews."""

    place_url: str = ""
    """Google Maps place URL."""
    max_results: int = 100
    """Maximum number of reviews to scrape."""
    min_rating: Optional[int] = None
    """Minimum rating filter (1-5)."""
    language: str = "en"
    """Language code."""


# =============================================================================
# FUNCTIONS
# =============================================================================


def search_google_maps(
    input_data: GoogleMapsSearchInput,
    options: Optional[ActorRunOptions] = None,
) -> list[GoogleMapsPlace]:
    """
    Search Google Maps for places matching a query.

    Example::

        places = search_google_maps(GoogleMapsSearchInput(
            query="coffee shops in San Francisco",
            max_results=50,
            include_reviews=True,
            max_reviews_per_place=10,
        ))
        top_coffee = sorted(
            [p for p in places if (p.rating or 0) >= 4.5 and (p.reviews_count or 0) >= 100],
            key=lambda p: p.rating or 0,
            reverse=True,
        )[:10]
        leads = [
            {"name": p.name, "email": p.email, "phone": p.phone}
            for p in top_coffee if p.email
        ]
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "compass/crawler-google-places",
        {
            "searchStringsArray": [input_data.query],
            "maxCrawledPlacesPerSearch": input_data.max_results,
            "language": input_data.language,
            "countryCode": input_data.country,
            "includeReviews": input_data.include_reviews,
            "maxReviews": input_data.max_reviews_per_place,
            "includeImages": input_data.include_images,
            "scrapeCompanyEmails": input_data.scrape_contact_info,
            "scrapeSocialMediaLinks": input_data.scrape_contact_info,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"Google Maps search failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(
        limit=input_data.max_results or 1000,
        offset=input_data.offset or 0,
    ))

    return [_transform_place(p) for p in items]


def scrape_google_maps_place(
    input_data: GoogleMapsPlaceInput,
    options: Optional[ActorRunOptions] = None,
) -> GoogleMapsPlace:
    """
    Scrape detailed data for a specific Google Maps place.

    Example::

        place = scrape_google_maps_place(GoogleMapsPlaceInput(
            place_url="https://maps.google.com/maps?cid=12345",
            include_reviews=True,
            max_reviews=100,
            scrape_contact_info=True,
        ))
        import time
        thirty_days_ago = time.time() * 1000 - (30 * 24 * 60 * 60 * 1000)
        recent_excellent = [r for r in (place.reviews or []) if r.rating == 5]
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "compass/crawler-google-places",
        {
            "startUrls": [input_data.place_url],
            "includeReviews": input_data.include_reviews,
            "maxReviews": input_data.max_reviews,
            "includeImages": input_data.include_images,
            "scrapeCompanyEmails": input_data.scrape_contact_info,
            "scrapeSocialMediaLinks": input_data.scrape_contact_info,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"Google Maps place scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(limit=1))

    if not items:
        raise RuntimeError(f"Place not found: {input_data.place_url}")

    return _transform_place(items[0])


def scrape_google_maps_reviews(
    input_data: GoogleMapsReviewsInput,
    options: Optional[ActorRunOptions] = None,
) -> list[GoogleMapsReview]:
    """
    Scrape reviews for a Google Maps place.

    Example::

        reviews = scrape_google_maps_reviews(GoogleMapsReviewsInput(
            place_url="https://maps.google.com/maps?cid=12345",
            max_results=500,
            language="en",
        ))
        detailed = [r for r in reviews if len(r.text) > 100 and r.image_urls]
        negative = [r for r in reviews if r.rating <= 2]
        positive = [r for r in reviews if r.rating >= 4]
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "compass/Google-Maps-Reviews-Scraper",
        {
            "startUrls": [input_data.place_url],
            "maxReviews": input_data.max_results,
            "reviewsSort": "newest",
            "language": input_data.language,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"Google Maps reviews scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(
        limit=input_data.max_results or 1000,
        offset=input_data.offset or 0,
    ))

    reviews = [_transform_review(r) for r in items]

    if input_data.min_rating is not None:
        reviews = [r for r in reviews if r.rating >= input_data.min_rating]

    return reviews


# =============================================================================
# HELPERS
# =============================================================================


def _transform_place(place: dict[str, Any]) -> GoogleMapsPlace:
    """Transform raw Google Maps place data to our standard format."""
    loc = place.get("location") or {}

    reviews = None
    if place.get("reviews"):
        reviews = [_transform_review(r) for r in place["reviews"]]

    return GoogleMapsPlace(
        place_id=place.get("placeId", ""),
        name=place.get("title") or place.get("name", ""),
        url=place.get("url", ""),
        category=place.get("categoryName"),
        categories=place.get("categories") or ([place.get("categoryName")] if place.get("categoryName") else None),
        address=place.get("address"),
        location=Location(
            latitude=loc.get("lat"),
            longitude=loc.get("lng"),
            address=place.get("address"),
            city=place.get("city"),
            state=place.get("state"),
            country=place.get("countryCode"),
            postal_code=place.get("postalCode"),
        ),
        rating=place.get("totalScore"),
        total_score=place.get("totalScore"),
        reviews_count=place.get("reviewsCount"),
        price_level=place.get("priceLevel"),
        phone=place.get("phone"),
        website=place.get("website"),
        email=place.get("email") or place.get("companyEmail"),
        opening_hours=place.get("openingHours"),
        popular_times=place.get("popularTimesHistogram"),
        is_temporarily_closed=place.get("temporarilyClosed"),
        is_permanently_closed=place.get("permanentlyClosed"),
        reviews_distribution=place.get("reviewsDistribution"),
        image_urls=place.get("imageUrls"),
        reviews=reviews,
        contact=ContactInfo(
            email=place.get("email") or place.get("companyEmail"),
            phone=place.get("phone"),
            website=place.get("website"),
        ),
        contact_info=ContactInfo(
            email=place.get("email") or place.get("companyEmail"),
            phone=place.get("phone"),
            website=place.get("website"),
        ),
        social_media=GoogleMapsSocialMedia(
            facebook=place.get("facebookUrl"),
            twitter=place.get("twitterUrl"),
            instagram=place.get("instagramUrl"),
            linkedin=place.get("linkedinUrl"),
        ),
        verification_status=place.get("claimThisBusiness"),
    )


def _transform_review(review: dict[str, Any]) -> GoogleMapsReview:
    """Transform raw Google Maps review data to our standard format."""
    return GoogleMapsReview(
        id=review.get("reviewId"),
        text=review.get("text") or review.get("reviewText", ""),
        published_at_date=review.get("publishedAtDate") or review.get("publishAt", ""),
        rating=review.get("stars") or review.get("rating", 0),
        likes_count=review.get("likesCount"),
        reviewer_id=review.get("reviewerId"),
        reviewer_name=review.get("name") or review.get("reviewerName"),
        reviewer_photo_url=review.get("profilePhotoUrl") or review.get("reviewerPhotoUrl"),
        reviewer_reviews_count=review.get("reviewerNumberOfReviews"),
        response_from_owner=review.get("responseFromOwnerText"),
        response_from_owner_date=review.get("responseFromOwnerDate"),
        image_urls=review.get("reviewImageUrls"),
    )
