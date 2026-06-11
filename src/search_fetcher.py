import re
import sqlite3
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup

from db import get_connection


SOURCE = "craigslist"

# Craigslist often paginates with an offset parameter like s=0, s=120, s=240.
# We keep this configurable and conservative.
PAGE_SIZE = 120
MAX_PAGES_PER_SEARCH = 10


def get_utc_now() -> str:
    """Return current UTC timestamp as a string."""
    return datetime.now(timezone.utc).isoformat()


def parse_price(price_text: Optional[str]) -> Optional[int]:
    """
    Convert Craigslist price text like '$2,400' into integer 2400.
    """
    if not price_text:
        return None

    digits = re.sub(r"[^\d]", "", price_text)

    if not digits:
        return None

    return int(digits)


def extract_source_listing_id(url: str) -> Optional[str]:
    """
    Extract Craigslist posting ID from URL.

    Example:
    https://seattle.craigslist.org/see/apa/d/seattle-example/1234567890.html
    → 1234567890
    """
    match = re.search(r"/(\d+)\.html", url)

    if not match:
        return None

    return match.group(1)


def set_query_param(url: str, key: str, value: str) -> str:
    """
    Return a URL with one query parameter added/replaced.

    Used for Craigslist pagination, e.g. setting s=120.
    """
    parsed = urlparse(url)
    query_pairs = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query_pairs[key] = value

    new_query = urlencode(query_pairs)

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment,
        )
    )


def build_paginated_url(base_url: str, offset: int) -> str:
    """
    Build a Craigslist search URL for a given result offset.
    """
    return set_query_param(base_url, "s", str(offset))


def fetch_active_search_configs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get active saved searches from search_config."""
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT search_id, name, source, url
        FROM search_config
        WHERE active = 1;
        """
    )

    return cursor.fetchall()


def create_fetch_run(conn: sqlite3.Connection) -> int:
    """Create a new fetch_run row and return run_id."""
    now = get_utc_now()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO fetch_run (
            started_at,
            status
        )
        VALUES (?, ?);
        """,
        (now, "running"),
    )

    conn.commit()
    return cursor.lastrowid


def complete_fetch_run(
    conn: sqlite3.Connection,
    run_id: int,
    status: str,
    records_found: int,
    records_new: int,
    error_message: Optional[str] = None,
) -> None:
    """Mark a fetch run as completed or failed."""
    now = get_utc_now()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE fetch_run
        SET completed_at = ?,
            status = ?,
            records_found = ?,
            records_new = ?,
            error_message = ?
        WHERE run_id = ?;
        """,
        (now, status, records_found, records_new, error_message, run_id),
    )

    conn.commit()


def fetch_html(url: str) -> str:
    """Fetch HTML from a search URL."""
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


