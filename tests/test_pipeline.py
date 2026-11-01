import main as market_data
import pandas as pd
import pytest

import indicators
import live_data
import resample_data
import task_optimization


@pytest.fixture
def sample_candles():
    """Create predictable hourly candles for two symbols."""
    rows = []
    times = pd.date_range(
        start="2026-04-01",
        periods=60,
        freq="h",
        tz="UTC",
    )

    for symbol in ["BTCUSDT", "ETHUSDT"]:
        for hour in range(60):
            price = 100 + hour

            rows.append({
                "symbol": symbol,
                "open_time": times[hour],
                "open": price,
                "high": price + 2,
                "low": price - 1,
                "close": price + 1,
                "volume": 10.0,
            })

    return pd.DataFrame(rows)


def test_indicators_are_calculated_per_symbol(sample_candles):
    result = indicators.calculate_indicators(sample_candles)

    assert len(result) == 120
    assert {"SMA_20", "EMA_20", "EMA_50"}.issubset(result.columns)

    for _, group in result.groupby("symbol"):
        group = group.reset_index(drop=True)

        assert group["SMA_20"].iloc[:19].isna().all()
        assert group["SMA_20"].iloc[19:].notna().all()
        assert group["EMA_20"].iloc[:19].isna().all()
        assert group["EMA_20"].iloc[19:].notna().all()
        assert group["EMA_50"].iloc[:49].isna().all()
        assert group["EMA_50"].iloc[49:].notna().all()

    # Indicator calculation should not modify the input DataFrame.
    assert "SMA_20" not in sample_candles.columns


def test_resample_to_four_hours(sample_candles):
    result = resample_data.resample_to_4h(sample_candles)

    assert len(result) == 30
    assert result.groupby("symbol").size().to_dict() == {
        "BTCUSDT": 15,
        "ETHUSDT": 15,
    }

    first_bar = result[
        (result["symbol"] == "BTCUSDT")
        & (
            result["open_time"]
            == pd.Timestamp("2026-04-01", tz="UTC")
        )
    ].iloc[0]

    assert first_bar["open"] == 100
    assert first_bar["high"] == 105
    assert first_bar["low"] == 99
    assert first_bar["close"] == 104
    assert first_bar["volume"] == 40


def test_sample_data_is_reproducible():
    first = task_optimization.create_sample_data(25)
    second = task_optimization.create_sample_data(25)

    pd.testing.assert_frame_equal(first, second)

    assert len(first) == 50
    assert first["symbol"].nunique() == 2


def test_vectorized_sma_values():
    candles = task_optimization.create_sample_data(25)
    result = task_optimization.calculate_sma_vectorized(candles)

    assert len(result) == 50
    assert result["SMA_20"].notna().sum() == 12

    for _, group in result.groupby("symbol"):
        assert group["SMA_20"].iloc[:19].isna().all()
        assert group["SMA_20"].iloc[19:].notna().all()


@pytest.fixture(autouse=True)
def reset_live_buffers():
    """Keep tests independent by clearing both candle buffers."""
    for buffer in live_data.candle_buffers.values():
        buffer.clear()


def make_candle(open_time, close=100):
    return {
        "symbol": "BTCUSDT",
        "open_time": open_time,
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": 10.0,
    }


def test_store_candle_ignores_duplicates():
    candle = make_candle(1_000)

    live_data.store_candle("BTCUSDT", candle)
    live_data.store_candle("BTCUSDT", candle)

    assert len(live_data.candle_buffers["BTCUSDT"]) == 1


def test_live_buffer_keeps_latest_100_candles():
    for minute in range(105):
        live_data.store_candle(
            "BTCUSDT",
            make_candle(minute * live_data.INTERVAL_MS),
        )

    buffer = live_data.candle_buffers["BTCUSDT"]

    assert len(buffer) == 100
    assert buffer[0]["open_time"] == 5 * live_data.INTERVAL_MS
    assert buffer[-1]["open_time"] == 104 * live_data.INTERVAL_MS


def test_incomplete_websocket_candle_is_ignored():
    candle = {
        "s": "BTCUSDT",
        "x": False,
        "t": 1_000,
        "o": "100",
        "h": "101",
        "l": "99",
        "c": "100",
        "v": "10",
    }

    live_data.process_candle(candle)

    assert len(live_data.candle_buffers["BTCUSDT"]) == 0


def test_unsupported_symbol_is_ignored():
    candle = {
        "s": "XRPUSDT",
        "x": True,
        "t": 1_000,
        "o": "100",
        "h": "101",
        "l": "99",
        "c": "100",
        "v": "10",
    }

    live_data.process_candle(candle)

    assert len(live_data.candle_buffers["BTCUSDT"]) == 0
    assert len(live_data.candle_buffers["ETHUSDT"]) == 0


