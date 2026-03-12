#!/usr/bin/env python3
"""Update Substrate US-Common-Metrics dataset with fresh data from APIs."""
from __future__ import annotations
import argparse, json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import httpx

SUBSTRATE_PATH = Path.home() / "Projects" / "Substrate" / "Data" / "US-Common-Metrics"
FRED_API_KEY = os.environ.get("FRED_API_KEY")
EIA_API_KEY = os.environ.get("EIA_API_KEY")

METRICS = {
    "UNRATE": {"name": "Unemployment Rate", "category": "Employment", "format": "percent"},
    "FEDFUNDS": {"name": "Fed Funds Rate", "category": "Financial", "format": "percent"},
    "CPIAUCSL": {"name": "CPI All Items", "category": "Inflation", "format": "index"},
    "DGS10": {"name": "10-Year Treasury", "category": "Financial", "format": "percent"},
    "MSPUS": {"name": "Median Home Price", "category": "Housing", "format": "currency"},
}

def fetch_fred(series_id: str) -> Optional[dict]:
    if not FRED_API_KEY: return None
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json&sort_order=desc&limit=1"
    try:
        resp = httpx.get(url, timeout=30)
        if resp.status_code != 200: return None
        obs = resp.json().get("observations", [{}])[0]
        if obs.get("value") == ".": return None
        return {"value": float(obs["value"]), "date": obs["date"]}
    except Exception: return None

def fetch_eia_gas() -> Optional[dict]:
    if not EIA_API_KEY: return None
    url = f"https://api.eia.gov/v2/petroleum/pri/gnd/data/?api_key={EIA_API_KEY}&frequency=weekly&data[0]=value&facets[product][]=EPMR&facets[duoarea][]=NUS&sort[0][column]=period&sort[0][direction]=desc&length=1"
    try:
        resp = httpx.get(url, timeout=30)
        if resp.status_code != 200: return None
        item = resp.json().get("response", {}).get("data", [{}])[0]
        return {"value": float(item["value"]), "date": item["period"]} if item.get("value") else None
    except Exception: return None

def fetch_treasury_debt() -> Optional[dict]:
    url = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny?sort=-record_date&page[size]=1"
    try:
        resp = httpx.get(url, timeout=30)
        if resp.status_code != 200: return None
        item = resp.json().get("data", [{}])[0]
        return {"value": float(item["tot_pub_debt_out_amt"]) / 1e12, "date": item["record_date"]} if item.get("tot_pub_debt_out_amt") else None
    except Exception: return None

def format_value(value: float, fmt: str) -> str:
    if fmt == "percent": return f"{value:.1f}%"
    if fmt == "currency": return f"${value:,.0f}"
    if fmt == "index": return f"{value:.3f}"
    return f"{value:.2f}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not FRED_API_KEY: print("FRED_API_KEY not set", file=sys.stderr); sys.exit(1)
    if not SUBSTRATE_PATH.exists(): print(f"Substrate path not found: {SUBSTRATE_PATH}", file=sys.stderr); sys.exit(1)

    print("=" * 60 + "\nUS-Common-Metrics Update\n" + "=" * 60)
    results = {}
    for mid, config in METRICS.items():
        print(f"  [FRED] {config['name']}...", end=" ")
        data = fetch_fred(mid)
        if data:
            results[mid] = {**data, "name": config["name"], "formatted": format_value(data["value"], config["format"])}
            print(f"{results[mid]['formatted']} ({data['date']})")
        else:
            print("Failed")
        time.sleep(0.1)

    if args.dry_run:
        print(f"\n[DRY RUN] Would update {len(results)} metrics"); return

    # Write CSV
    csv_path = SUBSTRATE_PATH / "us-metrics-current.csv"
    lines = ["metric_id,metric_name,value,formatted_value,period,updated"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for mid, r in results.items():
        lines.append(f"{mid},\"{r['name']}\",{r['value']},\"{r['formatted']}\",{r['date']},{now}")
    csv_path.write_text("\n".join(lines) + "\n")
    print(f"\nUpdate complete. {len(results)} metrics updated.")

if __name__ == "__main__": main()
