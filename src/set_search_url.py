import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "rentals.db"

SEARCH_ID = 1

UPDATED_URL = (
    "https://seattle.craigslist.org/search/apa"
    "?sort=date"
    "&max_price=3500"
    "&min_price=1500"
    "&postal=98105"
    "&search_distance=3"
)


def main() -> None:
    conn = sqlite3.connect(DB_PATH)

    conn.execute(
        """
        UPDATE search_config
        SET url = ?,
            updated_at = datetime('now')
        WHERE search_id = ?;
        """,
        (UPDATED_URL, SEARCH_ID),
    )

    conn.commit()

    rows = conn.execute(
        """
        SELECT search_id, name, url
        FROM search_config
        ORDER BY search_id;
        """
    ).fetchall()

    conn.close()

    print("Current search_config rows:")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()