"""Refresh the Grey Cells Market Pulse cache independently of the listing pipeline.

Usage:
    python src/update_market_pulse.py
    python src/update_market_pulse.py --no-download

The Zillow ZORI CSV is downloaded by default. Apartment List publishes the
remaining three indicators via its data-download page; save the metro-level,
wide-format files as:
    data/market_sources/vacancy.csv
    data/market_sources/time_to_lease.csv
    data/market_sources/concessions.csv

Each CSV should have a "RegionName" or "location" column and monthly columns
(YYYY-MM or YYYY-MM-DD), one Seattle metro row. Values for vacancy and
concessions may be fractions (0.06) or percentages (6.0), while time-to-lease
values must be in days. If files are missing, prior cached values are kept.

No Internet access is needed when running with --no-download.
"""
import argparse
import csv
import io
import json
import math
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from market_pulse import CACHE_PATH, load_market_cache

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "market_sources"
ZILLOW_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zori/"
    "Metro_zori_uc_sfrcondomfr_sm_sa_month.csv"
)
METRO_KEYS = ("seattle-tacoma-bellevue", "seattle-tacoma", "seattle-bellevue")


def load_csv(content):
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        raise ValueError("CSV has no data rows")
    return rows


def matching_row(rows, national=False):
    for row in rows:
        name = str(row.get("RegionName") or row.get("location") or row.get("Location") or row.get("name") or "").strip().lower()
        if national and name in ("united states", "national", "us", "usa"):
            return row
        if not national and any(key in name for key in METRO_KEYS):
            return row
    raise ValueError("Matching national/Seattle metro row not found")


def monthly_values(row):
    values = {}
    for key, text in row.items():
        if not key or len(key) < 7 or key[4] != "-":
            continue
        try:
            year, month = int(key[:4]), int(key[5:7])
            date(year, month, 1)
            numeric = float(str(text or "").strip().replace(",", "").replace("%", ""))
            if math.isfinite(numeric) and numeric >= 0:
                values[f"{year:04d}-{month:02d}"] = numeric
        except (ValueError, TypeError):
            continue
    if not values:
        raise ValueError("No valid monthly observations found")
    return values


def year_ago(month):
    return f"{int(month[:4])-1}{month[4:]}"


def calculate_rent_growth(csv_text):
    rows = load_csv(csv_text)
    sea = monthly_values(matching_row(rows))
    us = monthly_values(matching_row(rows, national=True))
    months = sorted(set(sea) & set(us))
    points = []
    for month in months:
        prior = year_ago(month)
        if prior not in sea or prior not in us or sea[prior] <= 0 or us[prior] <= 0:
            continue
        points.append({
            "month": month,
            "seattle": round((sea[month] / sea[prior] - 1) * 100, 3),
            "us": round((us[month] / us[prior] - 1) * 100, 3),
        })
    if not points:
        raise ValueError("Not enough matching monthly history to compute year-over-year growth")
    return {"series": points[-13:]}


def parse_metric_csv(csv_text, kind):
    rows = load_csv(csv_text)
    sea = monthly_values(matching_row(rows))
    # A fraction such as 0.067 becomes 6.7%. Reject mixed or ambiguous scaling.
    if kind in ("vacancy", "concessions"):
        values = list(sea.values())
        if max(values) <= 1:
            sea = {month: value * 100 for month, value in sea.items()}
        elif any(0 < value < 1 for value in values):
            raise ValueError("Ambiguous percentage units; expected consistent fractions or percent")
        if any(value > 100 for value in sea.values()):
            raise ValueError("Percentage exceeds 100")
    return {"series": [{"month": m, "seattle": round(v, 3)} for m, v in sorted(sea.items())[-13:]]}


def refresh(no_download=False, cache_path=CACHE_PATH, source_dir=SOURCE_DIR):
    data = load_market_cache(cache_path)
    cards = data.get("cards")
    cards = dict(cards) if isinstance(cards, dict) else {}
    changed = []

    if not no_download:
        try:
            request = Request(ZILLOW_URL, headers={"User-Agent": "GreyCellsMarketPulse/1.0"})
            with urlopen(request, timeout=25) as response:
                csv_text = response.read(6_000_000).decode("utf-8-sig")
            cards["rent_growth"] = calculate_rent_growth(csv_text)
            changed.append("rent_growth")
        except Exception as exc:
            print(f"WARNING: Zillow refresh skipped; previous data retained: {exc}")

    for key in ("vacancy", "time_to_lease", "concessions"):
        path = Path(source_dir) / f"{key}.csv"
        if not path.is_file():
            print(f"INFO: {path.name} not found; retaining previous {key} data")
            continue
        try:
            cards[key] = parse_metric_csv(path.read_text(encoding="utf-8-sig"), key)
            changed.append(key)
        except (ValueError, OSError) as exc:
            print(f"WARNING: Skipping {path.name}; previous data retained: {exc}")

    if not changed:
        print("No updates; existing cache unchanged.")
        return False

    payload = {
        "schema_version": 1,
        "refreshed_at_utc": datetime.now(timezone.utc).isoformat(),
        "cards": cards,
    }
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=cache_path.parent, encoding="utf-8", delete=False, suffix=".tmp") as temp:
            json.dump(payload, temp, indent=2)
            temp_name = temp.name
        os.replace(temp_name, cache_path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    print("Updated:", ", ".join(changed))
    print("Cache:", cache_path)
    return True


def main():
    parser = argparse.ArgumentParser(description="Update the local Grey Cells rental-market cache.")
    parser.add_argument("--no-download", action="store_true", help="Use local CSVs only; do not download Zillow data")
    args = parser.parse_args()
    refresh(no_download=args.no_download)


if __name__ == "__main__":
    main()
