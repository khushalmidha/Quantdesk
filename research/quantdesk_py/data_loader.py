"""Historical data ingestion placeholders for Binance public datasets."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_ticks_csv(path: str | Path) -> pd.DataFrame:
    """Load normalized tick data from CSV for later replay into the C++ engine."""
    frame = pd.read_csv(path)
    required = {"timestamp", "price", "quantity", "side"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")
    return frame.sort_values("timestamp").reset_index(drop=True)
