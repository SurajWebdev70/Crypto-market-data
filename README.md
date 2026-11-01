<!-- # Crypto Market Data Pipeline -->

<!-- over -->
A Python-based data pipeline that fetches historical hourly OHLCV market data for BTCUSDT and ETHUSDT from Binance's public REST API.

 <!-- ## Technologies  -->
 Python 3.12
 Requests
 Pandas
 PyArrow
 Binance REST API

<!--  Features -->
 Historical market data collection
 API pagination and retry handling
 UTC timestamp conversion
 Numeric data type conversion
 Duplicate candle removal
 Missing hourly candle detection
 Data validation
 CSV and Parquet export

   <!-- Date Range -->
April 1, 2026, to September 30, 2026, inclusive (UTC).

<!--  Run Instructions -->
1.Install Python 3.12 or a compatible version.
2.Install dependencies using`pip install -r requirements.txt`.
3.Run`python main.py`.

<!-- Output -->
The `output/` directory contains the combined historical OHLCV dataset in CSV and Parquet formats, plus missing-candle reports when gaps are detected.

<!-- Data Source -->
Binance public REST API — Kline/Candlestick data.   

<!-- Total rows aur coin-wise data dekhne ke liye: -->

<!-- python -c "import pandas as pd; df=pd.read_csv('output/historical_ohlcv.csv'); print('Total rows:',len(df)); print(df['symbol'].value_counts())" -->

<!-- Pehli 10 rows dekhne ke liye: -->

<!-- python -c "import pandas as pd; print(pd.read_csv('output/historical_ohlcv.csv').head(10).to_string(index=False))" -->   







<!-- ## Task 2: Technical Indicators and 4-Hour Candles -->

In this task, I worked with the historical market data of BTCUSDT and ETHUSDT. I used Python and Pandas to calculate moving averages and convert the 1-hour data into 4-hour candles.

<!--  1. Calculating Moving Averages -->
I added three technical indicators to the historical data:

 **SMA 20:** Calculates the average closing price of the last 20 candles.
 **EMA 20:** Gives more importance to recent closing prices using a span of 20.
 **EMA 50:** Calculates the exponential moving average using a span of 50.

I sorted the data by symbol and time before calculating the indicators. I also calculated them separately for BTCUSDT and ETHUSDT so that their prices would not get mixed up.

The initial values are left blank when there is not enough historical data to calculate an indicator.

The results are saved in `output/technical_indicators.csv`.

<!--  2. Converting 1-Hour Candles to 4-Hour Candles -->

I created another script to combine the 1-hour candles into 4-hour candles.

For each 4-hour candle, I used:
 The first hourly candle's open price.
 The highest price from the four candles.
 The lowest price from the four candles.
 The last hourly candle's close price.
 The total volume of the four candles.

I processed each cryptocurrency separately and saved the results in `output/ohlcv_4h.csv`. The original historical data remains unchanged.

<!-- 3. Checking the Results -->

After running both scripts, I checked the row counts and missing values to make sure the output looked correct.

 Historical data: 8,784 rows.
 Technical indicators: 8,784 rows.
 4-hour candles: 2,196 rows.
 BTCUSDT: 1,098 candles.
 ETHUSDT: 1,098 candles.

The required OHLCV columns in the 4-hour output have no missing values, and the high/low consistency check passed.

<!--  Tools Used -->

 Python
 Pandas
 CSV files
 Time-series resampling






<!-- ## Task 3: Live Cryptocurrency Data Streaming -->

 Overview
Developed a Python application to stream real-time cryptocurrency market data from Binance using WebSockets. The application monitors BTCUSDT and ETHUSDT trading pairs at a 1-minute interval.

 Features Implemented

1.**Live Data Streaming:** Connects to Binance WebSocket streams to receive real-time 1-minute candlestick (kline) updates for BTCUSDT and ETHUSDT.

2.**Completed Candle Storage:** Stores only completed candles, including open, high, low, close, volume, and candle opening timestamp.

3.**In-Memory Buffer:** Maintains the latest 100 completed candles separately for each trading pair using Python's deque with a maximum length of 100.

