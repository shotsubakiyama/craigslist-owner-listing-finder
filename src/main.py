import argparse
import sys
import time
from collections.abc import Callable
from typing import Any

from db import initialize_database
from export_review_data import main as export_review_data
from generate_shortlist_html import write_html_report
from listing_fetcher import run_listing_fetcher
from scoring_engine import run_scoring_engine
from search_fetcher import run_search_fetcher
from shortlist import print_shortlist


DEFAULT_LISTING_PASSES = 5
DEFAULT_SHORTLIST_LIMIT = 20
DEFAULT_MIN_SCORE = 0


def run_stage(name: str, function: Callable[[], Any]) -> Any:
    """Run one pipeline stage and print its elapsed time."""
    print("\n" + "=" * 100)
    print(name)
    print("=" * 100)

    started_at = time.perf_counter()
    result = function()
    elapsed_seconds = time.perf_counter() - started_at

    print(f"\n{name} completed in {elapsed_seconds:.1f} seconds.")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Grey Cells rental-discovery pipeline."
    )

    parser.add_argument(
        "--listing-passes",
        type=int,
        default=DEFAULT_LISTING_PASSES,
        help=(
            "Number of ListingFetcher passes to run. "
            f"Default: {DEFAULT_LISTING_PASSES}"
        ),
    )

    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=DEFAULT_SHORTLIST_LIMIT,
        help=(
            "Number of deduplicated listings to include in the shortlist "
            f"and HTML report. Default: {DEFAULT_SHORTLIST_LIMIT}"
        ),
    )

    parser.add_argument(
        "--min-score",
        type=int,
        default=DEFAULT_MIN_SCORE,
        help=(
            "Minimum Grey Cells score for the HTML report. "
            f"Default: {DEFAULT_MIN_SCORE}"
        ),
    )

    parser.add_argument(
        "--skip-search",
        action="store_true",
        help="Skip SearchFetcher and use listings already stored locally.",
    )

    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="Skip creation of the CSV review export.",
    )

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.listing_passes <= 0:
        raise ValueError("--listing-passes must be greater than 0.")

    if args.limit <= 0:
        raise ValueError("--limit must be greater than 0.")

    if args.min_score < 0 or args.min_score > 100:
        raise ValueError("--min-score must be between 0 and 100.")


def run_pipeline(args: argparse.Namespace) -> None:
    pipeline_started_at = time.perf_counter()

    run_stage("1. Initialize database", initialize_database)

    if args.skip_search:
        print("\n2. SearchFetcher skipped.")
    else:
        run_stage("2. Fetch search results", run_search_fetcher)

    for pass_number in range(1, args.listing_passes + 1):
        run_stage(
            f"3. Fetch listing details — pass "
            f"{pass_number} of {args.listing_passes}",
            run_listing_fetcher,
        )

    run_stage("4. Score listings", run_scoring_engine)

    run_stage(
        "5. Print shortlist",
        lambda: print_shortlist(args.limit),
    )

    html_path = run_stage(
        "6. Generate HTML report",
        lambda: write_html_report(
            limit=args.limit,
            min_score=args.min_score,
        ),
    )

    if args.skip_export:
        print("\n7. CSV export skipped.")
    else:
        run_stage("7. Export review data", export_review_data)

    total_seconds = time.perf_counter() - pipeline_started_at

    print("\n" + "=" * 100)
    print("GREY CELLS PIPELINE COMPLETE")
    print("=" * 100)
    print(f"HTML report: {html_path}")
    print(f"Total runtime: {total_seconds:.1f} seconds.")


def main() -> int:
    try:
        args = parse_args()
        validate_args(args)
        run_pipeline(args)
        return 0

    except KeyboardInterrupt:
        print("\nPipeline stopped by user.")
        return 130

    except Exception as exc:
        print(f"\nPipeline failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
