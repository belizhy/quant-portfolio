"""
Order book loader and derived series.

Loads CSV snapshots produced by collector.py and exposes clean
pandas Series for mid-price, spread, depth imbalance, and per-level views.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def load_snapshots(path: str | Path) -> pd.DataFrame:
    """
    Load a collector CSV into a tidy DataFrame.

    - timestamp_utc is parsed to datetime and set as the index.
    - All price/size columns are cast to float (empty-string pads → NaN).
    """
    df = pd.read_csv(path, parse_dates=["timestamp_utc"], index_col="timestamp_utc")
    df = df.apply(pd.to_numeric, errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Core derived series
# ---------------------------------------------------------------------------

def mid_price(df: pd.DataFrame) -> pd.Series:
    """Best mid-price: (bid_price_1 + ask_price_1) / 2."""
    return (df["bid_price_1"] + df["ask_price_1"]) / 2


def spread(df: pd.DataFrame) -> pd.Series:
    """Best bid-ask spread in absolute price units."""
    return df["ask_price_1"] - df["bid_price_1"]


def spread_bps(df: pd.DataFrame) -> pd.Series:
    """Spread in basis points: (spread / mid) × 10 000."""
    return (spread(df) / mid_price(df)) * 10_000


# ---------------------------------------------------------------------------
# Depth views
# ---------------------------------------------------------------------------

def bid_depth(df: pd.DataFrame, n: int | None = None) -> pd.DataFrame:
    """Price and size columns for the top-n bid levels (all levels if n=None)."""
    return df[_level_cols(df, "bid", n)]


def ask_depth(df: pd.DataFrame, n: int | None = None) -> pd.DataFrame:
    """Price and size columns for the top-n ask levels (all levels if n=None)."""
    return df[_level_cols(df, "ask", n)]


def _level_cols(df: pd.DataFrame, side: str, n: int | None) -> list[str]:
    max_levels = sum(1 for c in df.columns if c.startswith(f"{side}_price_"))
    k = min(n, max_levels) if n is not None else max_levels
    price_cols = [f"{side}_price_{i}" for i in range(1, k + 1)]
    size_cols  = [f"{side}_size_{i}"  for i in range(1, k + 1)]
    return price_cols + size_cols


# ---------------------------------------------------------------------------
# Volume & imbalance
# ---------------------------------------------------------------------------

def total_bid_volume(df: pd.DataFrame, n: int | None = None) -> pd.Series:
    """Cumulative quoted bid volume across the top-n levels."""
    cols = [c for c in df.columns if c.startswith("bid_size_")]
    if n is not None:
        cols = cols[:n]
    return df[cols].sum(axis=1)


def total_ask_volume(df: pd.DataFrame, n: int | None = None) -> pd.Series:
    """Cumulative quoted ask volume across the top-n levels."""
    cols = [c for c in df.columns if c.startswith("ask_size_")]
    if n is not None:
        cols = cols[:n]
    return df[cols].sum(axis=1)


def depth_imbalance(df: pd.DataFrame, n: int = 5) -> pd.Series:
    """
    Volume imbalance at the top-n levels:
        (bid_vol - ask_vol) / (bid_vol + ask_vol)
    Ranges from -1 (pure ask pressure) to +1 (pure bid pressure).
    """
    bv = total_bid_volume(df, n)
    av = total_ask_volume(df, n)
    return (bv - av) / (bv + av)
