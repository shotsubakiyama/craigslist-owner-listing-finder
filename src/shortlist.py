import argparse
import json
import re
import textwrap

from db import get_connection


def format_price(price) -> str:
    if price is None:
        return "unknown"
    return f"${price:,}"


def clean_text(text: str | None, width: int = 100) -> str:
    if not text:
        return ""

    text = " ".join(text.split())
    return textwrap.fill(text, width=width)


def parse_json_list(value: str | None) -> list[str]:
    if not value:
        return []

    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        return []

    return []


def normalize_for_fingerprint(value: str | None) -> str:
    if not value:
        return ""

    value = value.lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def get_duplicate_fingerprint(row: tuple) -> str:
    """
    Create a simple near-duplicate fingerprint.

    This intentionally catches reposts with the same title/price/neighborhood,
    like repeated Craigslist posts for the same 5-unit building.
    """
    (
        listing_id,
        title,
        price,
        neighborhood,
        url,
        scoring_version,
        grey_cells_score,
        owner_signal_score,
        owner_signal_reasons,
        human_signal_score,
        human_signal_reasons,
        fit_score,
        fit_reasons,
        property_type,
        description_preview,
    ) = row

    normalized_title = normalize_for_fingerprint(title)
    normalized_neighborhood = normalize_for_fingerprint(neighborhood)
    normalized_description_start = normalize_for_fingerprint(description_preview)[:120]

    return "|".join(
        [
            normalized_title,
            str(price or ""),
            normalized_neighborhood,
            normalized_description_start,
        ]
    )


def get_shortlist(limit: int) -> list[tuple]:
    conn = get_connection()
    cursor = conn.cursor()

    # Pull more than requested so we can dedupe in Python and still return enough rows.
    candidate_limit = max(limit * 6, 50)

    cursor.execute(
        """
        WITH latest_score AS (
            SELECT
                s.*
            FROM listing_score s
            JOIN (
                SELECT
                    listing_id,
                    MAX(scored_at) AS max_scored_at
                FROM listing_score
                GROUP BY listing_id
            ) latest
                ON s.listing_id = latest.listing_id
               AND s.scored_at = latest.max_scored_at
        )
        SELECT
            l.listing_id,
            l.title,
            l.price,
            l.neighborhood,
            l.url,
            s.scoring_version,
            s.grey_cells_score,
            s.owner_signal_score,
            s.owner_signal_reasons,
            s.human_signal_score,
            s.human_signal_reasons,
            s.fit_score,
            s.fit_reasons,
            s.property_type,
            SUBSTR(d.description, 1, 700) AS description_preview
        FROM latest_score s
        JOIN listing l
            ON s.listing_id = l.listing_id
        JOIN listing_detail d
            ON l.listing_id = d.listing_id
        WHERE s.grey_cells_score IS NOT NULL
        ORDER BY s.grey_cells_score DESC
        LIMIT ?;
        """,
        (candidate_limit,),
    )

    rows = cursor.fetchall()
    conn.close()

    deduped_rows = []
    seen_fingerprints = set()

    for row in rows:
        fingerprint = get_duplicate_fingerprint(row)

        if fingerprint in seen_fingerprints:
            continue

        seen_fingerprints.add(fingerprint)
        deduped_rows.append(row)

        if len(deduped_rows) >= limit:
            break

    return deduped_rows


def print_reason_block(label: str, reasons_json: str | None, max_reasons: int = 5) -> None:
    reasons = parse_json_list(reasons_json)

    if not reasons:
        return

    print(f"  {label}:")
    for reason in reasons[:max_reasons]:
        print(f"    - {reason}")


def print_shortlist(limit: int) -> None:
    rows = get_shortlist(limit)

    print("\nGrey Cells Shortlist")
    print("=" * 100)
    print(f"Showing top {len(rows)} deduped listings\n")

    if not rows:
        print("No scored listings found.")
        return

    for rank, row in enumerate(rows, start=1):
        (
            listing_id,
            title,
            price,
            neighborhood,
            url,
            scoring_version,
            grey_cells_score,
            owner_signal_score,
            owner_signal_reasons,
            human_signal_score,
            human_signal_reasons,
            fit_score,
            fit_reasons,
            property_type,
            description_preview,
        ) = row

        print("-" * 100)
        print(f"#{rank} | Grey Cells Score: {grey_cells_score}")
        print(f"Title: {title}")
        print(f"Price: {format_price(price)}")
        print(f"Neighborhood: {neighborhood or 'unknown'}")
        print(f"Property Type: {property_type}")
        print(f"Listing ID: {listing_id}")
        print(f"Scoring Version: {scoring_version}")
        print()
        print("Signals:")
        print(f"  Owner Signal: {owner_signal_score}")
        print(f"  Human Signal: {human_signal_score}")
        print(f"  Fit Score: {fit_score}")
        print()
        print("Reasons:")
        print_reason_block("Owner", owner_signal_reasons)
        print_reason_block("Human", human_signal_reasons)
        print_reason_block("Fit", fit_reasons)
        print()
        print("Description:")
        print(clean_text(description_preview))
        print()
        print(f"URL: {url}")
        print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show the Grey Cells Shortlist."
    )

    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=10,
        help="Number of listings to show. Example: --limit 5",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.limit <= 0:
        raise ValueError("Limit must be greater than 0.")

    print_shortlist(args.limit)


if __name__ == "__main__":
    main()