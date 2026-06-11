import csv
from datetime import datetime
from pathlib import Path

from db import get_connection


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def get_export_path() -> Path:
    today = datetime.now().strftime("%Y%m%d")
    filename = f"listings_for_review_{today}.csv"
    return PROJECT_ROOT / "data" / filename


def main() -> None:
    export_path = get_export_path()

    conn = get_connection()
    cursor = conn.cursor()

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
            l.source_listing_id,
            l.title,
            l.price,
            l.neighborhood,
            l.url,
            d.description,
            d.bedrooms,
            d.bathrooms,
            d.sqft,
            s.scoring_version,
            s.grey_cells_score,
            s.owner_signal_score,
            s.owner_signal_reasons,
            s.human_signal_score,
            s.human_signal_reasons,
            s.fit_score,
            s.fit_reasons,
            s.property_type
        FROM listing l
        JOIN listing_detail d
            ON l.listing_id = d.listing_id
        LEFT JOIN latest_score s
            ON l.listing_id = s.listing_id
        WHERE d.fetch_status = 'success'
        ORDER BY l.listing_id ASC;
        """
    )

    rows = cursor.fetchall()

    headers = [
        "listing_id",
        "source_listing_id",
        "title",
        "price",
        "neighborhood",
        "url",
        "description",
        "bedrooms",
        "bathrooms",
        "sqft",
        "scoring_version",
        "grey_cells_score",
        "owner_signal_score",
        "owner_signal_reasons",
        "human_signal_score",
        "human_signal_reasons",
        "fit_score",
        "fit_reasons",
        "property_type",
    ]

    export_path.parent.mkdir(parents=True, exist_ok=True)

    with open(export_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerows(rows)

    conn.close()

    print(f"Exported {len(rows)} rows to {export_path}")


if __name__ == "__main__":
    main()