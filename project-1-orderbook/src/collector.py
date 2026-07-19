"""
Binance order book collector.

Connects to the diff-depth WebSocket stream, seeds the local book from a REST
snapshot, and writes top-N level snapshots to CSV at a 1-second cadence.

Follows the official Binance synchronisation protocol:
  1. Open WebSocket — stream starts buffering events immediately.
  2. Fetch REST snapshot (contains lastUpdateId).
  3. Drop buffered events where u < lastUpdateId + 1.
  4. First valid event must satisfy U <= lastUpdateId + 1 <= u.
  5. Apply subsequent events in order; each event's U must equal prev u + 1.

Usage:
    python src/collector.py                          # BTCUSDT, 900 s, 10 levels
    python src/collector.py --duration 60 --levels 5 --output data/test.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

REST_DEPTH_URL  = "https://api.binance.com/api/v3/depth"
WS_DEPTH_URL    = "wss://stream.binance.com:9443/ws/{symbol}@depth@100ms"
SNAPSHOT_INTERVAL = 1.0   # seconds between CSV rows


# ---------------------------------------------------------------------------
# REST seed
# ---------------------------------------------------------------------------

def _fetch_rest_snapshot(symbol: str, limit: int = 1000) -> dict:
    """Pull a full order book snapshot from the Binance REST API."""
    resp = requests.get(
        REST_DEPTH_URL,
        params={"symbol": symbol.upper(), "limit": limit},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Local order book
# ---------------------------------------------------------------------------

class LocalOrderBook:
    """
    Maintains a local mirror of the Binance limit order book.

    Seeded from a REST snapshot; updated in real time via diff-depth events.
    Prices are stored as float keys for fast min/max lookup.
    """

    def __init__(self, snapshot: dict) -> None:
        self.last_update_id: int = snapshot["lastUpdateId"]
        self.bids: dict[float, float] = {
            float(p): float(q) for p, q in snapshot["bids"]
        }
        self.asks: dict[float, float] = {
            float(p): float(q) for p, q in snapshot["asks"]
        }
        self._synced = False

    # ------------------------------------------------------------------
    def apply_event(self, event: dict) -> bool:
        """
        Apply one diff-depth event.  Returns True when applied, False when dropped.

        u = final update ID in the event (Binance field name)
        U = first update ID in the event (Binance field name)
        """
        u: int = event["u"]
        U: int = event["U"]

        if not self._synced:
            if u < self.last_update_id + 1:
                return False  # stale — arrived before snapshot
            if not (U <= self.last_update_id + 1 <= u):
                return False  # gap between snapshot and stream; drop
            self._synced = True
            log.info("Book synced at lastUpdateId=%d", self.last_update_id)

        self._apply_side(self.bids, event["b"])
        self._apply_side(self.asks, event["a"])
        self.last_update_id = u
        return True

    @staticmethod
    def _apply_side(side: dict[float, float], updates: list) -> None:
        for price_str, qty_str in updates:
            price = float(price_str)
            qty   = float(qty_str)
            if qty == 0.0:
                side.pop(price, None)
            else:
                side[price] = qty

    # ------------------------------------------------------------------
    def top_n(self, n: int) -> tuple[list[tuple], list[tuple]]:
        """Top-N bids (best = highest price first) and asks (best = lowest first)."""
        top_bids = sorted(self.bids.items(), key=lambda x: -x[0])[:n]
        top_asks = sorted(self.asks.items(), key=lambda x:  x[0])[:n]
        return top_bids, top_asks

    def best_bid(self) -> float | None:
        return max(self.bids) if self.bids else None

    def best_ask(self) -> float | None:
        return min(self.asks) if self.asks else None


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def _csv_header(n: int) -> list[str]:
    cols = ["timestamp_utc"]
    cols += [f"bid_price_{i}" for i in range(1, n + 1)]
    cols += [f"bid_size_{i}"  for i in range(1, n + 1)]
    cols += [f"ask_price_{i}" for i in range(1, n + 1)]
    cols += [f"ask_size_{i}"  for i in range(1, n + 1)]
    return cols


def _csv_row(ts: str, top_bids: list, top_asks: list, n: int) -> list:
    """Build one CSV row; pads with empty string if fewer than n levels."""
    row = [ts]
    for i in range(n):
        row.append(top_bids[i][0] if i < len(top_bids) else "")
    for i in range(n):
        row.append(top_bids[i][1] if i < len(top_bids) else "")
    for i in range(n):
        row.append(top_asks[i][0] if i < len(top_asks) else "")
    for i in range(n):
        row.append(top_asks[i][1] if i < len(top_asks) else "")
    return row


# ---------------------------------------------------------------------------
# Core collection loop
# ---------------------------------------------------------------------------

async def collect(
    symbol: str,
    duration: int,
    n_levels: int,
    output_path: Path,
) -> None:
    """WebSocket → local book → 1-second CSV snapshots for `duration` seconds."""

    ws_url = WS_DEPTH_URL.format(symbol=symbol.lower())
    log.info("Connecting to %s", ws_url)

    async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
        # Fetch REST snapshot while WebSocket is already buffering events.
        log.info("Fetching REST snapshot …")
        loop = asyncio.get_event_loop()
        snapshot = await loop.run_in_executor(None, _fetch_rest_snapshot, symbol)
        book = LocalOrderBook(snapshot)
        log.info("Snapshot received: lastUpdateId=%d", book.last_update_id)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(_csv_header(n_levels))
            f.flush()

            start        = time.monotonic()
            last_snap    = 0.0
            rows_written = 0

            log.info("Capturing for %d s → %s", duration, output_path)

            while (elapsed := time.monotonic() - start) < duration:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                except asyncio.TimeoutError:
                    log.warning("WebSocket recv timed out; stopping capture.")
                    break

                event = json.loads(raw)
                if not book.apply_event(event):
                    continue

                now = time.monotonic()
                if now - last_snap >= SNAPSHOT_INTERVAL:
                    last_snap = now
                    ts = datetime.now(timezone.utc).isoformat()
                    top_bids, top_asks = book.top_n(n_levels)
                    writer.writerow(_csv_row(ts, top_bids, top_asks, n_levels))
                    f.flush()
                    rows_written += 1

                    if rows_written % 60 == 0:
                        mid = ((book.best_bid() or 0) + (book.best_ask() or 0)) / 2
                        log.info(
                            "%.0fs elapsed | rows=%d | mid=%.2f",
                            elapsed, rows_written, mid,
                        )

    log.info("Done. %d snapshots written to %s", rows_written, output_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Binance order book collector")
    parser.add_argument("--symbol",   default="BTCUSDT",
                        help="Trading pair symbol (default: BTCUSDT)")
    parser.add_argument("--duration", type=int, default=900,
                        help="Capture duration in seconds (default: 900)")
    parser.add_argument("--levels",   type=int, default=10,
                        help="Order book depth levels to capture (default: 10)")
    parser.add_argument("--output",   type=Path, default=None,
                        help="Output CSV path (default: data/ob_<symbol>_<timestamp>.csv)")
    args = parser.parse_args()

    if args.output is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        args.output = Path(f"data/ob_{args.symbol.lower()}_{ts}.csv")

    asyncio.run(collect(args.symbol, args.duration, args.levels, args.output))


if __name__ == "__main__":
    main()
