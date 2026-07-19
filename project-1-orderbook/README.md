# Project 1 — Order Book Dynamics & Market Microstructure

## Problem framing

Most market analysis treats price as a time series of OHLCV candles.
This project goes one level deeper: the **limit order book (LOB)** — the live queue of all outstanding buy and sell orders at every price level.
Studying how the book evolves reveals the *mechanics* of price formation, not just its outcome.

Three questions drive the analysis:

1. **Spread dynamics** — How wide is the bid-ask spread, and how does it fluctuate?
   The spread is the cost of immediacy for market-order traders; spikes signal liquidity stress.

2. **Order Flow Imbalance (OFI)** — Does net pressure at the best bid/ask predict short-term price moves?
   Formalised by Cont, Kukanov & Stoikov (2014), OFI measures incremental supply/demand imbalance at the touch.

3. **Directional predictability** — Can a simple linear model trading on OFI beat a 50 % random baseline at a 5-second horizon?

---

## Data source

**Binance WebSocket API** — public, no authentication required.

| | |
|---|---|
| Stream | `wss://stream.binance.com:9443/ws/btcusdt@depth@100ms` |
| Snapshot seed | `https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=1000` |
| Instrument | BTCUSDT (one of the most liquid crypto pairs, ~1–3 bps spread) |
| Capture cadence | 100 ms diff events → 1-second CSV snapshots |
| Default duration | 900 seconds (15 minutes) |
| Depth captured | Top 10 bid and ask levels per snapshot |

The book is reconstructed using the official Binance synchronisation protocol:
open the stream → buffer events → fetch REST snapshot → discard stale events → apply diffs in order.

---

## Methodology

### Data collection — `src/collector.py`

- Connects to the diff-depth WebSocket stream.
- Fetches a REST snapshot while the stream buffers incoming events.
- Applies each diff event to the local book after ID-gating (drops events where `u < lastUpdateId + 1`).
- Writes one CSV row per second: timestamp + top-10 bid prices/sizes + top-10 ask prices/sizes.

### Derived series — `src/orderbook.py`

| Function | Description |
|---|---|
| `mid_price(df)` | `(bid_price_1 + ask_price_1) / 2` |
| `spread(df)` | `ask_price_1 - bid_price_1` in USDT |
| `spread_bps(df)` | Spread in basis points |
| `depth_imbalance(df, n)` | `(bid_vol - ask_vol) / (bid_vol + ask_vol)` at top-n levels |

### Order Flow Imbalance — `src/ofi.py`

Point OFI at time t (Cont et al. 2014):

```
e_bid[t] = q_bid[t] · 𝟙(P_bid[t] ≥ P_bid[t−1]) − q_bid[t−1] · 𝟙(P_bid[t] ≤ P_bid[t−1])
e_ask[t] = q_ask[t] · 𝟙(P_ask[t] ≤ P_ask[t−1]) − q_ask[t−1] · 𝟙(P_ask[t] ≥ P_ask[t−1])
OFI[t]   = e_bid[t] − e_ask[t]
```

Aggregated over a rolling 10-second window for the regression study.

### Predictive analysis — `notebooks/01_exploration.ipynb`

- **Lag correlation**: Pearson ρ between rolling OFI[t] and log mid-return at t+k for k = 1…30 seconds.
- **Logistic regression**: `sign(Δmid[t+5]) ~ OFI[t]`, evaluated on a held-out 30 % time slice (no shuffling).

---

## How to run

Requires **Python ≥ 3.10**.

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Capture 15 minutes of live order book data (run from project root)
python src/collector.py

# Optional flags
python src/collector.py --duration 300 --levels 10 --output data/ob_test.csv

# 3. Open the analysis notebook
jupyter notebook notebooks/01_exploration.ipynb
```

The notebook auto-detects the most recent CSV in `data/`.

---

## Key findings

*(Based on a 15-minute live capture of BTCUSDT, 850 snapshots, July 19 2026.)*

- **Spread**: Mean ~15.5 bps for BTCUSDT; stable in a narrow band (~15.0–15.5 bps), with mild widening during periods of larger mid-price moves.
- **OFI correlation**: Peak Pearson ρ ≈ 0.31 at a ~10-second horizon, decaying to ρ ≈ 0.20 by 30 seconds — directionally consistent with Cont et al. (2014), though the peak correlation is higher than typical published estimates, likely reflecting the short 15-minute sample size.
- **Directional accuracy**: Logistic regression reaches 82.9 % out-of-sample accuracy, but this is *below* the 88.3 % naive majority-class baseline (dataset is imbalanced: only 11.7 % "Up" moves). Recall on the "Up" class is weak (27 %), showing that a naive classifier cannot yet exploit the OFI signal despite its real correlation with returns — next step is class rebalancing or reframing as regression on continuous returns.

---

## Possible extensions

- **Multi-level OFI**: Aggregate OFI across the top 5 levels, not just the best bid/ask.
- **Intraday seasonality**: OFI signal strength likely varies by time-of-day (US open, Asian session, etc.).
- **Cross-asset flow**: Does BTC OFI lead ETH price? (inter-market microstructure).
- **Execution modelling**: Use price impact estimates to simulate optimal execution (TWAP vs. OFI-adaptive).
- **Real-time dashboard**: Stream OFI and spread metrics into a live Plotly/Dash display.

---

*Reference: Cont R., Kukanov A. & Stoikov S. (2014). The Price Impact of Order Book Events. Journal of Financial Econometrics, 12(1), 47–88.*
