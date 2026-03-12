#!/usr/bin/env python3
"""Fetch historical data from FRED API for US Metrics analysis."""
from __future__ import annotations
import argparse, json, math, os, sys
from datetime import datetime, timezone, timedelta
from typing import Optional
import httpx

CORE_SERIES = {
    "GDPC1": {"name": "Real GDP", "category": "Economic Output", "unit": "Billions of Chained 2017 Dollars"},
    "UNRATE": {"name": "Unemployment Rate (U-3)", "category": "Employment", "unit": "Percent"},
    "CPIAUCSL": {"name": "CPI-U All Items", "category": "Inflation", "unit": "Index 1982-84=100"},
    "FEDFUNDS": {"name": "Fed Funds Rate", "category": "Financial", "unit": "Percent"},
    "DGS10": {"name": "10-Year Treasury Yield", "category": "Financial", "unit": "Percent"},
    "MSPUS": {"name": "Median Sales Price of Houses", "category": "Housing", "unit": "Dollars"},
    "MORTGAGE30US": {"name": "30-Year Mortgage Rate", "category": "Housing", "unit": "Percent"},
    "PAYEMS": {"name": "Nonfarm Payrolls", "category": "Employment", "unit": "Thousands of Persons"},
    "UMCSENT": {"name": "Consumer Sentiment (UMich)", "category": "Consumer", "unit": "Index 1966:Q1=100"},
    "PSAVERT": {"name": "Personal Saving Rate", "category": "Consumer", "unit": "Percent"},
}

def fetch_fred_series(series_id: str, years: int = 10) -> Optional[dict]:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        print("Error: FRED_API_KEY not set", file=sys.stderr); sys.exit(1)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=years * 365)
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={api_key}&file_type=json&observation_start={start_date.strftime('%Y-%m-%d')}&observation_end={end_date.strftime('%Y-%m-%d')}"
    try:
        resp = httpx.get(url, timeout=30)
        if resp.status_code != 200: print(f"Error fetching {series_id}: HTTP {resp.status_code}", file=sys.stderr); return None
        data = resp.json()
        if not data.get("observations"): return None
        info = CORE_SERIES.get(series_id, {"name": series_id, "category": "Unknown", "unit": "Unknown"})
        observations = [{"date": o["date"], "value": float(o["value"])} for o in data["observations"] if o["value"] != "."]
        values = [o["value"] for o in observations]
        stats = {"min": min(values), "max": max(values), "mean": sum(values)/len(values), "count": len(values)} if values else None
        return {"series_id": series_id, "name": info["name"], "category": info["category"], "unit": info["unit"],
                "observations": observations, "latest": observations[-1] if observations else None, "stats": stats}
    except Exception as e:
        print(f"Error fetching {series_id}: {e}", file=sys.stderr); return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("series", nargs="*")
    parser.add_argument("--years", type=int, default=10)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    series_ids = list(CORE_SERIES.keys()) if args.all else args.series
    if not series_ids: print("Error: Specify a series ID or use --all", file=sys.stderr); sys.exit(1)
    results = []
    for sid in series_ids:
        print(f"Fetching {sid}...", file=sys.stderr)
        data = fetch_fred_series(sid, args.years)
        if data: results.append(data)
    if args.json: print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(f"\n{'='*60}\n{r['name']} ({r['series_id']})\nCategory: {r['category']}\nUnit: {r['unit']}")
            if r["latest"]: print(f"Latest: {r['latest']['value']} ({r['latest']['date']})")
            if r["stats"]: print(f"Range: {r['stats']['min']:.2f} - {r['stats']['max']:.2f}\nMean: {r['stats']['mean']:.2f}")

if __name__ == "__main__": main()
