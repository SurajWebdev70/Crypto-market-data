"""Add moving averages to the historical candle data."""

import pandas as pd


def calculate_indicators(candles):
    """Return a copy of the candles with SMA-20, EMA-20 and EMA-50 columns."""
    result = candles.copy()
    result["open_time"] = pd.to_datetime(result["open_time"], utc=True)
    result = result.sort_values(["symbol", "open_time"]).reset_index(drop=True)

    close_by_symbol = result.groupby("symbol")["close"]
    result["SMA_20"] = close_by_symbol.transform(
        lambda prices: prices.rolling(window=20, min_periods=20).mean()
    )
    result["EMA_20"] = close_by_symbol.transform(
        lambda prices: prices.ewm(span=20, adjust=False, min_periods=20).mean()
    )
    result["EMA_50"] = close_by_symbol.transform(
        lambda prices: prices.ewm(span=50, adjust=False, min_periods=50).mean()
    )
    return result


def main():
    input_path = "output/historical_ohlcv.csv"
    output_path = "output/technical_indicators.csv"

    candles = pd.read_csv(input_path)
    result = calculate_indicators(candles)
    result.to_csv(output_path, index=False)

    print(f"Technical indicators saved to {output_path}")
    print("\nSample output:")
    columns = ["symbol", "open_time", "close", "SMA_20", "EMA_20", "EMA_50"]
    print(result[columns].head(25).tail(10).to_string(index=False))


if __name__ == "__main__":
    main()
