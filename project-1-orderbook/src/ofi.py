"""
Order Flow Imbalance (OFI) calculator.

Implements the OFI measure from:
    Cont, Kukanov & Stoikov (2014) — "The Price Impact of Order Book Events"
    Journal of Financial Econometrics, 12(1), 47-88.

OFI quantifies net buying/selling pressure at the touch (best bid and ask)
between consecutive book snapshots.  A positive OFI signals more aggressive
buying; negative signals more aggressive selling.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Point OFI
# ---------------------------------------------------------------------------

def compute_ofi(df: pd.DataFrame) -> pd.Series:
    """
    Compute point-in-time OFI from consecutive book snapshots.

    For each pair of adjacent rows (Cont et al. 2014, eq. 1):

        e_bid[t] = q_bid[t] · 𝟙(P_bid[t] ≥ P_bid[t-1])
                 − q_bid[t-1] · 𝟙(P_bid[t] ≤ P_bid[t-1])

        e_ask[t] = q_ask[t] · 𝟙(P_ask[t] ≤ P_ask[t-1])
                 − q_ask[t-1] · 𝟙(P_ask[t] ≥ P_ask[t-1])

        OFI[t] = e_bid[t] − e_ask[t]

    Intuition:
        e_bid > 0  →  bid side deepened or moved up   (buy pressure)
        e_ask < 0  →  ask side deepened or moved down  (buy pressure)
        Positive OFI therefore signals net buy-side aggression.

    Returns a Series aligned with df's index; first value is NaN.
    """
    bp = df["bid_price_1"]
    bq = df["bid_size_1"]
    ap = df["ask_price_1"]
    aq = df["ask_size_1"]

    bp_prev = bp.shift(1)
    bq_prev = bq.shift(1)
    ap_prev = ap.shift(1)
    aq_prev = aq.shift(1)

    e_bid = (
        bq * (bp >= bp_prev).astype(float)
        - bq_prev * (bp <= bp_prev).astype(float)
    )
    e_ask = (
        aq * (ap <= ap_prev).astype(float)
        - aq_prev * (ap >= ap_prev).astype(float)
    )

    ofi = e_bid - e_ask
    ofi.name = "ofi"
    return ofi


# ---------------------------------------------------------------------------
# Rolling OFI
# ---------------------------------------------------------------------------

def rolling_ofi(df: pd.DataFrame, window: int = 10) -> pd.Series:
    """
    Aggregate point OFI over a rolling window (sum).

    window: number of 1-second snapshots to accumulate (default 10 → 10-second OFI).
    A longer window smooths noise; shorter windows are more responsive but noisier.
    """
    point_ofi = compute_ofi(df)
    rofi = point_ofi.rolling(window, min_periods=window).sum()
    rofi.name = f"ofi_{window}s"
    return rofi


# ---------------------------------------------------------------------------
# Regression-ready dataset
# ---------------------------------------------------------------------------

def ofi_returns_df(
    df: pd.DataFrame,
    window: int = 10,
    horizon: int = 5,
) -> pd.DataFrame:
    """
    Build a clean DataFrame for OFI → forward-return regression.

    Columns:
        ofi       : rolling OFI at time t
        ret_fwd   : log mid-price return from t to t+horizon
        direction : 1 if ret_fwd > 0, else 0  (for logistic regression)

    Rows with any NaN are dropped so the caller gets a clean X/y pair.
    """
    mid = (df["bid_price_1"] + df["ask_price_1"]) / 2
    rofi = rolling_ofi(df, window=window)

    ret_fwd   = np.log(mid.shift(-horizon) / mid)
    direction = (ret_fwd > 0).astype(int)

    result = pd.DataFrame({
        "ofi":       rofi,
        "ret_fwd":   ret_fwd,
        "direction": direction,
    }).dropna()

    return result
