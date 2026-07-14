"""Convert Binance public trades CSV files into QuantDesk exporter input.

Binance spot trade files from data.binance.vision use these columns, usually
without a header row:

trade_id, price, qty, quote_qty, time_ms, is_buyer_maker, is_best_match

QuantDesk's CSV exporter expects:

timestamp, price, quantity, side

Usage:
    python research/convert_binance_trades.py raw.csv trades_ready.csv
    python research/convert_binance_trades.py raw.csv trades_ready.csv --limit 10000
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    args = parse_args()
    converted = convert(Path(args.src), Path(args.dst), limit=args.limit)
    print(f"Converted {converted} Binance trades -> {args.dst}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Binance trades CSV to QuantDesk tick CSV."
    )
    parser.add_argument("src", help="Raw Binance trades CSV.")
    parser.add_argument(
        "dst", help="Output CSV with timestamp,price,quantity,side columns."
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Optional max rows to convert."
    )
    return parser.parse_args()


def convert(src_path: Path, dst_path: Path, *, limit: int | None = None) -> int:
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with (
        src_path.open("r", newline="", encoding="utf-8-sig") as src,
        dst_path.open("w", newline="", encoding="utf-8") as dst,
    ):
        reader = csv.reader(src)
        writer = csv.writer(dst)
        writer.writerow(["timestamp", "price", "quantity", "side"])

        for row in reader:
            if not is_trade_row(row):
                continue
            _, price, quantity, _, time_ms, is_buyer_maker, *_ = row
            side = "SELL" if is_buyer_maker.strip().lower() == "true" else "BUY"
            timestamp = epoch_to_iso8601(int(time_ms))
            writer.writerow([timestamp, price, quantity, side])
            count += 1
            if limit is not None and count >= limit:
                break

    return count


def is_trade_row(row: list[str]) -> bool:
    return len(row) >= 7 and row[0].strip().lstrip("-").isdigit()


def epoch_to_iso8601(value: int) -> str:
    """Convert Binance epoch timestamps in seconds/ms/us/ns to UTC ISO-8601."""
    if value > 10_000_000_000_000_000:
        seconds = value / 1_000_000_000
    elif value > 10_000_000_000_000:
        seconds = value / 1_000_000
    elif value > 10_000_000_000:
        seconds = value / 1_000
    else:
        seconds = value
    return (
        datetime.fromtimestamp(seconds, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


if __name__ == "__main__":
    main()
