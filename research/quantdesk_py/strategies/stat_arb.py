"""Cointegration-based statistical arbitrage helpers."""

from __future__ import annotations

import pandas as pd
from statsmodels.tsa.stattools import coint


def engle_granger_pvalue(left: pd.Series, right: pd.Series) -> float:
    """Return the Engle-Granger cointegration test p-value."""
    _, pvalue, _ = coint(left, right)
    return float(pvalue)


def spread_zscore(spread: pd.Series, window: int = 100) -> pd.Series:
    """Compute rolling z-score for a spread series."""
    mean = spread.rolling(window).mean()
    std = spread.rolling(window).std()
    return (spread - mean) / std