def parse_search_results(html: str, base_url: str) -> list[dict]:
    """
    Parse Craigslist search results.

    This intentionally uses a few selector options because Craigslist markup can vary.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    cards = soup.select("li.cl-static-search-result")

    if not cards:
        cards = soup.select("li.result-row")

    print(f"Parser found {len(cards)} result cards.")

    for card in cards:
        link = card.select_one("a")

        if not link or not link.get("href"):
            continue

        url = urljoin(base_url, link["href"])
        source_listing_id = extract_source_listing_id(url)

        if not source_listing_id:
            continue

        title_el = (
            card.select_one(".title")
            or card.select_one(".result-title")
            or card.select_one("div.title")
        )

        price_el = (
            card.select_one(".price")
            or card.select_one(".result-price")
        )

        neighborhood_el = (
            card.select_one(".location")
            or card.select_one(".result-hood")
        )

        title = title_el.get_text(" ", strip=True) if title_el else None
        price = parse_price(price_el.get_text(" ", strip=True)) if price_el else None
        neighborhood = neighborhood_el.get_text(" ", strip=True) if neighborhood_el else None

        results.append(
            {
                "source": SOURCE,
                "source_listing_id": source_listing_id,
                "url": url,
                "title": title,
                "price": price,
                "neighborhood": neighborhood,
            }
        )

    return results


def upsert_listing(conn: sqlite3.Connection, listing: dict) -> tuple[int, bool]:
    """
    Insert a new listing or update an existing listing.

    Returns:
        listing_id, is_new
    """
    now = get_utc_now()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT listing_id
        FROM listing
        WHERE source = ?
          AND source_listing_id = ?;
        """,
        (listing["source"], listing["source_listing_id"]),
    )

    existing = cursor.fetchone()

    if existing:
        listing_id = existing[0]

        cursor.execute(
            """
            UPDATE listing
            SET url = ?,
                title = COALESCE(?, title),
                price = COALESCE(?, price),
                neighborhood = COALESCE(?, neighborhood),
                last_seen = ?
            WHERE listing_id = ?;
            """,
            (
                listing["url"],
                listing["title"],
                listing["price"],
                listing["neighborhood"],
                now,
                listing_id,
            ),
        )

        return listing_id, False

    cursor.execute(
        """
        INSERT INTO listing (
            source,
            source_listing_id,
            url,
            title,
            price,
            neighborhood,
            first_seen,
            last_seen
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            listing["source"],
            listing["source_listing_id"],
            listing["url"],
            listing["title"],
            listing["price"],
            listing["neighborhood"],
            now,
            now,
        ),
    )

    return cursor.lastrowid, True


def insert_observation(
    conn: sqlite3.Connection,
    listing_id: int,
    run_id: int,
    search_id: int,
    listing: dict,
) -> None:
    """Insert one observation for a listing seen in this run."""
    now = get_utc_now()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO listing_observation (
            listing_id,
            run_id,
            search_id,
            observed_at,
            observed_title,
            observed_price,
            observed_neighborhood
        )
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (
            listing_id,
            run_id,
            search_id,
            now,
            listing["title"],
            listing["price"],
            listing["neighborhood"],
        ),
    )


def fetch_all_pages_for_search(search: sqlite3.Row) -> list[dict]:
    """
    Fetch multiple Craigslist search-result pages for one saved search.

    Stops when:
    - a page returns no listings
    - a page returns only listings already seen during this SearchFetcher run
    - MAX_PAGES_PER_SEARCH is reached
    """
    all_listings = []
    seen_source_listing_ids = set()

    for page_index in range(MAX_PAGES_PER_SEARCH):
        offset = page_index * PAGE_SIZE
        page_url = build_paginated_url(search["url"], offset)

        print(f"\nFetching page {page_index + 1}/{MAX_PAGES_PER_SEARCH}")
        print(f"Offset: {offset}")
        print(f"URL: {page_url}")

        html = fetch_html(page_url)
        page_listings = parse_search_results(html, page_url)

        if not page_listings:
            print("No listings found on this page. Stopping pagination.")
            break

        new_on_this_page = []

        for listing in page_listings:
            source_listing_id = listing["source_listing_id"]

            if source_listing_id in seen_source_listing_ids:
                continue

            seen_source_listing_ids.add(source_listing_id)
            new_on_this_page.append(listing)

        print(f"Unique listings on this page: {len(new_on_this_page)}")

        if not new_on_this_page:
            print("No new unique listings on this page. Stopping pagination.")
            break

        all_listings.extend(new_on_this_page)

    return all_listings


def run_search_fetcher() -> None:
    """Main SearchFetcher workflow."""
    conn = get_connection()
    run_id = create_fetch_run(conn)

    total_found = 0
    total_new = 0

    try:
        searches = fetch_active_search_configs(conn)

        if not searches:
            complete_fetch_run(
                conn=conn,
                run_id=run_id,
                status="success",
                records_found=0,
                records_new=0,
                error_message="No active searches found.",
            )
            print("No active searches found.")
            return

        for search in searches:
            print("=" * 100)
            print(f"Fetching search: {search['name']}")
            print(f"Base URL: {search['url']}")

            listings = fetch_all_pages_for_search(search)

            print(f"\nTotal unique listings parsed for this search: {len(listings)}")

            for listing in listings:
                listing_id, is_new = upsert_listing(conn, listing)

                insert_observation(
                    conn=conn,
                    listing_id=listing_id,
                    run_id=run_id,
                    search_id=search["search_id"],
                    listing=listing,
                )

                total_found += 1

                if is_new:
                    total_new += 1

        conn.commit()

        complete_fetch_run(
            conn=conn,
            run_id=run_id,
            status="success",
            records_found=total_found,
            records_new=total_new,
        )

        print("\nSearchFetcher complete.")
        print(f"Records found: {total_found}")
        print(f"New listings: {total_new}")

    except Exception as exc:
        conn.rollback()

        complete_fetch_run(
            conn=conn,
            run_id=run_id,
            status="failed",
            records_found=total_found,
            records_new=total_new,
            error_message=str(exc),
        )

        print("SearchFetcher failed.")
        print(str(exc))
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    run_search_fetcher()