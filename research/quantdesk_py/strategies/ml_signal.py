"""Short-horizon alpha features used as a quote-skew input, not a standalone bot."""

from __future__ import annotations

import pandas as pd


def order_book_imbalance(bid_volume: pd.Series, ask_volume: pd.Series) -> pd.Series:
    """Return top-of-book volume imbalance in [-1, 1]."""
    denominator = bid_volume + ask_volume
    return (bid_volume - ask_volume) / denominator.replace(0, pd.NA)
