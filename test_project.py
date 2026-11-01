"""Sanity checks for the generated indicator and four-hour candle files."""

from pathlib import Path

import pandas as pd


def main():
    indicators_path = Path("output/technical_indicators.csv")
    candles_path = Path("output/ohlcv_4h.csv")
    if not indicators_path.exists():
        raise FileNotFoundError(f"Missing output file: {indicators_path}")
    if not candles_path.exists():
        raise FileNotFoundError(f"Missing output file: {candles_path}")

    indicators = pd.read_csv(indicators_path)
    candles = pd.read_csv(candles_path)

    assert len(indicators) == 8784, "Unexpected indicator row count"
    assert len(candles) == 2196, "Unexpected 4-hour row count"

    counts = candles.groupby("symbol").size()
    assert counts.get("BTCUSDT", 0) == 1098
    assert counts.get("ETHUSDT", 0) == 1098

    for column in ("SMA_20", "EMA_20", "EMA_50"):
        assert column in indicators.columns, f"{column} is missing"

    assert indicators["SMA_20"].isna().sum() == 38
    assert indicators["EMA_20"].isna().sum() == 38
    assert indicators["EMA_50"].isna().sum() == 98

    ohlcv = ["open", "high", "low", "close", "volume"]
    assert candles[ohlcv].notna().all().all(), "Missing OHLCV values"
    assert (
        candles["high"] >= candles[["open", "close", "low"]].max(axis=1)
    ).all(), "High validation failed"
    assert (
        candles["low"] <= candles[["open", "close", "high"]].min(axis=1)
    ).all(), "Low validation failed"

    print("All checks passed.")
    print(f"Indicator rows: {len(indicators)}")
    print(f"4-hour candle rows: {len(candles)}")
    print(counts.to_string())


if __name__ == "__main__":
    main()
