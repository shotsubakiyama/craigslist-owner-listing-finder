import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path

from db import get_connection


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "data"


def get_output_path() -> Path:
    today = datetime.now().strftime("%Y%m%d")
    return OUTPUT_DIR / f"shortlist_{today}.html"


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


def format_price(price) -> str:
    if price is None:
        return "unknown"
    return f"${price:,}"


def format_date(value: str | None) -> str:
    if not value:
        return "unknown"

    return value[:10]


def days_since(value: str | None) -> int:
    if not value:
        return 99999

    try:
        parsed = datetime.fromisoformat(value)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        delta = now - parsed.astimezone(timezone.utc)

        return max(0, delta.days)

    except ValueError:
        return 99999


def clean_text(value: str | None) -> str:
    if not value:
        return ""

    return " ".join(value.split())


def score_class(score: int | None) -> str:
    if score is None:
        return "score-muted"

    if score >= 85:
        return "score-great"

    if score >= 70:
        return "score-good"

    if score >= 55:
        return "score-ok"

    return "score-low"


def get_shortlist_rows(limit: int, min_score: int) -> list[tuple]:
    conn = get_connection()
    cursor = conn.cursor()

    candidate_limit = max(limit * 8, 100)

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
            l.first_seen,
            l.last_seen,
            d.posted_at,
            s.scoring_version,
            s.grey_cells_score,
            s.owner_signal_score,
            s.owner_signal_reasons,
            s.human_signal_score,
            s.human_signal_reasons,
            s.fit_score,
            s.fit_reasons,
            s.property_type,
            d.description
        FROM latest_score s
        JOIN listing l
            ON s.listing_id = l.listing_id
        JOIN listing_detail d
            ON l.listing_id = d.listing_id
        WHERE s.grey_cells_score IS NOT NULL
          AND s.grey_cells_score >= ?
        ORDER BY s.grey_cells_score DESC
        LIMIT ?;
        """,
        (min_score, candidate_limit),
    )

    rows = cursor.fetchall()
    conn.close()

    return dedupe_rows(rows, limit)


def normalize_for_fingerprint(value: str | None) -> str:
    if not value:
        return ""

    value = value.lower()
    keep_chars = []

    for char in value:
        if char.isalnum() or char.isspace():
            keep_chars.append(char)
        else:
            keep_chars.append(" ")

    normalized = "".join(keep_chars)
    normalized = " ".join(normalized.split())
    return normalized.strip()


def get_duplicate_fingerprint(row: tuple) -> str:
    item = unpack_row(row)

    normalized_title = normalize_for_fingerprint(item["title"])
    normalized_neighborhood = normalize_for_fingerprint(item["neighborhood"])
    normalized_description_start = normalize_for_fingerprint(item["description"])[:120]

    return "|".join(
        [
            normalized_title,
            str(item["price"] or ""),
            normalized_neighborhood,
            normalized_description_start,
        ]
    )


def dedupe_rows(rows: list[tuple], limit: int) -> list[tuple]:
    deduped = []
    seen = set()

    for row in rows:
        fingerprint = get_duplicate_fingerprint(row)

        if fingerprint in seen:
            continue

        seen.add(fingerprint)
        deduped.append(row)

        if len(deduped) >= limit:
            break

    return deduped


def render_reasons(title: str, reasons_json: str | None, max_reasons: int = 6) -> str:
    reasons = parse_json_list(reasons_json)

    if not reasons:
        return ""

    items = "\n".join(
        f"<li>{html.escape(reason)}</li>"
        for reason in reasons[:max_reasons]
    )

    return f"""
    <div class="reason-block">
      <div class="reason-title">{html.escape(title)}</div>
      <ul>
        {items}
      </ul>
    </div>
    """


def unpack_row(row: tuple) -> dict:
    (
        listing_id,
        source_listing_id,
        title,
        price,
        neighborhood,
        url,
        first_seen,
        last_seen,
        posted_at,
        scoring_version,
        grey_cells_score,
        owner_signal_score,
        owner_signal_reasons,
        human_signal_score,
        human_signal_reasons,
        fit_score,
        fit_reasons,
        property_type,
        description,
    ) = row

    return {
        "listing_id": listing_id,
        "source_listing_id": source_listing_id,
        "title": title,
        "price": price,
        "neighborhood": neighborhood,
        "url": url,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "posted_at": posted_at,
        "days_since_posted": days_since(posted_at),
        "scoring_version": scoring_version,
        "grey_cells_score": grey_cells_score,
        "owner_signal_score": owner_signal_score,
        "owner_signal_reasons": owner_signal_reasons,
        "human_signal_score": human_signal_score,
        "human_signal_reasons": human_signal_reasons,
        "fit_score": fit_score,
        "fit_reasons": fit_reasons,
        "property_type": property_type,
        "description": description,
    }


def render_summary_tile(rank: int, row: tuple) -> str:
    item = unpack_row(row)

    anchor = f"listing-{item['listing_id']}"
    title = html.escape(item["title"] or "Untitled listing")
    neighborhood = html.escape(item["neighborhood"] or "unknown")
    property_type = html.escape(item["property_type"] or "unknown")
    url = html.escape(item["url"] or "")
    posted_at = html.escape(format_date(item["posted_at"]))
    days_since_posted = item["days_since_posted"]

    return f"""
    <section class="tile" data-days-since-posted="{days_since_posted}">
      <div class="tile-top">
        <div class="tile-rank">#{rank}</div>
        <div class="tile-score {score_class(item['grey_cells_score'])}">
          {item['grey_cells_score']}
        </div>
      </div>

      <h3>{title}</h3>

      <div class="tile-meta">
        <span>{format_price(item["price"])}</span>
        <span>{neighborhood}</span>
        <span>{property_type}</span>
        <span>Posted {posted_at}</span>
      </div>

      <div class="tile-signals">
        <span>Owner {item["owner_signal_score"]}</span>
        <span>Human {item["human_signal_score"]}</span>
        <span>Fit {item["fit_score"]}</span>
      </div>

      <div class="tile-actions">
        <a href="{url}" target="_blank" rel="noopener noreferrer">Open</a>
        <a href="#{anchor}">Details</a>
      </div>
    </section>
    """


def render_summary_tiles(rows: list[tuple]) -> str:
    tiles = "\n".join(
        render_summary_tile(rank, row)
        for rank, row in enumerate(rows, start=1)
    )

    return f"""
    <section class="summary-section">
      <div class="section-heading">
        <h2>Top Shortlist</h2>
        <p>Quick view. Use “Open” for Craigslist or “Details” to jump lower on this page.</p>
      </div>

      <div class="filter-bar">
        <button class="filter-button active" data-filter="all">All</button>
        <button class="filter-button" data-filter="0">Posted today</button>
        <button class="filter-button" data-filter="5">Posted last 5 days</button>
        <button class="filter-button" data-filter="20">Posted last 20 days</button>
      </div>

      <div class="filter-note" id="filter-note">
        Showing all shortlist tiles.
      </div>

      <div class="tile-grid" id="tile-grid">
        {tiles}
      </div>
    </section>
    """


def render_listing_card(rank: int, row: tuple) -> str:
    item = unpack_row(row)

    description_preview = clean_text(item["description"])
    if len(description_preview) > 1100:
        description_preview = description_preview[:1100].rstrip() + "..."

    owner_reasons_html = render_reasons("Owner Signal reasons", item["owner_signal_reasons"])
    human_reasons_html = render_reasons("Human Signal reasons", item["human_signal_reasons"])
    fit_reasons_html = render_reasons("Fit reasons", item["fit_reasons"])

    listing_title = html.escape(item["title"] or "Untitled listing")
    listing_url = html.escape(item["url"] or "")
    neighborhood_text = html.escape(item["neighborhood"] or "unknown")
    property_type_text = html.escape(item["property_type"] or "unknown")
    posted_at_text = html.escape(format_date(item["posted_at"]))
    first_seen_text = html.escape(format_date(item["first_seen"]))
    last_seen_text = html.escape(format_date(item["last_seen"]))
    description_html = html.escape(description_preview)
    anchor = f"listing-{item['listing_id']}"

    return f"""
    <article class="card" id="{anchor}" data-days-since-posted="{item['days_since_posted']}">
      <div class="card-header">
        <div>
          <div class="rank">#{rank}</div>
          <h2>{listing_title}</h2>
          <div class="meta">
            <span>{format_price(item["price"])}</span>
            <span>{neighborhood_text}</span>
            <span>{property_type_text}</span>
            <span>Posted {posted_at_text}</span>
            <span>First seen {first_seen_text}</span>
            <span>Last seen {last_seen_text}</span>
          </div>
        </div>

        <div class="score-box {score_class(item["grey_cells_score"])}">
          <div class="score-label">Grey Cells</div>
          <div class="score-value">{item["grey_cells_score"]}</div>
        </div>
      </div>

      <div class="signals">
        <div class="signal">
          <div class="signal-label">Owner</div>
          <div class="signal-value">{item["owner_signal_score"]}</div>
        </div>
        <div class="signal">
          <div class="signal-label">Human</div>
          <div class="signal-value">{item["human_signal_score"]}</div>
        </div>
        <div class="signal">
          <div class="signal-label">Fit</div>
          <div class="signal-value">{item["fit_score"]}</div>
        </div>
      </div>

      <div class="actions">
        <a href="{listing_url}" target="_blank" rel="noopener noreferrer">Open Craigslist listing</a>
        <a href="#top">Back to top</a>
        <span>Internal ID: {item["listing_id"]}</span>
        <span>CL ID: {html.escape(str(item["source_listing_id"]))}</span>
        <span>{html.escape(item["scoring_version"] or "")}</span>
      </div>

      <p class="description">{description_html}</p>

      <details>
        <summary>Why this ranked here</summary>
        <div class="reason-grid">
          {owner_reasons_html}
          {human_reasons_html}
          {fit_reasons_html}
        </div>
      </details>
    </article>
    """


def render_html(rows: list[tuple], output_path: Path, min_score: int) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    summary_tiles = render_summary_tiles(rows)

    detail_cards = "\n".join(
        render_listing_card(rank, row)
        for rank, row in enumerate(rows, start=1)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Grey Cells Shortlist</title>
  <style>
    :root {{
      --bg: #f6f4ef;
      --card: #ffffff;
      --text: #222222;
      --muted: #666666;
      --border: #ded8ce;
      --accent: #2f4858;
      --good: #3f6f5e;
      --ok: #8a6d3b;
      --low: #8a3b3b;
      --soft: #fbfaf7;
    }}

    html {{
      scroll-behavior: smooth;
    }}

    body {{
      margin: 0;
      padding: 32px;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
      line-height: 1.45;
    }}

    .page {{
      max-width: 1180px;
      margin: 0 auto;
    }}

    .topbar {{
      margin-bottom: 24px;
    }}

    h1 {{
      margin: 0;
      font-size: 34px;
      letter-spacing: -0.03em;
    }}

    .subtitle {{
      color: var(--muted);
      margin-top: 6px;
    }}

    .summary-section {{
      margin-bottom: 32px;
    }}

    .section-heading {{
      margin: 18px 0 14px 0;
    }}

    .section-heading h2 {{
      margin: 0;
      font-size: 24px;
    }}

    .section-heading p {{
      margin: 4px 0 0 0;
      color: var(--muted);
    }}

    .filter-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 14px 0 8px 0;
    }}

    .filter-button {{
      border: 1px solid var(--border);
      background: white;
      color: var(--accent);
      border-radius: 999px;
      padding: 8px 12px;
      font-weight: bold;
      cursor: pointer;
    }}

    .filter-button:hover {{
      background: #f0eee8;
    }}

    .filter-button.active {{
      background: var(--accent);
      color: white;
      border-color: var(--accent);
    }}

    .filter-note {{
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 12px;
    }}

    .tile-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
      gap: 12px;
    }}

    .tile {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.035);
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-height: 225px;
    }}

    .tile.hidden-by-filter {{
      display: none;
    }}

    .card.hidden-by-filter {{
      display: none;
    }}

    .tile-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}

    .tile-rank {{
      color: var(--muted);
      font-size: 14px;
      font-weight: bold;
    }}

    .tile-score {{
      color: white;
      border-radius: 999px;
      font-weight: bold;
      font-size: 18px;
      min-width: 44px;
      text-align: center;
      padding: 5px 8px;
    }}

    .tile h3 {{
      margin: 0;
      font-size: 16px;
      line-height: 1.25;
      min-height: 40px;
    }}

    .tile-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      font-size: 12px;
      color: var(--muted);
    }}

    .tile-meta span {{
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 2px 7px;
      background: #fafafa;
    }}

    .tile-signals {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 6px;
      font-size: 12px;
    }}

    .tile-signals span {{
      background: var(--soft);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 5px;
      text-align: center;
      white-space: nowrap;
    }}

    .tile-actions {{
      margin-top: auto;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}

    .tile-actions a {{
      background: var(--accent);
      color: white;
      text-decoration: none;
      padding: 7px 10px;
      border-radius: 8px;
      font-weight: bold;
      font-size: 13px;
    }}

    .tile-actions a:nth-child(2) {{
      background: #6d7478;
    }}

    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 22px;
      margin-bottom: 18px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
      scroll-margin-top: 20px;
    }}

    .card-header {{
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: flex-start;
    }}

    .rank {{
      color: var(--muted);
      font-size: 14px;
      margin-bottom: 4px;
    }}

    h2 {{
      margin: 0 0 8px 0;
      font-size: 22px;
      line-height: 1.2;
    }}

    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      color: var(--muted);
      font-size: 14px;
    }}

    .meta span {{
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 3px 9px;
      background: #fafafa;
    }}

    .score-box {{
      min-width: 96px;
      border-radius: 12px;
      padding: 10px 12px;
      text-align: center;
      color: white;
    }}

    .score-great {{
      background: var(--good);
    }}

    .score-good {{
      background: var(--accent);
    }}

    .score-ok {{
      background: var(--ok);
    }}

    .score-low {{
      background: var(--low);
    }}

    .score-muted {{
      background: #777;
    }}

    .score-label {{
      font-size: 12px;
      opacity: 0.9;
    }}

    .score-value {{
      font-size: 30px;
      font-weight: bold;
      line-height: 1;
      margin-top: 3px;
    }}

    .signals {{
      display: flex;
      gap: 10px;
      margin: 18px 0 12px 0;
      flex-wrap: wrap;
    }}

    .signal {{
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 8px 12px;
      background: #fafafa;
      min-width: 80px;
    }}

    .signal-label {{
      font-size: 12px;
      color: var(--muted);
    }}

    .signal-value {{
      font-size: 20px;
      font-weight: bold;
    }}

    .actions {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 14px;
    }}

    .actions a {{
      background: var(--accent);
      color: white;
      text-decoration: none;
      padding: 7px 11px;
      border-radius: 8px;
      font-weight: bold;
    }}

    .actions a:nth-child(2) {{
      background: #6d7478;
    }}

    .actions a:hover,
    .tile-actions a:hover {{
      opacity: 0.9;
    }}

    .description {{
      white-space: pre-wrap;
      background: var(--soft);
      border-left: 4px solid var(--border);
      padding: 12px 14px;
      border-radius: 8px;
      margin: 14px 0;
    }}

    details {{
      margin-top: 10px;
    }}

    summary {{
      cursor: pointer;
      color: var(--accent);
      font-weight: bold;
    }}

    .reason-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 12px;
      margin-top: 12px;
    }}

    .reason-block {{
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px;
      background: #fafafa;
    }}

    .reason-title {{
      font-weight: bold;
      margin-bottom: 6px;
    }}

    ul {{
      margin: 0;
      padding-left: 20px;
    }}

    li {{
      margin-bottom: 4px;
    }}

    @media (max-width: 700px) {{
      body {{
        padding: 16px;
      }}

      .card-header {{
        flex-direction: column;
      }}

      .score-box {{
        width: 100%;
      }}

      .tile {{
        min-height: auto;
      }}
    }}
  </style>
</head>
<body>
  <main class="page" id="top">
    <header class="topbar">
      <h1>Grey Cells Shortlist</h1>
      <div class="subtitle">
        Generated {html.escape(generated_at)} · {len(rows)} deduped listings · min score {min_score} · {html.escape(str(output_path.name))}
      </div>
    </header>

    {summary_tiles}

    <section class="section-heading">
      <h2>Detailed Notes</h2>
      <p>Expanded listing descriptions and scoring reasons.</p>
    </section>

    {detail_cards}
  </main>

  <script>
    function applyFilter(filterValue) {{
      const maxDays = filterValue === "all" ? null : Number(filterValue);
      const tiles = Array.from(document.querySelectorAll(".tile"));
      const cards = Array.from(document.querySelectorAll(".card"));
      const buttons = Array.from(document.querySelectorAll(".filter-button"));
      const note = document.getElementById("filter-note");

      buttons.forEach((button) => {{
        button.classList.toggle("active", button.dataset.filter === filterValue);
      }});

      let visibleTiles = 0;
      let totalTiles = tiles.length;

      function shouldShow(element) {{
        if (maxDays === null) {{
          return true;
        }}

        const daysSince = Number(element.dataset.daysSincePosted || "99999");
        return daysSince <= maxDays;
      }}

      tiles.forEach((tile) => {{
        const show = shouldShow(tile);
        tile.classList.toggle("hidden-by-filter", !show);
        if (show) {{
          visibleTiles += 1;
        }}
      }});

      cards.forEach((card) => {{
        const show = shouldShow(card);
        card.classList.toggle("hidden-by-filter", !show);
      }});

      if (maxDays === null) {{
        note.textContent = `Showing all ${{totalTiles}} shortlist tiles.`;
      }} else if (maxDays === 0) {{
        note.textContent = `Showing ${{visibleTiles}} of ${{totalTiles}} shortlist tiles posted today.`;
      }} else {{
        note.textContent = `Showing ${{visibleTiles}} of ${{totalTiles}} shortlist tiles posted in the last ${{maxDays}} days.`;
      }}
    }}

    document.querySelectorAll(".filter-button").forEach((button) => {{
      button.addEventListener("click", () => {{
        applyFilter(button.dataset.filter);
      }});
    }});
  </script>
</body>
</html>
"""


def write_html_report(limit: int, min_score: int) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = get_output_path()

    rows = get_shortlist_rows(limit=limit, min_score=min_score)
    html_content = render_html(rows=rows, output_path=output_path, min_score=min_score)

    output_path.write_text(html_content, encoding="utf-8")

    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an HTML Grey Cells Shortlist report."
    )

    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=20,
        help="Number of deduped listings to include. Example: --limit 10",
    )

    parser.add_argument(
        "--min-score",
        type=int,
        default=0,
        help="Minimum Grey Cells score to include. Example: --min-score 65",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.limit <= 0:
        raise ValueError("Limit must be greater than 0.")

    if args.min_score < 0 or args.min_score > 100:
        raise ValueError("Min score must be between 0 and 100.")

    output_path = write_html_report(
        limit=args.limit,
        min_score=args.min_score,
    )

    print("Generated HTML Shortlist report:")
    print(output_path)


if __name__ == "__main__":
    main()