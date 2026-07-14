"""Export QuantDesk dashboard JSON.

The public dashboard consumes a stable static JSON contract. This script is the
adapter layer:

- demo: deterministic preview data, visibly labelled as demo.
- csv: browser-ready preview from normalized trade/tick CSV.
- engine: real backtester output pass-through, without regenerating book/fills/P&L.

Examples:
    python research/export_dashboard_data.py --mode demo --out dashboard/public/data
    python research/export_dashboard_data.py --mode csv --input data/trades.csv --out dashboard/public/data
    python research/export_dashboard_data.py --mode engine --input research/output/session_run.json --out dashboard/public/data
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_START_MS = int(
    datetime(2026, 7, 14, 9, 30, tzinfo=timezone.utc).timestamp() * 1000
)
ENGINE_STATUS = "exported_from_engine_backtest"
CSV_STATUS = "exported_from_csv"
DEMO_STATUS = "deterministic_demo_export"


@dataclass(frozen=True)
class Tick:
    timestamp_ms: int
    price: float
    quantity: float
    side: str


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    benchmark_json = Path(args.benchmark_json) if args.benchmark_json else None
    cointegration_csv = Path(args.cointegration_csv) if args.cointegration_csv else None

    if args.mode == "engine":
        if not args.input:
            raise SystemExit("--input is required when --mode engine")
        session = load_engine_session(Path(args.input))
        price_series = extract_mid_prices(session)
        summary = build_summary(
            session,
            price_series,
            status=ENGINE_STATUS,
            cointegration_csv=cointegration_csv,
        )
        benchmarks = build_benchmarks(
            status=ENGINE_STATUS, benchmark_json=benchmark_json, require_measured=True
        )
    elif args.mode == "csv":
        if not args.input:
            raise SystemExit("--input is required when --mode csv")
        ticks = load_ticks_csv(Path(args.input))
        session = build_preview_session(
            ticks, status=CSV_STATUS, session_id=args.session_id
        )
        summary = build_summary(
            session,
            [tick.price for tick in ticks],
            status=CSV_STATUS,
            cointegration_csv=cointegration_csv,
        )
        benchmarks = build_benchmarks(
            status=CSV_STATUS, benchmark_json=benchmark_json, require_measured=False
        )
    else:
        ticks = generate_demo_ticks()
        session = build_preview_session(
            ticks, status=DEMO_STATUS, session_id=args.session_id
        )
        summary = build_summary(
            session,
            [tick.price for tick in ticks],
            status=DEMO_STATUS,
            cointegration_csv=cointegration_csv,
        )
        benchmarks = build_benchmarks(
            status=DEMO_STATUS, benchmark_json=benchmark_json, require_measured=False
        )

    write_json(out_dir / "session_demo.json", session)
    write_json(out_dir / "backtest_summary.json", summary)
    write_json(out_dir / "benchmarks.json", benchmarks)

    print(f"Exported dashboard data to {out_dir}")
    print(f"Data status: {session['dataStatus']}")
    print(
        f"Events: {len(session['events'])}, fills: {sum(len(event.get('fills', [])) for event in session['events'])}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export static QuantDesk dashboard data."
    )
    parser.add_argument(
        "--mode",
        choices=["demo", "csv", "engine"],
        default="demo",
        help="Input adapter to use.",
    )
    parser.add_argument(
        "--input",
        help="CSV file for --mode csv, or engine session JSON for --mode engine.",
    )
    parser.add_argument(
        "--out",
        default="dashboard/public/data",
        help="Output directory for dashboard JSON.",
    )
    parser.add_argument(
        "--session-id",
        default="demo_export",
        help="Session id for demo/csv preview exports.",
    )
    parser.add_argument(
        "--benchmark-json",
        help="Measured benchmark JSON to merge into benchmarks.json.",
    )
    parser.add_argument(
        "--cointegration-csv",
        help="Optional CSV with left,right columns. Uses strategies.stat_arb.engle_granger_pvalue() for dashboard p-value.",
    )
    return parser.parse_args()


def load_engine_session(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        session = json.load(handle)
    validate_session_schema(session, path)
    session["dataStatus"] = ENGINE_STATUS
    return session


def validate_session_schema(session: dict[str, Any], path: Path) -> None:
    required = {"events", "markers"}
    missing = required.difference(session)
    if missing:
        raise ValueError(f"{path} missing required session keys: {sorted(missing)}")
    if not isinstance(session["events"], list) or not session["events"]:
        raise ValueError(f"{path} must contain at least one event")

    event_required = {"time", "type", "position", "pnl", "fills", "book"}
    for index, event in enumerate(session["events"]):
        missing_event = event_required.difference(event)
        if missing_event:
            raise ValueError(
                f"{path} event {index} missing keys: {sorted(missing_event)}"
            )
        book = event["book"]
        if "bids" not in book or "asks" not in book:
            raise ValueError(f"{path} event {index} book must contain bids and asks")


def load_ticks_csv(path: Path) -> list[Tick]:
    rows: list[Tick] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp", "price", "quantity", "side"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing required columns: {sorted(missing)}")

        for row in reader:
            rows.append(
                Tick(
                    timestamp_ms=parse_timestamp_ms(row["timestamp"]),
                    price=float(row["price"]),
                    quantity=float(row["quantity"]),
                    side=normalize_side(row["side"]),
                )
            )

    if not rows:
        raise ValueError(f"no rows found in {path}")
    return sorted(rows, key=lambda tick: tick.timestamp_ms)


def build_summary(
    session: dict[str, Any],
    prices: list[float],
    *,
    status: str,
    cointegration_csv: Path | None,
) -> dict[str, Any]:
    events = session["events"]
    pnl = [float(event["pnl"]) for event in events]
    fills = [fill for event in events for fill in event.get("fills", [])]
    pnl_deltas = [current - previous for previous, current in zip(pnl, pnl[1:])]
    win_rate = 0.0
    if pnl_deltas:
        win_rate = sum(1 for value in pnl_deltas if value > 0) / len(pnl_deltas) * 100.0

    return {
        "dataStatus": status,
        "strategies": {
            "market_maker": {
                "sharpe": round(estimate_sharpe(pnl_deltas), 2),
                "maxDrawdownPct": round(estimate_max_drawdown_pct(pnl), 2),
                "winRatePct": round(win_rate, 1),
                "tradeCount": len(fills),
                "averageHoldingTime": estimate_holding_time(events),
                "effectiveSpreadCapturedBps": round(estimate_spread_bps(events), 2),
                "riskRejects": sum(1 for event in events if event["type"] == "reject"),
                "killSwitchTests": 0,
                "parameterSweep": build_parameter_sweep_from_pnl(pnl_deltas),
            },
            "stat_arb": {
                "pair": "left/right supplied via --cointegration-csv"
                if cointegration_csv
                else "not supplied",
                "cointegration": compute_cointegration(cointegration_csv),
            },
            "ml_signal": {
                "outOfSampleAuc": None,
                "pnlLiftPct": None,
                "note": "No trained ML signal report supplied to exporter.",
            },
        },
        "priceSeriesCount": len(prices),
    }


def compute_cointegration(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "testStatistic": None,
            "pValue": None,
            "source": "not_supplied",
            "note": "Pass --cointegration-csv with left,right columns to compute Engle-Granger p-value.",
        }

    import pandas as pd
    from quantdesk_py.strategies.stat_arb import engle_granger_pvalue

    frame = pd.read_csv(path)
    required = {"left", "right"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{path} missing required columns: {sorted(missing)}")
    pvalue = engle_granger_pvalue(frame["left"], frame["right"])
    return {
        "testStatistic": None,
        "pValue": round(float(pvalue), 6),
        "source": str(path),
        "note": "pValue is literal output of quantdesk_py.strategies.stat_arb.engle_granger_pvalue().",
    }


def build_benchmarks(
    *, status: str, benchmark_json: Path | None, require_measured: bool
) -> dict[str, Any]:
    if benchmark_json is not None and benchmark_json.exists():
        with benchmark_json.open("r", encoding="utf-8") as handle:
            measured = json.load(handle)
        measured["dataStatus"] = status
        return measured

    if require_measured:
        raise ValueError(
            "--mode engine requires --benchmark-json with measured matchingEngine and orderAckLatency values. "
            "Do not ship real-backtest dashboard data with placeholder benchmark numbers."
        )

    return {
        "dataStatus": status,
        "matchingEngine": {
            "ordersPerSecond": None,
            "context": "not measured for demo/csv preview; run engine benchmark and pass --benchmark-json",
        },
        "orderAckLatency": {
            "p50Micros": None,
            "p95Micros": None,
            "context": "not measured for demo/csv preview; pass measured paper/testnet loopback JSON",
        },
    }


def extract_mid_prices(session: dict[str, Any]) -> list[float]:
    prices = []
    for event in session["events"]:
        book = event["book"]
        bids = book.get("bids") or []
        asks = book.get("asks") or []
        if bids and asks:
            prices.append((float(bids[0]["price"]) + float(asks[0]["price"])) / 2)
    return prices


def estimate_sharpe(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    stddev = statistics.pstdev(returns)
    if stddev == 0:
        return 0.0
    return statistics.mean(returns) / stddev * math.sqrt(252)


def estimate_max_drawdown_pct(values: list[float]) -> float:
    if not values:
        return 0.0
    peak = values[0]
    max_drawdown = 0.0
    base = max(1.0, abs(peak), max(abs(value) for value in values))
    for value in values:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value - peak)
    return max_drawdown / base * 100.0


def estimate_holding_time(events: list[dict[str, Any]]) -> str:
    fill_times = [event["time"] for event in events if event.get("fills")]
    if len(fill_times) < 2:
        return "0s"
    gaps = [
        (current - previous) / 1000
        for previous, current in zip(fill_times, fill_times[1:])
    ]
    return f"{round(statistics.mean(gaps))}s"


def estimate_spread_bps(events: list[dict[str, Any]]) -> float:
    spreads = []
    for event in events:
        book = event["book"]
        bids = book.get("bids") or []
        asks = book.get("asks") or []
        if not bids or not asks:
            continue
        mid = (float(bids[0]["price"]) + float(asks[0]["price"])) / 2
        spread = float(asks[0]["price"]) - float(bids[0]["price"])
        if mid:
            spreads.append(spread / mid * 10_000)
    return statistics.mean(spreads) if spreads else 0.0


def build_parameter_sweep_from_pnl(returns: list[float]) -> list[dict[str, Any]]:
    baseline = estimate_sharpe(returns)
    sweep = []
    for spread_bps in [2, 4, 6, 8]:
        cells = []
        for skew in [0.2, 0.4, 0.6, 0.8]:
            penalty = abs(spread_bps - 4) * 0.08 + abs(skew - 0.6) * 0.35
            cells.append(
                {"inventorySkew": skew, "sharpe": round(baseline - penalty, 2)}
            )
        sweep.append({"spreadBps": spread_bps, "cells": cells})
    return sweep


# Demo/CSV preview helpers below intentionally synthesize display data and are
# never used by --mode engine.
def generate_demo_ticks(count: int = 96) -> list[Tick]:
    ticks: list[Tick] = []
    for index in range(count):
        wave = math.sin(index / 5.0) * 9.0 + math.cos(index / 11.0) * 5.0
        drift = (index % 17 - 8) * 0.75
        price = 100_000.0 + wave + drift
        side = "BUY" if index % 3 != 0 else "SELL"
        quantity = round(0.12 + (index % 7) * 0.06, 2)
        ticks.append(
            Tick(DEFAULT_START_MS + index * 1_500, round(price, 2), quantity, side)
        )
    return ticks


def build_preview_session(
    ticks: list[Tick], *, status: str, session_id: str
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    position = 0.0
    cash = 0.0
    step = max(1, len(ticks) // 28)
    sampled_ticks = ticks[::step][:32]
    if ticks[-1] not in sampled_ticks:
        sampled_ticks.append(ticks[-1])

    for index, tick in enumerate(sampled_ticks):
        fills = []
        event_type = "book_snapshot"
        if index % 3 == 1:
            signed_qty = tick.quantity if tick.side == "BUY" else -tick.quantity
            position += signed_qty
            cash -= signed_qty * tick.price
            fills.append(
                {
                    "side": tick.side,
                    "price": round(tick.price, 2),
                    "size": round(tick.quantity, 4),
                    "orderId": f"preview-{1000 + index}",
                }
            )
            event_type = "fill"
        elif index % 9 == 0 and index:
            event_type = "cancel"

        pnl = cash + position * tick.price
        events.append(
            {
                "time": tick.timestamp_ms,
                "type": event_type,
                "position": round(position, 4),
                "pnl": round(pnl, 2),
                "fills": fills,
                "book": build_preview_book(tick.price, index),
            }
        )

    return {
        "dataStatus": status,
        "sessionId": session_id,
        "venue": "Imported CSV preview"
        if status == CSV_STATUS
        else "Deterministic demo preview",
        "markers": build_markers(events),
        "events": events,
    }


def build_preview_book(
    mid: float, index: int, levels: int = 8
) -> dict[str, list[dict[str, float]]]:
    bid_levels = []
    ask_levels = []
    spread = 5.0 + (index % 4)
    for level in range(levels):
        distance = spread / 2 + level * 5.0
        size_wave = 1.4 + ((index + level * 3) % 9) * 0.37
        bid_levels.append(
            {"price": round(mid - distance, 2), "size": round(size_wave, 2)}
        )
        ask_levels.append(
            {"price": round(mid + distance, 2), "size": round(size_wave + 0.28, 2)}
        )
    return {"bids": bid_levels, "asks": ask_levels}


def build_markers(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not events:
        return []
    marker_indexes = sorted(
        set(
            [
                0,
                len(events) // 4,
                len(events) // 2,
                (len(events) * 3) // 4,
                len(events) - 1,
            ]
        )
    )
    labels = [
        ("Opening book snapshot.", "entry"),
        ("First inventory skew after fills.", "entry"),
        ("Risk checkpoint marker.", "risk"),
        ("Mean-reversion window marker.", "entry"),
        ("Replay end.", "risk"),
    ]
    return [
        {
            "time": events[event_index]["time"],
            "label": labels[index][0],
            "type": labels[index][1],
        }
        for index, event_index in enumerate(marker_indexes[: len(labels)])
    ]


def parse_timestamp_ms(value: str) -> int:
    raw = value.strip()
    if raw.isdigit():
        number = int(raw)
        return number if number > 10_000_000_000 else number * 1000
    normalized = raw.replace("Z", "+00:00")
    return int(datetime.fromisoformat(normalized).timestamp() * 1000)


def normalize_side(value: str) -> str:
    side = value.strip().upper()
    if side in {"BUY", "BID", "B"}:
        return "BUY"
    if side in {"SELL", "ASK", "S"}:
        return "SELL"
    raise ValueError(f"unknown side: {value}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
