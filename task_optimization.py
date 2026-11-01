"""Compare the cost of adding a rolling average to a large DataFrame."""

import time

import numpy as np
import pandas as pd


ROWS_PER_SYMBOL = 2_500_000
SYMBOLS = ["BTCUSDT", "ETHUSDT"]


def create_sample_data(rows_per_symbol):
    """Build reproducible synthetic OHLCV data for each configured symbol."""
    rng = np.random.default_rng(42)
    frames = []

    for symbol in SYMBOLS:
        close = 100 + np.cumsum(rng.normal(0, 1, rows_per_symbol))
        open_price = np.empty(rows_per_symbol)
        open_price[0] = close[0]
        open_price[1:] = close[:-1]

        frames.append(pd.DataFrame({
            "symbol": symbol,
            "open": open_price,
            "high": np.maximum(open_price, close) + rng.uniform(0, 1, rows_per_symbol),
            "low": np.minimum(open_price, close) - rng.uniform(0, 1, rows_per_symbol),
            "close": close,
            "volume": rng.uniform(1, 1000, rows_per_symbol),
        }))

    return pd.concat(frames, ignore_index=True)


def calculate_sma_vectorized(candles):
    """Add a 20-row simple moving average, calculated per symbol."""
    candles["SMA_20"] = candles.groupby("symbol", sort=False)["close"].transform(
        lambda prices: prices.rolling(window=20, min_periods=20).mean()
    )
    return candles


def main():
    expected_rows = ROWS_PER_SYMBOL * len(SYMBOLS)
    print("=" * 60)
    print("LARGE-DATA PANDAS OPTIMIZATION BENCHMARK")
    print("=" * 60)
    print(f"\nRows per symbol: {ROWS_PER_SYMBOL:,}")
    print(f"Expected total rows: {expected_rows:,}")

    print("\nGenerating sample OHLCV data...")
    started = time.perf_counter()
    candles = create_sample_data(ROWS_PER_SYMBOL)
    generation_time = time.perf_counter() - started
    print(f"Data generation time: {generation_time:.2f} seconds")
    print(f"Actual total rows: {len(candles):,}")
    print(f"Number of symbols: {candles['symbol'].nunique()}")

    memory_before_mb = candles.memory_usage(deep=True).sum() / (1024 ** 2)
    print(f"DataFrame memory before SMA: {memory_before_mb:.2f} MB")

    print("\nCalculating SMA-20 with Pandas...")
    started = time.perf_counter()
    result = calculate_sma_vectorized(candles)
    calculation_time = time.perf_counter() - started
    memory_after_mb = result.memory_usage(deep=True).sum() / (1024 ** 2)

    valid_sma_count = int(result["SMA_20"].notna().sum())
    expected_valid_count = len(result) - len(SYMBOLS) * 19
    validation_passed = (
        len(result) == expected_rows and valid_sma_count == expected_valid_count
    )

    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Total rows processed: {len(result):,}")
    print(f"SMA calculation time: {calculation_time:.4f} seconds")
    print(f"Memory before SMA: {memory_before_mb:.2f} MB")
    print(f"Memory after SMA: {memory_after_mb:.2f} MB")
    print(f"Valid SMA values: {valid_sma_count:,}")
    print(f"Output validation passed: {validation_passed}")

    print("\nSample results:")
    print(result[["symbol", "close", "SMA_20"]].groupby("symbol", sort=False).tail(3))
    print("\nLarge-data benchmark completed.")


if __name__ == "__main__":
    main()
