"""Watch Binance for completed one-minute candles and SMA crossovers."""

import asyncio
import json
from collections import deque

import requests
import websockets


BINANCE_WS_URL = (
    "wss://stream.binance.com:9443/stream"
    "?streams=btcusdt@kline_1m/ethusdt@kline_1m"
)
REST_URL = "https://data-api.binance.vision/api/v3/klines"
MAX_CANDLES = 100
INTERVAL_MS = 60_000

candle_buffers = {
    "BTCUSDT": deque(maxlen=MAX_CANDLES),
    "ETHUSDT": deque(maxlen=MAX_CANDLES),
}


def check_sma_crossover(symbol):
    """Print when the latest close crosses the 20-candle simple average."""
    candles = list(candle_buffers[symbol])
    if len(candles) < 21:
        return

    previous_close = candles[-2]["close"]
    current_close = candles[-1]["close"]
    previous_sma = sum(candle["close"] for candle in candles[-21:-1]) / 20
    current_sma = sum(candle["close"] for candle in candles[-20:]) / 20

    if previous_close <= previous_sma and current_close > current_sma:
        direction = "BULLISH"
    elif previous_close >= previous_sma and current_close < current_sma:
        direction = "BEARISH"
    else:
        return

    print(
        f"{direction} CROSSOVER: {symbol} "
        f"| Close: {current_close:.2f} | SMA20: {current_sma:.2f}"
    )


def store_candle(symbol, candle, source="LIVE"):
    """Add a completed candle once, keeping the buffer in time order."""
    buffer = candle_buffers[symbol]
    open_time = candle["open_time"]
    if any(item["open_time"] == open_time for item in buffer):
        return

    # REST API hamesha sabse latest live candle ka data nahi deti, kabhi-kabhi usse purana candle data bhi return kar sakti hai.   
    if buffer and open_time < buffer[-1]["open_time"]:
        by_time = {item["open_time"]: item for item in buffer}  
        by_time[open_time] = candle
        ordered = sorted(by_time.values(), key=lambda item: item["open_time"])
        buffer.clear()
        buffer.extend(ordered[-MAX_CANDLES:])
        print(f"{symbol} | Recovered older candle: {open_time}")
        return

    buffer.append(candle)
    print(
        f"{symbol} | Close: {candle['close']:.2f} | {source} candle stored "
        f"| Buffer: {len(buffer)}/{MAX_CANDLES}"
    )
    check_sma_crossover(symbol)


def fetch_missing_candles(symbol, start_time, end_time):
    """Fetch closed one-minute candles in the requested time range."""
    if start_time > end_time:
        return []

    response = requests.get(
        REST_URL,
        params={
            "symbol": symbol,
            "interval": "1m",
            "startTime": start_time,
            "endTime": end_time,
            "limit": 1000,
        },
        timeout=10,
    )
    response.raise_for_status()

    recovered = []
    for row in response.json():
        if int(row[6]) >= end_time + INTERVAL_MS:
            continue
        recovered.append({
            "symbol": symbol,
            "open_time": int(row[0]),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
        })
    return recovered


def recover_gaps(symbol, next_open_time):
    """Fill in any missing minutes before the next live candle."""
    buffer = candle_buffers[symbol]
    if not buffer:
        return

    missing_start = buffer[-1]["open_time"] + INTERVAL_MS
    missing_end = next_open_time - INTERVAL_MS
    if missing_start > missing_end:
        return

    print(f"{symbol} | Gap detected. Recovering missing candles...")
    try:
        recovered = fetch_missing_candles(symbol, missing_start, missing_end)
    except requests.RequestException as error:
        print(f"{symbol} | REST recovery failed: {error}")
        return

    for candle in recovered:
        store_candle(symbol, candle, source="RECOVERED")
    print(f"{symbol} | Recovery finished: {len(recovered)} candles fetched")


def process_candle(candle):
    """Handle a WebSocket kline message once Binance marks it closed."""
    symbol = candle["s"]
    if symbol not in candle_buffers or not candle["x"]:
        return

    open_time = int(candle["t"])
    if candle_buffers[symbol]:
        recover_gaps(symbol, open_time)

    completed = {
        "symbol": symbol,
        "open_time": open_time,
        "open": float(candle["o"]),
        "high": float(candle["h"]),
        "low": float(candle["l"]),
        "close": float(candle["c"]),
        "volume": float(candle["v"]),
    }
    store_candle(symbol, completed)


async def receive_live_data():
    print("Connecting to Binance WebSocket...")
    async with websockets.connect(
        BINANCE_WS_URL,
        ping_interval=20,
        ping_timeout=20,
        open_timeout=20,
    ) as websocket:
        print("Connected successfully!")
        print("Listening to BTCUSDT and ETHUSDT 1-minute candles.")
        print("Press Ctrl+C to stop.\n")

        async for message in websocket:
            event = json.loads(message)
            process_candle(event["data"]["k"])


async def main():
    retry_delay = 5
    while True:
        try:
            await receive_live_data()
            print("Connection closed. Reconnecting...")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"WebSocket error: {error}")

        print(f"Retrying in {retry_delay} seconds...")
        await asyncio.sleep(retry_delay)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApplication stopped by user.")
        for symbol, buffer in candle_buffers.items():
            print(f"{symbol}: {len(buffer)} candles in memory.")