def test_bullish_crossover_is_reported(capsys):
    buffer = live_data.candle_buffers["BTCUSDT"]

    for minute in range(20):
        buffer.append(
            make_candle(minute * live_data.INTERVAL_MS, close=10)
        )

    buffer.append(
        make_candle(20 * live_data.INTERVAL_MS, close=20)
    )

    live_data.check_sma_crossover("BTCUSDT")

    output = capsys.readouterr().out
    assert "BULLISH CROSSOVER: BTCUSDT" in output


def test_invalid_rest_range_skips_request(monkeypatch):
    def unexpected_request(*args, **kwargs):
        pytest.fail("REST request should not be made for an invalid range")

    monkeypatch.setattr(live_data.requests, "get", unexpected_request)

    result = live_data.fetch_missing_candles(
        "BTCUSDT",
        start_time=2_000,
        end_time=1_000,
    )

    assert result == []


def make_binance_row(open_time_ms, open_price="100", high="102",
                     low="99", close="101", volume="10"):
    return [
        open_time_ms, open_price, high, low, close, volume,
        open_time_ms + market_data.INTERVAL_MS - 1,
        "1000", 5, "4", "400", "0",
    ]


class FakeResponse:
    def __init__(self, rows):
        self.rows = rows

    def raise_for_status(self):
        return None

    def json(self):
        return self.rows


def test_fetch_candles_with_mock_api(monkeypatch, tmp_path):
    start = pd.Timestamp("2026-04-01 00:00:00", tz="UTC")
    monkeypatch.setattr(market_data, "START", start)
    monkeypatch.setattr(
        market_data, "END", start + pd.Timedelta(hours=2)
    )
    monkeypatch.setattr(market_data, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(market_data.time, "sleep", lambda _: None)

    rows = [
        make_binance_row(int(start.timestamp() * 1000)),
        make_binance_row(
            int((start + pd.Timedelta(hours=1)).timestamp() * 1000),
            open_price="101", high="103", low="100", close="102",
        ),
    ]

    monkeypatch.setattr(
        market_data.session, "get",
        lambda *args, **kwargs: FakeResponse(rows),
    )

    result = market_data.fetch_candles("BTCUSDT")

    assert len(result) == 2
    assert result["symbol"].eq("BTCUSDT").all()
    assert result["open_time"].is_monotonic_increasing
    assert result["close"].tolist() == [101, 102]


def test_fetch_candles_rejects_invalid_ohlc(monkeypatch, tmp_path):
    start = pd.Timestamp("2026-04-01 00:00:00", tz="UTC")
    monkeypatch.setattr(market_data, "START", start)
    monkeypatch.setattr(
        market_data, "END", start + pd.Timedelta(hours=1)
    )
    monkeypatch.setattr(market_data, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(market_data.time, "sleep", lambda _: None)

    invalid_row = make_binance_row(
        int(start.timestamp() * 1000),
        open_price="100", high="98", low="99", close="100",
    )

    monkeypatch.setattr(
        market_data.session, "get",
        lambda *args, **kwargs: FakeResponse([invalid_row]),
    )

    with pytest.raises(ValueError, match="invalid candles"):
        market_data.fetch_candles("BTCUSDT")


def test_fetch_candles_rejects_empty_api_response(monkeypatch):
    start = pd.Timestamp("2026-04-01 00:00:00", tz="UTC")
    monkeypatch.setattr(market_data, "START", start)
    monkeypatch.setattr(
        market_data, "END", start + pd.Timedelta(hours=1)
    )

    monkeypatch.setattr(
        market_data.session, "get",
        lambda *args, **kwargs: FakeResponse([]),
    )

    with pytest.raises(RuntimeError, match="No data received"):
        market_data.fetch_candles("BTCUSDT")


def test_fetch_candles_handles_multiple_api_pages(monkeypatch, tmp_path):
    start = pd.Timestamp("2026-04-01 00:00:00", tz="UTC")
    monkeypatch.setattr(market_data, "START", start)
    monkeypatch.setattr(
        market_data, "END", start + pd.Timedelta(hours=2)
    )
    monkeypatch.setattr(market_data, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(market_data.time, "sleep", lambda _: None)

    first_row = make_binance_row(int(start.timestamp() * 1000))
    second_row = make_binance_row(
        int((start + pd.Timedelta(hours=1)).timestamp() * 1000),
        open_price="101", high="103", low="100", close="102",
    )

    pages = [[first_row], [second_row]]
    calls = []

    def fake_get(*args, **kwargs):
        calls.append(kwargs["params"]["startTime"])
        return FakeResponse(pages[len(calls) - 1])

    monkeypatch.setattr(market_data.session, "get", fake_get)

    result = market_data.fetch_candles("BTCUSDT")

    assert len(calls) == 2
    assert len(result) == 2
    assert result["close"].tolist() == [101, 102]


