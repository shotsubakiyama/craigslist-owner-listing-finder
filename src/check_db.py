from db import get_connection


def main() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    tables = [
        "search_config",
        "fetch_run",
        "listing",
        "listing_observation",
        "listing_detail",
        "listing_score",
    ]

    print("Table counts:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table};")
        count = cursor.fetchone()[0]
        print(f"- {table}: {count}")

    print("\nShortlist:")
    cursor.execute(
        """
        SELECT
            l.listing_id,
            l.title,
            l.price,
            l.neighborhood,
            s.grey_cells_score,
            s.owner_signal_score,
            s.human_signal_score,
            s.fit_score,
            s.property_type,
            SUBSTR(d.description, 1, 300) AS description_preview
        FROM listing_score s
        JOIN listing l
            ON s.listing_id = l.listing_id
        JOIN listing_detail d
            ON l.listing_id = d.listing_id
        WHERE s.grey_cells_score IS NOT NULL
        ORDER BY s.grey_cells_score DESC
        LIMIT 10;
        """
    )

    for row in cursor.fetchall():
        print("\n" + "-" * 80)
        print(f"listing_id: {row[0]}")
        print(f"title: {row[1]}")
        print(f"price: {row[2]}")
        print(f"neighborhood: {row[3]}")
        print(f"grey_cells_score: {row[4]}")
        print(f"owner_signal_score: {row[5]}")
        print(f"human_signal_score: {row[6]}")
        print(f"fit_score: {row[7]}")
        print(f"property_type: {row[8]}")
        print("description_preview:")
        print(row[9])

    conn.close()


if __name__ == "__main__":
    main()