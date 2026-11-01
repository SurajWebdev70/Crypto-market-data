"""Combine hourly candles into four-hour candles."""

import pandas as pd


def resample_to_4h(candles):
    """Aggregate each symbol independently into four-hour OHLCV bars."""
    result = candles.copy()
    result["open_time"] = pd.to_datetime(result["open_time"], utc=True)
    result = result.sort_values(["symbol", "open_time"])

    # Ek bar pehle hourly candle ke opening time par khulta hai aur aakhri hourly candle ke closing time par band hota hai.
    ohlcv = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    return (
        result.set_index("open_time")
        .groupby("symbol")
        .resample("4h", origin="start_day")
        .agg(ohlcv)
        .dropna(subset=["open", "high", "low", "close"])
        .reset_index()
    )


def main():
    input_path = "output/historical_ohlcv.csv"
    output_path = "output/ohlcv_4h.csv"

    candles = pd.read_csv(input_path)
    four_hour = resample_to_4h(candles)
    four_hour.to_csv(output_path, index=False)

    print(f"Four-hour candles saved to {output_path}")
    print(f"Total rows: {len(four_hour)}")
    print("\nSample data:")
    print(four_hour.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
