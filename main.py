"""Download and validate Binance hourly candles for the selected symbols."""

import logging
import time
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BASE_URL = "https://data-api.binance.vision/api/v3/klines"
SYMBOLS = ["BTCUSDT", "ETHUSDT"]
INTERVAL = "1h"
INTERVAL_MS = 3_600_000
LIMIT = 1000
START = pd.Timestamp("2026-04-01 00:00:00", tz="UTC")
END = pd.Timestamp("2026-10-01 00:00:00", tz="UTC")
OUTPUT_DIR = Path("output")

COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore",
]
NUMERIC_COLUMNS = [
    "open", "high", "low", "close", "volume", "quote_volume", "trades",
    "taker_buy_base", "taker_buy_quote",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

session = requests.Session()
session.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            respect_retry_after_header=True,
        )
    ),
)


def fetch_candles(symbol):
    """Download a symbol's candles and return a cleaned DataFrame."""
    start_ms = int(START.timestamp() * 1000)
    end_ms = int(END.timestamp() * 1000)
    rows = []

    logging.info("Fetching %s historical data", symbol)
    while start_ms < end_ms:
        response = session.get(
            BASE_URL,
            params={
                "symbol": symbol,
                "interval": INTERVAL,
                "startTime": start_ms,
                "endTime": end_ms - 1,
                "limit": LIMIT,
            },
            timeout=30,
        )
        response.raise_for_status()
        page = response.json()
        if not page:
            break

        rows.extend(page)
        next_start = int(page[-1][0]) + INTERVAL_MS
        if next_start <= start_ms:
            raise RuntimeError("Pagination failed to advance")
        start_ms = next_start

        logging.info("%s: fetched %d candles so far", symbol, len(rows))
        time.sleep(0.2)

    if not rows:
        raise RuntimeError(f"No data received for {symbol}")

    candles = pd.DataFrame(rows, columns=COLUMNS)
    for column in ("open_time", "close_time"):
        candles[column] = pd.to_datetime(candles[column], unit="ms", utc=True)
    candles[NUMERIC_COLUMNS] = candles[NUMERIC_COLUMNS].apply(
        pd.to_numeric, errors="raise"
    )

    candles = candles[
        (candles["open_time"] >= START) & (candles["open_time"] < END)
    ].copy()
    candles = (
        candles.drop_duplicates(subset="open_time", keep="last")
        .sort_values("open_time")
        .reset_index(drop=True)
    )

    invalid = (
        (candles["high"] < candles[["open", "close", "low"]].max(axis=1))
        | (candles["low"] > candles[["open", "close", "high"]].min(axis=1))
        | (candles[["open", "high", "low", "close"]] <= 0).any(axis=1)
        | (candles["volume"] < 0)
        | (candles["trades"] < 0)
    )
    if invalid.any():
        raise ValueError(f"{symbol}: {int(invalid.sum())} invalid candles")

    expected_times = pd.date_range(
        start=START, end=END, freq=INTERVAL, inclusive="left"
    )
    missing_times = expected_times.difference(candles["open_time"])
    if len(missing_times):
        pd.DataFrame({"missing_open_time": missing_times}).to_csv(
            OUTPUT_DIR / f"{symbol}_missing_candles.csv", index=False
        )

    logging.info(
        "%s: %d candles; %d missing timestamps",
        symbol, len(candles), len(missing_times),
    )
    candles.insert(0, "symbol", symbol)
    return candles


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    symbol_data = []

    for symbol in SYMBOLS:
        try:
            symbol_data.append(fetch_candles(symbol))
        except (requests.RequestException, ValueError, RuntimeError):
            logging.exception("Failed to process %s", symbol)
            raise

    candles = pd.concat(symbol_data, ignore_index=True)
    candles = (
        candles.drop_duplicates(subset=["symbol", "open_time"])
        .sort_values(["symbol", "open_time"])
        .reset_index(drop=True)
    )

    csv_path = OUTPUT_DIR / "historical_ohlcv.csv"
    parquet_path = OUTPUT_DIR / "historical_ohlcv.parquet"
    candles.to_csv(csv_path, index=False)
    candles.to_parquet(parquet_path, index=False)

    logging.info("Data processing completed successfully")
    logging.info("Total rows: %d", len(candles))
    logging.info("CSV saved: %s", csv_path.resolve())
    logging.info("Parquet saved: %s", parquet_path.resolve())


if __name__ == "__main__":
    main()
