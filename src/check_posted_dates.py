from db import get_connection


def main() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM listing_detail
        WHERE fetch_status = 'success'
          AND posted_at IS NULL;
        """
    )

    missing = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM listing_detail
        WHERE fetch_status = 'success'
          AND posted_at IS NOT NULL;
        """
    )

    found = cursor.fetchone()[0]

    print(f"Posted dates found: {found}")
    print(f"Missing posted_at: {missing}")

    conn.close()


if __name__ == "__main__":
    main()