4.**SMA 20 Calculation:** Calculates the 20-period Simple Moving Average (SMA) using the closing prices of completed candles.

5.**Crossover Detection:** Detects bullish crossovers when the closing price crosses above SMA 20 and bearish crossovers when it crosses below SMA 20.

6.**Duplicate Prevention:** Checks candle opening timestamps to prevent duplicate candles from being stored in the buffer.

7.**Automatic Reconnection:** Attempts to reconnect to Binance WebSocket after connection errors, using a 5-second retry delay.

8.**Missing Candle Recovery:** Uses Binance's REST API to fetch missing 1-minute candles when a timestamp gap is detected between stored candles and incoming live data.

 Testing and Validation

 Successfully connected to Binance WebSocket streams.
 Received and stored completed candles for both trading pairs.
 Verified bullish and bearish SMA 20 crossover signal generation.
 Tested automatic reconnection after a network interruption.
 Successfully recovered 8 missing ETHUSDT candles during a disconnect-recovery test.
 Confirmed that live candle streaming continued after recovery.

 Limitations

-Candle buffers are stored in memory and reset when the application stops.
-Missing-candle recovery has been verified for ETHUSDT; BTCUSDT recovery requires separate validation.
-The current recovery implementation may require additional handling for long gaps, failed REST requests, and repeated recovery attempts.
-SMA crossover signals are technical indicators and do not guarantee future price movements.

 Technologies Used

 Python
 Binance WebSocket API
 Binance REST API
 `websockets`
 `requests`
 `asyncio`
 `collections.deque`






 <!-- Task 4: Optimize Pandas Calculations -->

 Objective
Optimize Pandas calculations for large OHLCV datasets containing multiple cryptocurrency symbols while maintaining correct SMA-20 results.

 Dataset
 **Total rows:** 5,000,000
 **Symbols:** BTCUSDT and ETHUSDT
 **Rows per symbol:** 2,500,000
 **Columns:** symbol, open, high, low, close, volume

The dataset was synthetically generated using NumPy with a fixed random seed for reproducibility.

 Optimization Implemented
The original implementation used DataFrame.iterrows() to calculate the 20-period Simple Moving Average (SMA-20) row by row.

The optimized implementation uses Pandas `groupby()`, `transform()`, and `rolling().mean()` to calculate SMA-20 separately for each cryptocurrency symbol.

```python
df["SMA_20"] = (
    df.groupby("symbol", sort=False)["close"]
    .transform(
        lambda series: series.rolling(
            window=20,
            min_periods=20
        ).mean()
    )
)
```

 Benchmark Results

 Original vs. Optimized — 20,000 Rows

| Metric | Original iterrows() | Vectorized Pandas |
|---|---:|---:|
| Execution time | 1.8059 seconds | 0.0024 seconds |
| Measured speedup | — | 749.68x |
| Execution-time reduction | — | 99.87% |

Both implementations produced equivalent SMA values within the configured numerical tolerance.

 Large Dataset — 5,000,000 Rows

| Metric | Result |
|---|---:|
| Total rows processed | 5,000,000 |
| Data generation time | 0.38 seconds |
| DataFrame memory before SMA | 262.86 MB |
| Vectorized SMA execution time | 0.2939 seconds |
| DataFrame memory after SMA | 301.00 MB |
| Valid SMA-20 values | 4,999,962 |
| Output validation | PASS |

The original iterrows() implementation was not benchmarked on the 5-million-row dataset.

 Output Validation
The large-data test confirmed that:
 All 5,000,000 rows were processed.
 Both cryptocurrency symbols were retained.
 The expected number of valid SMA-20 values was produced.
 The output validation check passed.

The first 19 rows for each symbol contain NaN SMA values because 20 closing prices are required to calculate the first SMA-20 value.

 Conclusion
Vectorized Pandas operations substantially improved performance in the 20,000-row benchmark. The optimized implementation also processed 5 million OHLCV rows successfully, calculating SMA-20 in approximately 0.294 seconds on the test environment.

Actual performance may vary depending on hardware, software versions, and available memory.

