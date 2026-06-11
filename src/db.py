import sqlite3
from pathlib import Path
from datetime import datetime, timezone


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "rentals.db"


def get_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    return conn


def column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()

    return any(column[1] == column_name for column in columns)


def run_migrations(conn: sqlite3.Connection) -> None:
    """
    Lightweight SQLite migrations for existing local databases.

    This lets us evolve the schema without deleting rentals.db.
    """
    cursor = conn.cursor()

    if not column_exists(conn, "listing_detail", "posted_at"):
        cursor.execute(
            """
            ALTER TABLE listing_detail
            ADD COLUMN posted_at TEXT;
            """
        )
        print("Migration applied: added listing_detail.posted_at")

    conn.commit()


def create_tables() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS search_config (
            search_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            source TEXT NOT NULL,
            url TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS fetch_run (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL,
            records_found INTEGER DEFAULT 0,
            records_new INTEGER DEFAULT 0,
            error_message TEXT
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS listing (
            listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            source_listing_id TEXT NOT NULL,
            url TEXT NOT NULL,
            title TEXT,
            price INTEGER,
            neighborhood TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,

            UNIQUE(source, source_listing_id)
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS listing_observation (
            observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER NOT NULL,
            run_id INTEGER NOT NULL,
            search_id INTEGER NOT NULL,
            observed_at TEXT NOT NULL,
            observed_title TEXT,
            observed_price INTEGER,
            observed_neighborhood TEXT,

            FOREIGN KEY (listing_id) REFERENCES listing(listing_id),
            FOREIGN KEY (run_id) REFERENCES fetch_run(run_id),
            FOREIGN KEY (search_id) REFERENCES search_config(search_id)
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS listing_detail (
            listing_id INTEGER PRIMARY KEY,
            posted_at TEXT,
            description TEXT,
            bedrooms REAL,
            bathrooms REAL,
            sqft INTEGER,
            latitude REAL,
            longitude REAL,
            raw_html TEXT,
            fetched_at TEXT NOT NULL,
            fetch_status TEXT NOT NULL,
            error_message TEXT,

            FOREIGN KEY (listing_id) REFERENCES listing(listing_id)
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS listing_score (
            score_id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER NOT NULL,
            scored_at TEXT NOT NULL,
            scoring_version TEXT NOT NULL,

            eligibility_status TEXT NOT NULL,
            eligibility_reasons TEXT,

            scam_risk_status TEXT NOT NULL,
            scam_risk_reasons TEXT,

            owner_signal_score INTEGER NOT NULL,
            owner_signal_reasons TEXT,

            human_signal_score INTEGER NOT NULL,
            human_signal_reasons TEXT,

            property_type TEXT NOT NULL,
            property_type_score INTEGER NOT NULL,
            property_type_reasons TEXT,

            fit_score INTEGER NOT NULL,
            fit_reasons TEXT,

            grey_cells_score INTEGER,

            FOREIGN KEY (listing_id) REFERENCES listing(listing_id)
        );
        """
    )

    conn.commit()
    run_migrations(conn)
    conn.close()


def seed_search_config() -> None:
    now = get_utc_now()

    starter_search = {
        "name": "98105 3mi starter",
        "source": "craigslist",
        "url": "https://seattle.craigslist.org/search/apa?sort=date&max_price=3500&min_price=1500&postal=98105&search_distance=3",
    }

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT search_id FROM search_config LIMIT 1;")

    existing = cursor.fetchone()

    if existing:
        print("Starter search already exists.")
    else:
        cursor.execute(
            """
            INSERT INTO search_config (
                name,
                source,
                url,
                active,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                starter_search["name"],
                starter_search["source"],
                starter_search["url"],
                1,
                now,
                now,
            ),
        )

        print("Starter search inserted.")

    conn.commit()
    conn.close()


def initialize_database() -> None:
    create_tables()
    seed_search_config()
    print(f"Database initialized at: {DB_PATH}")


if __name__ == "__main__":
    initialize_database()
