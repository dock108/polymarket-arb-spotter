#!/usr/bin/env python
"""
Market snapshot exporter for Polymarket historical data.

This script exports market tick data from the history store to CSV or JSONL
format for external analysis. Supports filtering by date range and markets.

Usage:
    python scripts/export_history.py [OPTIONS]

Options:
    --output FILE           Output file path (required)
    --format FORMAT         Output format: csv or jsonl (default: csv)
    --start DATE            Start date filter (ISO format, e.g., 2024-01-01)
    --end DATE              End date filter (ISO format, e.g., 2024-01-31)
    --markets ID1,ID2,...   Comma-separated list of market IDs to export
    --db-path PATH          Path to history database (default: data/market_history.db)

Examples:
    # Export all history to CSV
    python scripts/export_history.py --output history.csv

    # Export to JSONL format
    python scripts/export_history.py --output history.jsonl --format jsonl

    # Export with date range filter
    python scripts/export_history.py --output history.csv --start 2024-01-01 --end 2024-01-31

    # Export specific markets
    python scripts/export_history.py --output history.csv --markets market_1,market_2

    # Combine filters
    python scripts/export_history.py --output history.csv --start 2024-01-01 --markets market_1
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.history_store import get_ticks, get_market_ids  # noqa: E402
from app.core.logger import logger  # noqa: E402


# Maximum number of ticks to retrieve per market (can be very large for export)
MAX_TICKS_PER_MARKET = 10000000


def get_filtered_ticks(
    market_ids: Optional[List[str]] = None,
    start: Optional[Union[datetime, str]] = None,
    end: Optional[Union[datetime, str]] = None,
    db_path: str = "data/market_history.db",
) -> List[Dict[str, Any]]:
    """
    Get ticks filtered by markets and date range.

    Args:
        market_ids: List of market IDs to include. If None, includes all markets.
        start: Start of time range (inclusive). If None, no lower bound.
        end: End of time range (inclusive). If None, no upper bound.
        db_path: Path to the SQLite database file

    Returns:
        List of tick dictionaries ordered by timestamp ascending.
    """
    # Get market IDs to query
    if market_ids is None:
        market_ids = get_market_ids(db_path)

    if not market_ids:
        return []

    # Collect ticks from all markets
    all_ticks = []
    for market_id in market_ids:
        ticks = get_ticks(
            market_id=market_id,
            start=start,
            end=end,
            limit=MAX_TICKS_PER_MARKET,
            db_path=db_path,
        )
        all_ticks.extend(ticks)

    # Sort by timestamp (filter out any records with missing timestamps)
    all_ticks = [t for t in all_ticks if t.get("timestamp")]
    all_ticks.sort(key=lambda x: x["timestamp"])

    return all_ticks


def export_to_csv(
    ticks: List[Dict[str, Any]],
    output_path: str,
) -> int:
    """
    Export ticks to CSV format.

    Args:
        ticks: List of tick dictionaries to export
        output_path: Path to the output CSV file

    Returns:
        Number of rows exported
    """
    if not ticks:
        logger.warning("No ticks to export")
        return 0

    # Define CSV columns
    fieldnames = [
        "id",
        "market_id",
        "timestamp",
        "yes_price",
        "no_price",
        "volume",
        "depth_summary",
    ]

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for tick in ticks:
            # Convert depth_summary dict to JSON string for CSV
            row = tick.copy()
            if row.get("depth_summary") is not None:
                if isinstance(row["depth_summary"], dict):
                    row["depth_summary"] = json.dumps(row["depth_summary"])
            writer.writerow(row)

    logger.info(f"Exported {len(ticks)} ticks to CSV: {output_path}")
    return len(ticks)


def export_to_jsonl(
    ticks: List[Dict[str, Any]],
    output_path: str,
) -> int:
    """
    Export ticks to JSONL (JSON Lines) format.

    Each line in the output file is a valid JSON object.

    Args:
        ticks: List of tick dictionaries to export
        output_path: Path to the output JSONL file

    Returns:
        Number of rows exported
    """
    if not ticks:
        logger.warning("No ticks to export")
        return 0

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as jsonlfile:
        for tick in ticks:
            jsonlfile.write(json.dumps(tick) + "\n")

    logger.info(f"Exported {len(ticks)} ticks to JSONL: {output_path}")
    return len(ticks)


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse a date string to datetime object.

    Supports ISO format dates (YYYY-MM-DD) and datetimes (YYYY-MM-DDTHH:MM:SS).

    Args:
        date_str: Date string in ISO format, or None

    Returns:
        datetime object or None if input is None
    """
    if date_str is None:
        return None

    try:
        # Try datetime format first
        if "T" in date_str:
            return datetime.fromisoformat(date_str)
        # Try date-only format
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(
            f"Invalid date format: {date_str}. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"
        ) from e


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Export market history data to CSV or JSONL format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export all history to CSV
  python scripts/export_history.py --output history.csv

  # Export to JSONL format
  python scripts/export_history.py --output history.jsonl --format jsonl

  # Export with date range filter
  python scripts/export_history.py --output history.csv --start 2024-01-01 --end 2024-01-31

  # Export specific markets
  python scripts/export_history.py --output history.csv --markets market_1,market_2

  # Combine filters
  python scripts/export_history.py --output history.csv --start 2024-01-01 --markets market_1
        """,
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        required=True,
        help="Output file path (required)",
    )

    parser.add_argument(
        "--format",
        "-f",
        type=str,
        choices=["csv", "jsonl"],
        default="csv",
        help="Output format: csv or jsonl (default: csv)",
    )

    parser.add_argument(
        "--start",
        "-s",
        type=str,
        default=None,
        help="Start date filter (ISO format, e.g., 2024-01-01)",
    )

    parser.add_argument(
        "--end",
        "-e",
        type=str,
        default=None,
        help="End date filter (ISO format, e.g., 2024-01-31)",
    )

    parser.add_argument(
        "--markets",
        "-m",
        type=str,
        default=None,
        help="Comma-separated list of market IDs to export",
    )

    parser.add_argument(
        "--db-path",
        type=str,
        default="data/market_history.db",
        help="Path to history database (default: data/market_history.db)",
    )

    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the export script.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    args = parse_args()

    # Parse date filters
    try:
        start_date = parse_date(args.start)
        end_date = parse_date(args.end)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Parse market IDs
    market_ids = None
    if args.markets:
        market_ids = [m.strip() for m in args.markets.split(",") if m.strip()]

    # Log export parameters
    print("Exporting market history data...")
    print(f"  Output: {args.output}")
    print(f"  Format: {args.format}")
    print(f"  Database: {args.db_path}")
    if start_date:
        print(f"  Start date: {start_date.isoformat()}")
    if end_date:
        print(f"  End date: {end_date.isoformat()}")
    if market_ids:
        print(f"  Markets: {', '.join(market_ids)}")

    # Get filtered ticks
    ticks = get_filtered_ticks(
        market_ids=market_ids,
        start=start_date,
        end=end_date,
        db_path=args.db_path,
    )

    if not ticks:
        print("No data found matching the specified filters.")
        return 0

    print(f"  Found {len(ticks)} ticks to export")

    # Export based on format
    if args.format == "csv":
        count = export_to_csv(ticks, args.output)
    else:
        count = export_to_jsonl(ticks, args.output)

    print(f"Successfully exported {count} ticks to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
