import argparse
import re

from db import get_connection


def extract_source_listing_id(value: str) -> str:
    match = re.search(r"/(\d+)\.html", value)
    if match:
        return match.group(1)

    return value.strip()


def lookup_listing(source_listing_id: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            l.listing_id,
            l.source_listing_id,
            l.title,
            l.price,
            l.neighborhood,
            l.url,
            l.first_seen,
            l.last_seen,
            d.fetch_status,
            LENGTH(d.description) AS description_length,
            s.grey_cells_score,
            s.owner_signal_score,
            s.human_signal_score,
            s.fit_score,
            s.property_type
        FROM listing l
        LEFT JOIN listing_detail d
            ON l.listing_id = d.listing_id
        LEFT JOIN listing_score s
            ON l.listing_id = s.listing_id
        WHERE l.source_listing_id = ?
        ORDER BY s.scored_at DESC
        LIMIT 1;
        """,
        (source_listing_id,),
    )

    row = cursor.fetchone()

    if not row:
        print(f"Listing {source_listing_id} not found in database.")
        conn.close()
        return

    (
        listing_id,
        source_listing_id,
        title,
        price,
        neighborhood,
        url,
        first_seen,
        last_seen,
        fetch_status,
        description_length,
        grey_cells_score,
        owner_signal_score,
        human_signal_score,
        fit_score,
        property_type,
    ) = row

    print("\nListing found")
    print("=" * 80)
    print(f"listing_id: {listing_id}")
    print(f"source_listing_id: {source_listing_id}")
    print(f"title: {title}")
    print(f"price: {price}")
    print(f"neighborhood: {neighborhood}")
    print(f"url: {url}")
    print(f"first_seen: {first_seen}")
    print(f"last_seen: {last_seen}")
    print(f"detail_fetch_status: {fetch_status}")
    print(f"description_length: {description_length}")
    print()
    print("Scores")
    print("-" * 80)
    print(f"grey_cells_score: {grey_cells_score}")
    print(f"owner_signal_score: {owner_signal_score}")
    print(f"human_signal_score: {human_signal_score}")
    print(f"fit_score: {fit_score}")
    print(f"property_type: {property_type}")

    cursor.execute(
        """
        SELECT
            SUBSTR(d.description, 1, 1200)
        FROM listing_detail d
        WHERE d.listing_id = ?;
        """,
        (listing_id,),
    )

    detail_row = cursor.fetchone()

    if detail_row and detail_row[0]:
        print()
        print("Description preview")
        print("-" * 80)
        print(detail_row[0])

    conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Look up a listing by Craigslist ID or Craigslist URL."
    )

    parser.add_argument(
        "listing",
        help="Craigslist listing ID or URL. Example: 7938136991",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_listing_id = extract_source_listing_id(args.listing)
    lookup_listing(source_listing_id)


if __name__ == "__main__":
    main()