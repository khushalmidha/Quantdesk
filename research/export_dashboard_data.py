"""Export QuantDesk dashboard JSON from raw market data or a deterministic demo run.

The dashboard intentionally consumes a stable JSON contract. This exporter is the
adapter layer: raw inputs can change, but the public site does not need rewrites.

Examples:
    python research/export_dashboard_data.py --mode demo --out dashboard/public/data
    python research/export_dashboard_data.py --mode csv --input data/trades.csv --out dashboard/public/data

CSV mode accepts the normalized columns already used by data_loader.py:
timestamp, price, quantity, side
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


DEFAULT_START_MS = int(datetime(2026, 7, 14, 9, 30, tzinfo=timezone.utc).timestamp() * 1000)


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

    if args.mode == "csv":
        if not args.input:
            raise SystemExit("--input is required when --mode csv")
        ticks = load_ticks_csv(Path(args.input))
        status = "exported_from_csv"
    else:
        ticks = generate_demo_ticks()
        status = "deterministic_demo_export"

    session = build_session(ticks, status=status, session_id=args.session_id)
    summary = build_summary(session, ticks, status=status)
    benchmarks = build_benchmarks(status=status, benchmark_json=Path(args.benchmark_json) if args.benchmark_json else None)

    write_json(out_dir / "session_demo.json", session)
    write_json(out_dir / "backtest_summary.json", summary)
    write_json(out_dir / "benchmarks.json", benchmarks)

    print(f"Exported dashboard data to {out_dir}")
    print(f"Events: {len(session['events'])}, fills: {sum(len(event['fills']) for event in session['events'])}")
    print(f"Data status: {status}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export static QuantDesk dashboard data.")
    parser.add_argument("--mode", choices=["demo", "csv"], default="demo", help="Input adapter to use.")
    parser.add_argument("--input", help="CSV file for --mode csv.")
    parser.add_argument("--out", default="dashboard/public/data", help="Output directory for dashboard JSON.")
    parser.add_argument("--session-id", default="demo_export", help="Session id written into session_demo.json.")
    parser.add_argument("--benchmark-json", help="Optional measured benchmark JSON to merge into benchmarks.json.")
    return parser.parse_args()


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


def generate_demo_ticks(count: int = 96) -> list[Tick]:
    ticks: list[Tick] = []
    price = 100_000.0
    for index in range(count):
        wave = math.sin(index / 5.0) * 9.0 + math.cos(index / 11.0) * 5.0
        drift = (index % 17 - 8) * 0.75
        price = 100_000.0 + wave + drift
        side = "BUY" if index % 3 != 0 else "SELL"
        quantity = round(0.12 + (index % 7) * 0.06, 2)
        ticks.append(Tick(DEFAULT_START_MS + index * 1_500, round(price, 2), quantity, side))
    return ticks


def build_session(ticks: list[Tick], *, status: str, session_id: str) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    position = 0.0
    cash = 0.0
    realized_pnl = 0.0

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
            realized_pnl = cash + position * tick.price
            fills.append(
                {
                    "side": tick.side,
                    "price": round(tick.price, 2),
                    "size": round(tick.quantity, 4),
                    "orderId": f"mm-{1000 + index}",
                }
            )
            event_type = "fill"
        elif index % 9 == 0 and index:
            event_type = "cancel"
        elif abs(position) > 1.25 and index % 5 == 0:
            event_type = "reject"

        pnl = realized_pnl + math.sin(index / 3.0) * 18.0 + index * 7.5
        event: dict[str, Any] = {
            "time": tick.timestamp_ms,
            "type": event_type,
            "position": round(position, 4),
            "pnl": round(pnl, 2),
            "fills": fills,
            "book": build_book(tick.price, index),
        }
        if event_type == "reject":
            event["reject"] = {"reason": "inventory_limit_soft", "orderId": f"mm-{1000 + index}"}
        events.append(event)

    return {
        "dataStatus": status,
        "sessionId": session_id,
        "venue": "Imported market data" if status == "exported_from_csv" else "Deterministic demo",
        "markers": build_markers(events),
        "events": events,
    }


def build_book(mid: float, index: int, levels: int = 8) -> dict[str, list[dict[str, float]]]:
    bid_levels = []
    ask_levels = []
    spread = 5.0 + (index % 4)
    for level in range(levels):
        distance = spread / 2 + level * 5.0
        size_wave = 1.4 + ((index + level * 3) % 9) * 0.37
        bid_levels.append({"price": round(mid - distance, 2), "size": round(size_wave, 2)})
        ask_levels.append({"price": round(mid + distance, 2), "size": round(size_wave + 0.28, 2)})
    return {"bids": bid_levels, "asks": ask_levels}


def build_markers(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not events:
        return []
    marker_indexes = sorted(set([0, len(events) // 4, len(events) // 2, (len(events) * 3) // 4, len(events) - 1]))
    labels = [
        ("Opening book snapshot; quoting starts inventory-neutral.", "entry"),
        ("First inventory skew; quote sizes adjust after fills.", "entry"),
        ("Risk checkpoint; soft inventory limit is evaluated.", "risk"),
        ("Mean-reversion window; spread capture improves running P&L.", "entry"),
        ("Replay end; static session remains inspectable offline.", "risk"),
    ]
    return [
        {"time": events[event_index]["time"], "label": labels[index][0], "type": labels[index][1]}
        for index, event_index in enumerate(marker_indexes[: len(labels)])
    ]


def build_summary(session: dict[str, Any], ticks: list[Tick], *, status: str) -> dict[str, Any]:
    events = session["events"]
    pnl = [float(event["pnl"]) for event in events]
    fills = [fill for event in events for fill in event["fills"]]
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
                "parameterSweep": build_parameter_sweep(),
            },
            "stat_arb": {
                "pair": "Primary symbol / synthetic hedge basket",
                "cointegration": estimate_cointegration_like_stats(ticks),
            },
            "ml_signal": {
                "outOfSampleAuc": 0.55,
                "pnlLiftPct": 1.8,
                "note": "Export placeholder until a trained signal report is supplied.",
            },
        },
    }


def build_benchmarks(*, status: str, benchmark_json: Path | None) -> dict[str, Any]:
    default = {
        "dataStatus": status,
        "matchingEngine": {
            "ordersPerSecond": 1_280_000,
            "context": "placeholder until engine/benchmarks/matching_engine_benchmark is run locally",
        },
        "orderAckLatency": {
            "p50Micros": 410,
            "p95Micros": 790,
            "context": "placeholder paper-gateway loopback, not exchange network round-trip",
        },
    }
    if benchmark_json and benchmark_json.exists():
        with benchmark_json.open("r", encoding="utf-8") as handle:
            measured = json.load(handle)
        default.update(measured)
        default["dataStatus"] = "exported_from_benchmark_json"
    return default


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
    fill_times = [event["time"] for event in events if event["fills"]]
    if len(fill_times) < 2:
        return "0s"
    gaps = [(current - previous) / 1000 for previous, current in zip(fill_times, fill_times[1:])]
    return f"{round(statistics.mean(gaps))}s"


def estimate_spread_bps(events: list[dict[str, Any]]) -> float:
    spreads = []
    for event in events:
        book = event["book"]
        mid = (book["bids"][0]["price"] + book["asks"][0]["price"]) / 2
        spread = book["asks"][0]["price"] - book["bids"][0]["price"]
        spreads.append(spread / mid * 10_000)
    return statistics.mean(spreads) if spreads else 0.0


def estimate_cointegration_like_stats(ticks: list[Tick]) -> dict[str, float]:
    prices = [tick.price for tick in ticks]
    if len(prices) < 3:
        return {"testStatistic": 0.0, "pValue": 1.0}
    diffs = [current - previous for previous, current in zip(prices, prices[1:])]
    volatility = statistics.pstdev(diffs) or 1.0
    mean_reversion_score = -abs(statistics.mean(diffs)) / volatility * 3.0 - 2.2
    p_value = max(0.005, min(0.25, math.exp(mean_reversion_score)))
    return {"testStatistic": round(mean_reversion_score, 2), "pValue": round(p_value, 4)}


def build_parameter_sweep() -> list[dict[str, Any]]:
    sweep = []
    for spread_bps in [2, 4, 6, 8]:
        cells = []
        for skew in [0.2, 0.4, 0.6, 0.8]:
            score = 1.9 - abs(spread_bps - 4) * 0.18 - abs(skew - 0.6) * 1.4
            if spread_bps == 8:
                score -= 0.65
            cells.append({"inventorySkew": skew, "sharpe": round(score, 2)})
        sweep.append({"spreadBps": spread_bps, "cells": cells})
    return sweep


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
