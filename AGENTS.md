# Agent instructions — Craigslist Owner Listing Finder

## Mission
This is a local-first Python/SQLite pipeline for discovering and ranking Craigslist rentals that *appear* owner-managed and personally written. Its priorities are explainability, privacy, practical usefulness, and simplicity. Do not claim to verify landlord ownership.

## Code map
- `src/main.py`: CLI and pipeline orchestration.
- `src/search_fetcher.py`, `src/listing_fetcher.py`: listing retrieval.
- `src/db.py`: persistence.
- `src/scoring_engine.py`, `src/shortlist.py`: transparent ranking, filters, and deduplication.
- `src/generate_shortlist_html.py`: HTML shortlist.
- `src/market_pulse.py`, `src/update_market_pulse.py`: optional cached market indicators.
- `tests/test_market_pulse.py`: existing regression tests.

## Behavior and design
- Preserve an inspectable breakdown of Owner Signal, Human Signal, and Fit Score, with reasons a user can understand.
- Treat reposts and near-duplicate listings carefully, especially across multiple collection runs. Do not let small URL or title changes cause obvious repeats.
- Keep the shortlist clear, compact, and locally useful. Prefer reliable filters and explicit data quality over speculative machine learning.
- Maintain clear separation between network fetches, database updates, scoring, and report rendering.
- Keep the daily listing workflow separate from optional monthly market-data refresh. The HTML generator must read the cache rather than download market data.
- Label market-data source, observation date, geography, and limitations. Do not extrapolate Apartment List multifamily metrics to owner-managed Craigslist houses.

## Privacy and external data
- Do not commit live scraped listing text, precise addresses, contact details, local SQLite databases, generated personal reports, credentials, or private configuration.
- Use synthetic or redacted examples in public tests and documentation. Respect external-site access limits and terms.

## Change discipline
1. Read `README.md` and affected files. This repo overlaps with `grey-cells`, but it is a separate repository: do not assume code or fixes are automatically synchronized.
2. Keep edits small; preserve CLI compatibility unless explicitly changing it.
3. Run relevant tests, including `python -m unittest discover -s tests` when supported. Exercise a local no-search/limited run for pipeline changes, using safe fixtures rather than live data where possible.
4. For HTML changes, inspect the rendered output at desktop and mobile widths.
5. State what was actually run and whether changes were committed, deployed, or installed locally. Never claim a local scheduled task is active without verification.
