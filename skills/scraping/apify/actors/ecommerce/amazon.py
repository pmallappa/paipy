#!/usr/bin/env python3
"""
Amazon Scraper

Top Actors:
- junglee/free-amazon-product-scraper (8,898 users, 4.97 rating)
- axesso_data/amazon-reviews-scraper (1,647 users, 4.62 rating, $0.75/1k reviews)

Extract Amazon product data, reviews, pricing without API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ... import Apify, DatasetOptions
from ...types import ActorRunOptions, PaginationOptions


# =============================================================================
# TYPES
# =============================================================================


@dataclass
class AmazonProductInput:
    """Input for scraping an Amazon product."""

    product_url: str = ""
    """Amazon product URL or ASIN."""
    include_reviews: bool = False
    """Include reviews."""
    max_reviews: int = 0
    """Maximum reviews to scrape."""


@dataclass
class ProductVariant:
    """A product variant."""

    asin: str = ""
    title: str = ""
    price: Optional[float] = None
    image_url: Optional[str] = None


@dataclass
class AmazonReview:
    """A single Amazon review."""

    id: str = ""
    title: str = ""
    text: str = ""
    rating: float = 0.0
    date: str = ""
    verified_purchase: Optional[bool] = None
    helpful: Optional[int] = None
    reviewer_name: Optional[str] = None
    reviewer_url: Optional[str] = None
    images: Optional[list[str]] = None


@dataclass
class AmazonProduct:
    """Amazon product details."""

    asin: str = ""
    title: str = ""
    url: str = ""
    price: Optional[float] = None
    currency: Optional[str] = None
    price_string: Optional[str] = None
    original_price: Optional[float] = None
    discount: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    stars: Optional[float] = None
    description: Optional[str] = None
    features: Optional[list[str]] = None
    images: Optional[list[str]] = None
    variants: Optional[list[ProductVariant]] = None
    availability: Optional[str] = None
    in_stock: Optional[bool] = None
    seller: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    reviews: Optional[list[AmazonReview]] = None


@dataclass
class AmazonReviewsInput(PaginationOptions):
    """Input for scraping Amazon reviews."""

    product_url: str = ""
    """Amazon product URL or ASIN."""
    max_results: int = 100
    """Maximum reviews to scrape."""
    star_rating: Optional[int] = None
    """Star rating filter (1-5)."""
    verified_only: Optional[bool] = None
    """Verified purchases only."""


# =============================================================================
# FUNCTIONS
# =============================================================================


def scrape_amazon_product(
    input_data: AmazonProductInput,
    options: Optional[ActorRunOptions] = None,
) -> AmazonProduct:
    """
    Scrape Amazon product data.

    Example::

        product = scrape_amazon_product(AmazonProductInput(
            product_url="https://www.amazon.com/dp/B08L5VT894",
            include_reviews=True,
            max_reviews=50,
        ))
        print(f"{product.title} - ${product.price}")
        print(f"Rating: {product.rating}/5 ({product.reviews_count} reviews)")
        top_reviews = [r for r in (product.reviews or []) if r.rating == 5 and r.verified_purchase]
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "junglee/free-amazon-product-scraper",
        {
            "startUrls": [input_data.product_url],
            "maxReviews": input_data.max_reviews,
            "includeReviews": input_data.include_reviews,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"Amazon product scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(limit=1))

    if not items:
        raise RuntimeError(f"Product not found: {input_data.product_url}")

    product = items[0]

    reviews = None
    if product.get("topReviews"):
        reviews = [
            AmazonReview(
                id=r.get("id", ""),
                title=r.get("title", ""),
                text=r.get("text") or r.get("body", ""),
                rating=r.get("stars") or r.get("rating", 0),
                date=r.get("date", ""),
                verified_purchase=r.get("verified"),
                helpful=r.get("helpful"),
                reviewer_name=r.get("reviewer"),
                reviewer_url=r.get("reviewerUrl"),
                images=r.get("images"),
            )
            for r in product["topReviews"]
        ]

    return AmazonProduct(
        asin=product.get("asin", ""),
        title=product.get("title", ""),
        url=product.get("url") or input_data.product_url,
        price=product.get("price"),
        currency=product.get("currency"),
        price_string=product.get("priceString"),
        original_price=product.get("originalPrice"),
        discount=product.get("discount"),
        rating=product.get("stars") or product.get("rating"),
        stars=product.get("stars"),
        reviews_count=product.get("reviews") or product.get("reviewsCount"),
        description=product.get("description"),
        features=product.get("features") or product.get("featureBullets"),
        images=product.get("images"),
        variants=product.get("variants"),
        availability=product.get("availability"),
        in_stock=product.get("inStock"),
        seller=product.get("seller"),
        brand=product.get("brand"),
        category=product.get("category"),
        reviews=reviews,
    )


def scrape_amazon_reviews(
    input_data: AmazonReviewsInput,
    options: Optional[ActorRunOptions] = None,
) -> list[AmazonReview]:
    """
    Scrape Amazon product reviews.

    Example::

        reviews = scrape_amazon_reviews(AmazonReviewsInput(
            product_url="https://www.amazon.com/dp/B08L5VT894",
            max_results=500,
            verified_only=True,
        ))
        detailed = [r for r in reviews if len(r.text) > 200 and r.images]
        positive = [r for r in reviews if r.rating >= 4]
        negative = [r for r in reviews if r.rating <= 2]
        print(f"Sentiment: {len(positive)}+ / {len(negative)}-")
    """
    apify = Apify()

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    run = apify.call_actor(
        "axesso_data/amazon-reviews-scraper",
        {
            "urls": [input_data.product_url],
            "maxReviews": input_data.max_results,
            "starRating": input_data.star_rating,
            "verifiedPurchaseOnly": input_data.verified_only,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"Amazon reviews scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(
        limit=input_data.max_results or 1000,
        offset=input_data.offset or 0,
    ))

    return [
        AmazonReview(
            id=review.get("id") or review.get("reviewId", ""),
            title=review.get("title", ""),
            text=review.get("text") or review.get("body", ""),
            rating=review.get("stars") or review.get("rating", 0),
            date=review.get("date", ""),
            verified_purchase=review.get("verifiedPurchase") or review.get("verified"),
            helpful=review.get("helpful") or review.get("helpfulCount"),
            reviewer_name=review.get("reviewerName") or review.get("author"),
            reviewer_url=review.get("reviewerUrl"),
            images=review.get("images") or review.get("reviewImages"),
        )
        for review in items
    ]
