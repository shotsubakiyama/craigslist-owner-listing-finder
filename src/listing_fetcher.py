import re
import sqlite3
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from db import get_connection


MAX_LISTINGS_PER_RUN = 50
DELAY_SECONDS = 1.5


def get_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }

    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return response.text


def parse_number_from_text(text: str) -> Optional[float]:
    match = re.search(r"(\d+(\.\d+)?)", text)

    if not match:
        return None

    return float(match.group(1))


def parse_posted_at(soup: BeautifulSoup) -> Optional[str]:
    """
    Parse Craigslist's actual posted timestamp from the listing detail page.

    Craigslist commonly exposes this in a <time datetime="..."> element.
    """
    selectors = [
        "p.postinginfo time[datetime]",
        "time.date[datetime]",
        "time[datetime]",
    ]

    for selector in selectors:
        time_el = soup.select_one(selector)

        if time_el and time_el.get("datetime"):
            return time_el["datetime"]

    return None


def parse_listing_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    posted_at = parse_posted_at(soup)

    description_el = soup.select_one("#postingbody")
    description = None

    if description_el:
        description = description_el.get_text("\n", strip=True)

        description = description.replace(
            "QR Code Link to This Post",
            "",
        ).strip()

    bedrooms = None
    bathrooms = None
    sqft = None

    attr_groups = soup.select(".attrgroup span")

    for attr in attr_groups:
        text = attr.get_text(" ", strip=True).lower()

        if "br" in text and bedrooms is None:
            bedrooms = parse_number_from_text(text)

        if "ba" in text and bathrooms is None:
            bathrooms = parse_number_from_text(text)

        if "ft2" in text or "sqft" in text:
            parsed_sqft = parse_number_from_text(text)
            if parsed_sqft is not None:
                sqft = int(parsed_sqft)

    map_el = soup.select_one("#map")
    latitude = None
    longitude = None

    if map_el:
        lat = map_el.get("data-latitude")
        lon = map_el.get("data-longitude")

        if lat:
            latitude = float(lat)

        if lon:
            longitude = float(lon)

    return {
        "posted_at": posted_at,
        "description": description,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "sqft": sqft,
        "latitude": latitude,
        "longitude": longitude,
        "raw_html": html,
    }


def get_listings_missing_details(
    conn: sqlite3.Connection,
    limit: int = MAX_LISTINGS_PER_RUN,
) -> list[sqlite3.Row]:
    """
    Find listings that need detail fetching.

    Includes:
    - listings with no detail row
    - listings with successful detail row but missing posted_at, so we can backfill posted date
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            l.listing_id,
            l.url,
            l.title
        FROM listing l
        LEFT JOIN listing_detail d
            ON l.listing_id = d.listing_id
        WHERE d.listing_id IS NULL
           OR (
                d.fetch_status = 'success'
                AND d.posted_at IS NULL
           )
        ORDER BY l.listing_id ASC
        LIMIT ?;
        """,
        (limit,),
    )

    return cursor.fetchall()


def save_listing_detail(
    conn: sqlite3.Connection,
    listing_id: int,
    detail: dict,
    fetch_status: str,
    error_message: Optional[str] = None,
) -> None:
    now = get_utc_now()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO listing_detail (
            listing_id,
            posted_at,
            description,
            bedrooms,
            bathrooms,
            sqft,
            latitude,
            longitude,
            raw_html,
            fetched_at,
            fetch_status,
            error_message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            listing_id,
            detail.get("posted_at"),
            detail.get("description"),
            detail.get("bedrooms"),
            detail.get("bathrooms"),
            detail.get("sqft"),
            detail.get("latitude"),
            detail.get("longitude"),
            detail.get("raw_html"),
            now,
            fetch_status,
            error_message,
        ),
    )


def save_failed_detail(
    conn: sqlite3.Connection,
    listing_id: int,
    error_message: str,
) -> None:
    save_listing_detail(
        conn=conn,
        listing_id=listing_id,
        detail={
            "posted_at": None,
            "description": None,
            "bedrooms": None,
            "bathrooms": None,
            "sqft": None,
            "latitude": None,
            "longitude": None,
            "raw_html": None,
        },
        fetch_status="failed",
        error_message=error_message,
    )


def run_listing_fetcher() -> None:
    conn = get_connection()

    listings = get_listings_missing_details(conn)

    if not listings:
        print("No listings missing details or posted_at.")
        conn.close()
        return

    print(f"ListingFetcher will fetch {len(listings)} listings.")

    success_count = 0
    failure_count = 0
    posted_at_count = 0

    try:
        for listing in listings:
            listing_id = listing["listing_id"]
            url = listing["url"]
            title = listing["title"]

            print(f"\nFetching listing_id={listing_id}: {title}")
            print(url)

            try:
                html = fetch_html(url)
                detail = parse_listing_detail(html)

                save_listing_detail(
                    conn=conn,
                    listing_id=listing_id,
                    detail=detail,
                    fetch_status="success",
                )

                conn.commit()
                success_count += 1

                if detail.get("posted_at"):
                    posted_at_count += 1

                description_length = len(detail["description"] or "")
                print(f"Saved detail. Description length: {description_length}")
                print(f"Posted at: {detail.get('posted_at')}")

            except Exception as exc:
                save_failed_detail(
                    conn=conn,
                    listing_id=listing_id,
                    error_message=str(exc),
                )

                conn.commit()
                failure_count += 1
                print(f"Failed: {exc}")

            time.sleep(DELAY_SECONDS)

        print("\nListingFetcher complete.")
        print(f"Success: {success_count}")
        print(f"Failed: {failure_count}")
        print(f"Posted dates found: {posted_at_count}")

    finally:
        conn.close()


if __name__ == "__main__":
    run_listing_fetcher()