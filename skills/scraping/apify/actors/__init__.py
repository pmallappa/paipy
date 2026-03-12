#!/usr/bin/env python3
"""
Apify Actors -- File-Based API Wrappers

Direct API access to the most popular Apify actors without MCP overhead.
Filter data in code BEFORE returning to model context for massive token savings.

Categories:
- Social Media: Instagram, LinkedIn, TikTok, YouTube, Facebook
- Business: Google Maps (lead generation)
- E-commerce: Amazon
- Web: General-purpose web scraper

Token Efficiency Example:
- MCP approach: ~50,000 tokens (full unfiltered dataset)
- Code-first approach: ~500 tokens (filtered top 10 results)
- Savings: 99% token reduction!
"""

import importlib as _importlib
import sys as _sys

# Social Media (directory is "social-media" -- hyphen not valid in Python imports)
_sm = _importlib.import_module("." + "social-media", __package__)
_sys.modules[__name__ + ".social_media"] = _sm  # alias for convenience

# Re-export everything from social-media subpackage
_names = getattr(_sm, "__all__", None)
if _names is None:
    _names = [n for n in dir(_sm) if not n.startswith("_")]
for _n in _names:
    globals()[_n] = getattr(_sm, _n)

# Business & Lead Generation
from .business import *  # noqa: F401,F403

# E-commerce
from .ecommerce import *  # noqa: F401,F403

# Web Scraping
from .web import *  # noqa: F401,F403
