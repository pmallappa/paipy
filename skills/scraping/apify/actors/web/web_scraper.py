#!/usr/bin/env python3
"""
Web Scraper (General Purpose)

Apify Actor: apify/web-scraper (94,522 users, 4.39 rating)
Pricing: FREE -- only pay for Apify platform usage

Crawl any website and extract structured data using JavaScript functions.
Most versatile actor -- handles ANY website!
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
class WebScraperInput:
    """Input for the general-purpose web scraper."""

    start_urls: Optional[list[str]] = None
    """URLs to start crawling from."""
    page_function: Optional[str] = None
    """JavaScript function to extract data from each page."""
    link_selector: Optional[str] = None
    """CSS selector for links to follow."""
    pseudo_urls: Optional[list[str]] = None
    """Pseudo-URLs to match for crawling."""
    max_pages_per_crawl: int = 100
    """Maximum pages to crawl."""
    max_crawling_depth: int = 0
    """Maximum crawling depth."""
    use_proxy: bool = False
    """Proxy configuration."""
    wait_until: str = "networkidle2"
    """Wait for dynamic content: 'load', 'domcontentloaded', 'networkidle0', 'networkidle2'."""


@dataclass
class ScrapedPage:
    """A single scraped page result."""

    url: str = ""
    title: Optional[str] = None
    html: Optional[str] = None
    text: Optional[str] = None
    extra: Optional[dict[str, Any]] = None
    """Custom extracted data fields."""


# =============================================================================
# FUNCTIONS
# =============================================================================


def scrape_website(
    input_data: WebScraperInput,
    options: Optional[ActorRunOptions] = None,
) -> list[dict[str, Any]]:
    """
    Scrape data from websites using custom extraction logic.

    Example::

        products = scrape_website(WebScraperInput(
            start_urls=["https://example.com/products"],
            link_selector="a.product-link",
            max_pages_per_crawl=100,
            page_function='''
                async function pageFunction(context) {
                    const { request, $, log } = context
                    return {
                        url: request.url,
                        title: $('h1.product-title').text(),
                        price: $('span.price').text(),
                        description: $('.description').text(),
                        inStock: $('.in-stock').length > 0
                    }
                }
            ''',
        ))
        affordable = [p for p in products if p.get("inStock") and float(p.get("price", "$999").replace("$", "")) < 100]
    """
    apify = Apify()

    default_page_function = """
        async function pageFunction(context) {
            const { request, $, log } = context

            return {
                url: request.url,
                title: $('title').text() || $('h1').first().text(),
                text: $('body').text().trim()
            }
        }
    """

    run_options = None
    if options:
        run_options = {"memory": options.memory, "timeout": options.timeout, "build": options.build}

    pseudo_urls_param = None
    if input_data.pseudo_urls:
        pseudo_urls_param = [{"purl": pattern} for pattern in input_data.pseudo_urls]

    run = apify.call_actor(
        "apify/web-scraper",
        {
            "startUrls": [{"url": u} for u in (input_data.start_urls or [])],
            "pageFunction": input_data.page_function or default_page_function,
            "linkSelector": input_data.link_selector,
            "pseudoUrls": pseudo_urls_param,
            "maxPagesPerCrawl": input_data.max_pages_per_crawl,
            "maxCrawlingDepth": input_data.max_crawling_depth,
            "useProxy": input_data.use_proxy,
            "waitUntil": input_data.wait_until,
        },
        run_options,
    )

    apify.wait_for_run(run.id)

    final_run = apify.get_run(run.id)
    if final_run.status != "SUCCEEDED":
        raise RuntimeError(f"Web scraping failed: {final_run.status}")

    dataset = apify.get_dataset(final_run.default_dataset_id)
    items = dataset.list_items(DatasetOptions(
        limit=input_data.max_pages_per_crawl or 10000,
    ))

    return items


def scrape_page(
    url: str,
    page_function: str,
    options: Optional[ActorRunOptions] = None,
) -> dict[str, Any]:
    """
    Extract structured data from a single page.

    Example::

        product = scrape_page(
            "https://example.com/product/123",
            '''async function pageFunction(context) {
                const { $, request } = context
                return {
                    name: $('h1.product-name').text(),
                    price: $('span.price').text(),
                    rating: parseFloat($('.rating').attr('data-rating')),
                    reviews: parseInt($('.review-count').text()),
                }
            }''',
        )
        print(f"{product['name']} - {product['price']}")
    """
    results = scrape_website(
        WebScraperInput(
            start_urls=[url],
            max_pages_per_crawl=1,
            page_function=page_function,
        ),
        options,
    )

    if not results:
        raise RuntimeError(f"Failed to scrape page: {url}")

    return results[0]
